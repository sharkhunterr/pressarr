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

    async def generate_json(
        self,
        model: str,
        prompt: str,
        system: str | None = None,
        images_b64: list[str] | None = None,
        temperature: float = 0.2,
        num_ctx: int | None = None,
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

        Returns the parsed dict. Raises ``OllamaError`` if the call
        itself failed or the response was not valid JSON. The caller
        catches and decides whether to fallback or fail.
        """
        options: dict[str, Any] = {"temperature": temperature}
        if num_ctx is not None:
            options["num_ctx"] = num_ctx
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
        except json.JSONDecodeError as exc:
            raise OllamaError(
                f"Ollama response was not valid JSON: {raw[:200]}"
            ) from exc


def encode_image_file(path: Path) -> str:
    """Base64-encode an image file for the Ollama ``images`` field.

    Raises FileNotFoundError if the file doesn't exist — the caller
    should have checked already since a missing cover image usually
    means the PDF-to-PNG conversion failed one step earlier.
    """
    with open(path, "rb") as f:
        return base64.b64encode(f.read()).decode("ascii")
