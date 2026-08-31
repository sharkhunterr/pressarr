"""Deterministic Python OCR — 3ᵉ source d'extraction texte aux côtés
de l'analyse nom-torrent (text LLM) et de l'IA vision.

Trois moteurs interchangeables via config ``ai_python_ocr_engine`` :

  - ``tesseract`` : rapide (~1 s), léger (~15 MB + apt tesseract-ocr-fra),
    excellent en imprimé net. Sensible aux textes stylisés / couleurs.
  - ``rapidocr``  : ONNX runtime, ~100 MB modèles inclus, bon compromis
    précision/poids. Pas d'install système.
  - ``easyocr``   : PyTorch, ~500 MB, très robuste sur textes stylisés
    et multi-langue. Le plus lourd des trois.

Chaque backend expose la même méthode ``read(png_bytes) -> str``.
L'engine est instancié à la demande et mis en cache module-level
(warm-up 3-5 s pour easyocr/rapidocr).

Le résultat brut est joint dans le pool text du ``_arbitrate`` Python,
et surfacé comme source 4 dans le prompt arbiter LLM. Deterministic
+ IA vision = deux sources indépendantes qui se corroborent, l'arbiter
tranche.
"""
from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


ENGINE_NAMES = ("tesseract", "rapidocr", "easyocr")


class OCREngineError(RuntimeError):
    """Raised when an engine is unavailable OR the call itself failed.

    The caller (enrich pipeline) swallows and continues — losing the
    python_ocr source is not fatal, we still have LLM vision + torrent.
    """


class _BaseOCR:
    """Common contract : read(png_bytes) → str (may be empty)."""

    name: str = "base"

    def read(self, png_bytes: bytes) -> str:  # pragma: no cover - iface
        raise NotImplementedError


# ---------------------------------------------------------------------------
# Tesseract backend
# ---------------------------------------------------------------------------


