"""Ollama HTTP adapter — JSON-strict output + explicit model management.

Focused on pressarr's 3 use cases : text extraction from a torrent
name, vision extraction from a PDF cover image, and arbitration
between multiple sources. Every call forces ``format: "json"`` so
the response is guaranteed parseable.

Model switching : Ollama unloads inactive models based on
``OLLAMA_KEEP_ALIVE`` (default 5 min). We explicitly send
``keep_alive: 0`` on the last call for a model when we're about to
switch — frees VRAM immediately instead of waiting for the timer.
Loading a new model takes 5-30s (disk read) on the first call ; the
UI must show this as a "Chargement modèle X" step so the user
doesn't think the pipeline hung.

Every call is async ; the caller decides sequential vs parallel.
Pressarr's pipeline is intentionally sequential — the user prefers
predictable step-by-step progress in the queue over parallelism.
"""

from __future__ import annotations

import base64
import json
import logging
from pathlib import Path
from typing import Any

import httpx

logger = logging.getLogger(__name__)


class OllamaError(Exception):
    """Raised on any non-recoverable Ollama call failure.

    Recoverable cases (model not found → fallback) do NOT raise ;
    the caller inspects the returned dict for `error`.
    """


class OllamaAdapter:
    """Thin async wrapper over the Ollama HTTP API.

    ``url`` : http URL of the Ollama server, e.g. ``http://192.168.1.24:11434``.
    ``timeout_s`` : per-call timeout. Vision calls on CPU can push
    past 60s so callers should set a generous value (300s default).
    """

    def __init__(self, url: str, timeout_s: int = 300) -> None:
        self.url = (url or "http://localhost:11434").rstrip("/")
        self.timeout_s = timeout_s

    async def list_models(self) -> list[str]:
        """Return the names of every model currently pulled locally.

        Empty list on any failure — the caller uses that to decide
        whether to enable AI features in the UI.
        """
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                r = await client.get(f"{self.url}/api/tags")
                r.raise_for_status()
                data = r.json()
                return [m.get("name") for m in data.get("models", []) if m.get("name")]
        except Exception as exc:  # noqa: BLE001
            logger.warning("Ollama list_models failed: %s", exc)
            return []

    async def has_model(self, name: str) -> bool:
        """True when ``name`` is present in the local model list.

        Match is exact — ``mistral:7b`` won't match ``mistral:latest``.
        Callers should feed the exact tag they want.
        """
        return name in await self.list_models()

    async def unload_model(self, name: str) -> None:
        """Force-unload a model from RAM/VRAM.

        Ollama exposes this by sending an ``/api/generate`` with
        ``keep_alive: 0`` and an empty prompt. Free-form ping — we
        don't care about the response. Safe to call even when the
        model isn't currently loaded.
        """
        try:
            async with httpx.AsyncClient(timeout=15) as client:
                await client.post(
                    f"{self.url}/api/generate",
                    json={
                        "model": name,
                        "prompt": "",
                        "keep_alive": 0,
                        "stream": False,
                    },
                )
        except Exception as exc:  # noqa: BLE001
            logger.debug("Ollama unload %s failed (non-fatal): %s", name, exc)

    async def loaded_models(self) -> list[dict[str, Any]]:
        """Return the models currently resident in Ollama memory.

        Each dict has at least ``name`` and ``expires_at``. Used to
        detect a foreign model pinned by another process (keep_alive=-1
        → expires_at year 2300+) that would starve VRAM for ours.
        Empty list on any failure — the caller treats that as
        « unknown, proceed anyway ».
        """
        try:
            async with httpx.AsyncClient(timeout=5) as client:
                r = await client.get(f"{self.url}/api/ps")
                r.raise_for_status()
                return r.json().get("models", []) or []
        except Exception as exc:  # noqa: BLE001
            logger.debug("Ollama /api/ps failed (non-fatal): %s", exc)
            return []

    async def free_vram_for(self, needed_models: set[str]) -> list[str]:
        """Unload any loaded model that is NOT in ``needed_models``.

        Returns the names actually unloaded (best-effort — errors
        swallowed). Use before an enrichment run when a shared Ollama
        might have a foreign model pinned in VRAM.
        """
        loaded = await self.loaded_models()
        to_unload = [
            m.get("name") for m in loaded
            if m.get("name") and m["name"] not in needed_models
        ]
        for name in to_unload:
            await self.unload_model(name)
            logger.info("[ollama] freed VRAM by unloading foreign model %s", name)
        return to_unload

    async def generate_json(
        self,
        model: str,
        prompt: str,
        system: str | None = None,
        images_b64: list[str] | None = None,
        temperature: float = 0.2,
        num_ctx: int | None = None,
        num_predict: int | None = None,
        repeat_penalty: float | None = None,
    ) -> dict[str, Any]:
        """Run a single generation, force JSON output, parse it.

        Low temperature (0.2) by default — the tasks here are
        extraction/arbitration where determinism matters more than
        creativity. Vision + text share the same endpoint ; images
        are passed as base64 strings via the ``images`` field.

        ``num_ctx`` : override du contexte Ollama (défaut 4096 pour
        la plupart des modèles). Une image PDF rendue à 350 DPI
        encodée base64 consomme 3000-8000 tokens vision selon la
        taille — passer ``num_ctx=16384`` évite les
        ``exceed_context_size_error`` HTTP 400 vus sur qwen2.5vl:7b
        avec de grosses images.

        ``num_predict`` : plafond sur la taille de la génération.
        Utile pour les vision sur bandeaux difficiles à OCRer :
        minicpm-v entre parfois en boucle de répétition
        (« SCANIA:C6H7D/SCANIA:C6H7D/… ») qui casse le JSON. Un cap
        800 tokens laisse ~600 pour un masthead + JSON structure.

        ``repeat_penalty`` : > 1.0 pénalise les tokens récemment vus.
        1.3 sur vision aide à casser les loops sans étouffer un
        raw_text légitime.

        Returns the parsed dict. Raises ``OllamaError`` if the call
        itself failed or the response was totally unusable. Malformed
        JSON is best-effort salvaged (truncated ``raw_text`` field
        etc.) before giving up.
        """
        options: dict[str, Any] = {"temperature": temperature}
        if num_ctx is not None:
            options["num_ctx"] = num_ctx
        if num_predict is not None:
            options["num_predict"] = num_predict
        if repeat_penalty is not None:
            options["repeat_penalty"] = repeat_penalty
        payload: dict[str, Any] = {
            "model": model,
            "prompt": prompt,
            "stream": False,
            "format": "json",
            "options": options,
        }
        if system:
            payload["system"] = system
        if images_b64:
            payload["images"] = images_b64

        try:
            async with httpx.AsyncClient(timeout=self.timeout_s) as client:
                r = await client.post(f"{self.url}/api/generate", json=payload)
                r.raise_for_status()
                data = r.json()
        except httpx.HTTPStatusError as exc:
            raise OllamaError(
                f"Ollama HTTP {exc.response.status_code}: {exc.response.text[:200]}"
            ) from exc
        except Exception as exc:  # noqa: BLE001
            raise OllamaError(f"Ollama request failed: {exc}") from exc

        raw = data.get("response", "")
        if not raw:
            raise OllamaError("Ollama returned an empty response body")
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            salvaged = _salvage_partial_json(raw)
            if salvaged is not None:
                logger.warning(
                    "Ollama returned malformed JSON, salvaged partial keys=%s",
                    list(salvaged.keys()),
                )
                return salvaged
            # Detect the repetition-loop pattern to give the caller a
            # useful hint (« vision loop » instead of raw JSON dump).
            hint = _describe_bad_response(raw)
            raise OllamaError(hint)