class _TesseractOCR(_BaseOCR):
    name = "tesseract"

    def __init__(self) -> None:
        try:
            import pytesseract  # noqa: F401
            from PIL import Image  # noqa: F401
        except ImportError as e:
            raise OCREngineError(
                "pytesseract / Pillow non installés — "
                "`pip install pytesseract`"
            ) from e
        # Vérifie que le binaire tesseract est bien présent (apt).
        import subprocess
        try:
            subprocess.run(
                ["tesseract", "--version"],
                capture_output=True, timeout=5, check=True,
            )
        except (FileNotFoundError, subprocess.CalledProcessError,
                subprocess.TimeoutExpired) as e:
            raise OCREngineError(
                "binaire système `tesseract` introuvable — "
                "`apt-get install tesseract-ocr tesseract-ocr-fra`"
            ) from e

    def read(self, png_bytes: bytes) -> str:
        import io

        import pytesseract
        from PIL import Image, ImageOps
        try:
            img = Image.open(io.BytesIO(png_bytes))

            # --- Preprocessing pour améliorer la reconnaissance ---
            # Tesseract lit beaucoup mieux avec un contraste net et un
            # texte assez grand. Sur les crops fins (Prix/Date/Numéro)
            # renderés en couleur avec fond légèrement teinté, la reco
            # rate 1 char sur 3 (`Q9E` au lieu de `82E`, `JQL ITAINE`
            # au lieu de `2E ANNÉE`).

            # 1. Grayscale (le fond teinté noircit les chars fins)
            if img.mode != "L":
                img = img.convert("L")
            # 2. Auto-contrast strict — noircit le texte, éclaircit le fond
            img = ImageOps.autocontrast(img, cutoff=2)
            # 3. Upscale ×2 si le côté court < 200 px (auto-fit ~400 px)
            #    Tesseract est optimisé pour du texte à ~30-40 px de haut.
            w, h = img.size
            short = min(w, h)
            if short < 200:
                factor = min(3, max(2, 400 // max(1, short)))
                img = img.resize((w * factor, h * factor), Image.LANCZOS)

            # `fra+eng` : force les 2 langues au cas où le magazine
            # contient un titre anglais (« Vogue Business »).
            # `--psm 6` : traite l'image comme un bloc de texte uniforme
            #            (défaut = 3 = auto page segment, source de bruit
            #            sur crops petits où Tesseract cherche des colonnes
            #            inexistantes → hallucine des chars).
            # `--oem 1` : moteur LSTM only (meilleure reco que legacy).
            txt = pytesseract.image_to_string(
                img,
                lang="fra+eng",
                config="--psm 6 --oem 1",
            )
            return (txt or "").strip()
        except pytesseract.TesseractNotFoundError as e:
            raise OCREngineError(str(e)) from e
        except Exception as e:  # noqa: BLE001
            raise OCREngineError(f"tesseract call failed: {e}") from e


# ---------------------------------------------------------------------------
# RapidOCR backend (ONNX)
# ---------------------------------------------------------------------------


class _RapidOCR(_BaseOCR):
    name = "rapidocr"

    def __init__(self) -> None:
        try:
            from rapidocr_onnxruntime import RapidOCR
        except ImportError as e:
            raise OCREngineError(
                "rapidocr_onnxruntime non installé — "
                "`pip install rapidocr-onnxruntime`"
            ) from e
        # Warm-up : charge les 3 modèles ONNX (det+cls+rec).
        # Coûteux la 1ère fois (~3-5 s), négligeable ensuite grâce
        # au cache module-level.
        self._engine = RapidOCR()

    def read(self, png_bytes: bytes) -> str:
        import io

        import numpy as np
        from PIL import Image
        try:
            img = np.array(Image.open(io.BytesIO(png_bytes)).convert("RGB"))
            result, _ = self._engine(img)
            if not result:
                return ""
            # ``result`` = list[(bbox, text, confidence)].
            return "\n".join(r[1] for r in result if len(r) >= 2 and r[1])
        except Exception as e:  # noqa: BLE001
            raise OCREngineError(f"rapidocr call failed: {e}") from e


# ---------------------------------------------------------------------------
# EasyOCR backend (PyTorch)
# ---------------------------------------------------------------------------


class _EasyOCR(_BaseOCR):
    name = "easyocr"

    def __init__(self) -> None:
        try:
            import easyocr  # noqa: F401
        except ImportError as e:
            raise OCREngineError(
                "easyocr non installé — `pip install easyocr` "
                "(tire ~500 MB de PyTorch)"
            ) from e
        import easyocr as _easyocr
        # gpu=False pour rester compatible avec les VM/containers
        # sans CUDA. On paye ~2-3× le temps CPU mais on évite
        # l'échec silencieux sur les hôtes non-GPU.
        # Premier appel : download des poids fra+eng (~120 MB, mis
        # en cache sous ~/.EasyOCR/).
        self._reader = _easyocr.Reader(["fr", "en"], gpu=False, verbose=False)

    def read(self, png_bytes: bytes) -> str:
        import io

        import numpy as np
        from PIL import Image
        try:
            img = np.array(Image.open(io.BytesIO(png_bytes)).convert("RGB"))
            # detail=0 → renvoie juste la liste des strings détectées,
            # sans bbox ni confidence. Suffit pour le pool text.
            lines = self._reader.readtext(img, detail=0, paragraph=False)
            return "\n".join(lines or [])
        except Exception as e:  # noqa: BLE001
            raise OCREngineError(f"easyocr call failed: {e}") from e


# ---------------------------------------------------------------------------
# Factory + cache
# ---------------------------------------------------------------------------


_ENGINE_CACHE: dict[str, _BaseOCR] = {}


def get_engine(name: str) -> _BaseOCR:
    """Return a cached engine instance, warming up on first request.

    ``name`` : one of ``ENGINE_NAMES``. Raises ``OCREngineError`` when
    the engine is unknown OR its dependency is missing.
    """
    key = (name or "").lower().strip()
    if key not in ENGINE_NAMES:
        raise OCREngineError(
            f"unknown OCR engine '{name}' (expected one of {ENGINE_NAMES})"
        )
    cached = _ENGINE_CACHE.get(key)
    if cached is not None:
        return cached
    logger.info("Warming up python-OCR engine: %s", key)
    if key == "tesseract":
        eng = _TesseractOCR()
    elif key == "rapidocr":
        eng = _RapidOCR()
    else:  # easyocr
        eng = _EasyOCR()
    _ENGINE_CACHE[key] = eng
    return eng


def probe_available() -> dict[str, dict[str, Any]]:
    """Introspect which engines are usable — LÉGER (pas de warm-up).

    ⚠️ Ne PAS appeler ``get_engine()`` ici : ça charge PyTorch pour
    easyocr (~5 s) et les modèles ONNX pour rapidocr (~3 s). La page
    Settings/AI appelle probe au load — un warm-up bloque le rendu.

    On teste juste :
      - ``tesseract``  : présence du binaire système + pytesseract Python
      - ``rapidocr``   : présence du package Python
      - ``easyocr``    : présence du package Python

    Le warm-up réel se fera au premier appel OCR (paye le coût la 1ère
    fois, cache pour la suite).
    """
    import importlib.util
    import shutil
    import subprocess

    def _pkg_installed(name: str) -> bool:
        return importlib.util.find_spec(name) is not None

    out: dict[str, dict[str, Any]] = {}

    # Tesseract : binaire + pytesseract
    if not _pkg_installed("pytesseract"):
        out["tesseract"] = {
            "available": False,
            "error": "pytesseract non installé — `pip install pytesseract`",
        }
    elif shutil.which("tesseract") is None:
        # Fallback : peut être installé mais pas dans le PATH
        try:
            subprocess.run(
                ["tesseract", "--version"],
                capture_output=True, timeout=2, check=True,
            )
            out["tesseract"] = {"available": True, "error": None}
        except Exception:  # noqa: BLE001
            out["tesseract"] = {
                "available": False,
                "error": (
                    "binaire système `tesseract` introuvable — "
                    "`apt-get install tesseract-ocr tesseract-ocr-fra`"
                ),
            }
    else:
        out["tesseract"] = {"available": True, "error": None}

    # RapidOCR
    if _pkg_installed("rapidocr_onnxruntime"):
        out["rapidocr"] = {"available": True, "error": None}
    else:
        out["rapidocr"] = {
            "available": False,
            "error": "rapidocr_onnxruntime non installé",
        }

    # EasyOCR
    if _pkg_installed("easyocr"):
        out["easyocr"] = {"available": True, "error": None}
    else:
        out["easyocr"] = {
            "available": False,
            "error": "easyocr non installé (tire ~500 MB de PyTorch)",
        }

    return out