def _salvage_partial_json(raw: str) -> dict[str, Any] | None:
    """Best-effort recovery of a truncated / loop-broken JSON response.

    Ollama with ``format: json`` sometimes cuts mid-value when the model
    hits ``num_predict`` or gets stuck in a repetition loop. The prefix
    is usually a valid object opening ; we regex-grab whatever we can
    for the vision-shape (``title``, ``raw_text``) and return a dict
    with just those, so the downstream Python arbiter can still glean
    what the model DID see. Returns None when nothing usable is
    extractable.
    """
    import re
    out: dict[str, Any] = {}
    # title : accept null or "..."
    m = re.search(r'"title"\s*:\s*(?:null|"((?:[^"\\]|\\.)*)")', raw)
    if m:
        out["title"] = m.group(1) if m.group(1) is not None else None
    # raw_text : take everything up to the next unescaped quote OR
    # end of the truncated string. Cap 4 KB to shed loop garbage.
    m = re.search(r'"raw_text"\s*:\s*"((?:[^"\\]|\\.){0,4096})', raw)
    if m:
        # Best-effort unescape of the common sequences.
        rt = m.group(1)
        rt = rt.replace(r"\n", "\n").replace(r"\t", "\t").replace(r'\"', '"')
        # Trim repetition tails (« FOO FOO FOO FOO … ») : detect any
        # 4-token substring that repeats ≥ 3× and cut before the loop.
        cleaned = _trim_repetition_tail(rt)
        out["raw_text"] = cleaned
    return out or None


def _trim_repetition_tail(text: str, min_len: int = 4, min_reps: int = 3) -> str:
    """Cut the string at the first repetition-loop pattern detected.

    Returns the prefix up to (but not including) the start of the loop.
    Idempotent : text without a loop is returned unchanged.
    """
    import re
    if not text:
        return text
    # Match a phrase of ≥ min_len characters that repeats ≥ min_reps
    # times back to back. Non-greedy inner group so we catch the
    # smallest repeating unit.
    pattern = rf"(.{{{min_len},}}?)(?:\1){{{min_reps - 1},}}"
    m = re.search(pattern, text)
    if m:
        return text[:m.start()].rstrip()
    return text


def _describe_bad_response(raw: str) -> str:
    """Convert a raw broken Ollama response into a short human hint."""
    snippet = raw[:200].replace("\n", " ")
    # Loop signature ?
    trimmed = _trim_repetition_tail(raw, min_len=8, min_reps=4)
    if trimmed != raw and len(trimmed) < len(raw) * 0.5:
        return (
            "Vision loop détectée (le modèle a répété la même chaîne "
            "sans jamais fermer le JSON). Prompt/zone à revoir. "
            f"Prefix : {snippet}"
        )
    return f"Ollama response was not valid JSON: {snippet}"


def encode_image_file(path: Path) -> str:
    """Base64-encode an image file for the Ollama ``images`` field.

    Raises FileNotFoundError if the file doesn't exist — the caller
    should have checked already since a missing cover image usually
    means the PDF-to-PNG conversion failed one step earlier.
    """
    with open(path, "rb") as f:
        return base64.b64encode(f.read()).decode("ascii")
