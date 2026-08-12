"""Application configuration with YAML file + environment variable override."""

import os
import secrets
from pathlib import Path

import yaml


class Config:
    """Configuration loaded from YAML with PRESSARR__* env overrides."""

    def __init__(self) -> None:
        self.config_path = Path(
            os.environ.get("PRESSARR__CONFIG_PATH", "/config/pressarr.yml")
        )
        self.db_path = Path(
            os.environ.get("PRESSARR__DB_PATH", "/config/pressarr.db")
        )
        self.port: int = 8585
        self.log_level: str = "info"
        self.api_key: str = ""
        self.auth_enabled: bool = False

        # Scheduler intervals (seconds)
        self.rss_sync_interval: int = 1800  # 30 minutes
        self.download_check_interval: int = 30
        self.history_purge_interval: int = 86400  # 24 hours
        self.forecast_refresh_interval: int = 86400
        self.metadata_refresh_interval: int = 86400
        self.history_retention_days: int = 365

        # Naming template
        self.naming_template: str = (
            "{magazine_title}/{magazine_title} - {number} ({year}-{month:02d}).{format}"
        )

        # Metadata sources
        self.google_books_api_key: str = ""
        self.internet_archive_enabled: bool = True
        self.annas_archive_enabled: bool = False
        self.annas_archive_mirror: str = "annas-archive.li"

        # FlareSolverr-compatible bypass endpoint (default of
        # ``http://flaresolverr:8191/v1`` matches grabarr's
        # docker-compose so a single sidecar serves both apps).
        # When set + reachable, scrapers that hit anti-bot walls
        # (Bookys is behind CHEQ AI; future French scene sites
        # often hide behind Cloudflare) route their HTTP through
        # this endpoint instead of httpx. Empty string disables
        # bypass — those scrapers then fail gracefully.
        self.flaresolverr_url: str = "http://flaresolverr:8191/v1"
        self.flaresolverr_timeout_ms: int = 60000

        # Scene magazine indexers. These scrape HTML — no public
        # API exists — so they're disabled by default; operators
        # turn them on explicitly. Credentials are stored in
        # plaintext, same pattern as other provider settings;
        # pressarr can grow a real secrets store later without
        # touching this file's contract.
        self.bookys_enabled: bool = False
        # Bookys defaults to bookys-gratuit.com; some operators
        # use a mirror so it stays configurable. Trailing slash
        # is stripped at load time so the rest of the code can
        # concatenate paths freely.
        self.bookys_url: str = "https://www6.bookys-ebooks.com"
        self.bookys_username: str = ""
        self.bookys_password: str = ""
        self.telecharger_magazines_enabled: bool = False
        self.telecharger_magazines_url: str = (
            "https://www.telecharger-magazines.org"
        )

        # JDownloader 2 folder-watch dispatcher. When enabled,
        # ``POST /api/v1/magazine/{id}/releases/{rid}/grab``
        # writes a ``.crawljob`` file (JD2's native batch format,
        # plain text key=value) into ``jdownloader_folderwatch``
        # and JD2 — running side-by-side with pressarr in
        # docker-compose — picks it up via its Folder Watch
        # extension. No HTTP API call needed; far more robust
        # than the My JDownloader cloud client and friendlier
        # to self-hosters.
        self.jdownloader_enabled: bool = False
        self.jdownloader_folderwatch: str = "/downloads/jd2/folderwatch"
        # Where finished downloads land. Used by both JD2 (final
        # ``downloaddir`` of every dispatched job) and pressarr
        # (the importer polls this dir to mark releases as
        # ``imported``).
        self.jdownloader_output_path: str = "/downloads/jd2/complete"
        # JD2's *internal* view of the same output dir. The
        # ``.crawljob`` ``downloadFolder=`` field is read by JD2
        # which lives in its own container with its own mounts.
        # Default matches the upstream ``jlesage/jdownloader-2``
        # image where downloads land at ``/jdownloader/downloads``.
        # If the operator runs a different JD2 image they adjust
        # this; the dispatcher writes this value verbatim into the
        # crawljob so the path is whatever JD2 expects.
        self.jdownloader_output_path_in_jd2: str = "/jdownloader/downloads"

        # Import mode: copy, move, or copy_delete
        self.import_mode: str = "copy"

        # Download path for IA direct downloads
        self.download_path: str = "/tmp/pressarr_downloads"

        # --- AI (Ollama) ---
        # Local LLM enrichment of metadata + search ranking. Disabled
        # by default — enable in Settings → IA. All models must exist
        # on the Ollama server (pressarr does NOT pull models on its
        # own; the operator is responsible for `ollama pull <name>`
        # before enabling). Missing model → the pipeline logs a warning
        # and falls back gracefully (regex parser for enrichment, native
        # scorer for ranker) without failing the parent job.
        self.ai_ollama_url: str = "http://localhost:11434"
        self.ai_ollama_timeout_s: int = 300

        # Metadata enrichment (torrent name → text LLM + PDF cover →
        # vision LLM + arbiter that merges the two).
        self.ai_enrichment_enabled: bool = False
        # 3 modes : "remplace" (overwrite), "complete" (fill nulls only),
        # "propose" (store as proposals for user validation, don't touch
        # the imported metadata directly).
        self.ai_enrichment_mode: str = "remplace"
        # Pages passed to vision — negatives count from the end.
        # Example: [1] = cover only ; [1, -1] = cover + back cover.
        self.ai_enrichment_vision_pages: list[int] = [1]
        self.ai_text_model: str = "mistral:7b"
        self.ai_vision_model: str = "minicpm-v:8b"
        # Prompts — operator-editable. Kept short + explicit JSON
        # contract so small models don't drift.
        self.ai_text_prompt: str = (
            "Analyse ce nom de fichier torrent d'un magazine et "
            "extrais UNIQUEMENT les informations claires et précises. "
            "Si un élément est ambigu ou absent, mets `null`.\n\n"
            "Réponds avec un objet JSON strict :\n"
            "{\"title\": str|null, \"issue_number\": int|null, "
            "\"year\": int|null, \"month\": int|null, \"day\": int|null, "
            "\"is_hs\": bool, \"series_number\": int|null}\n\n"
            "`is_hs` = true si c'est un hors-série (mots clés : HS, "
            "Hors-Série, Spécial, Numéro spécial). `series_number` = "
            "numéro de la série si HS numéroté."
        )
        self.ai_vision_prompt: str = (
            "Regarde la couverture de ce magazine. Extrais UNIQUEMENT "
            "le titre principal (en très gros), le numéro d'issue, et "
            "la date de publication si elle est visible. Ignore les "
            "titres d'articles.\n\n"
            "Réponds avec un objet JSON strict :\n"
            "{\"title\": str|null, \"issue_number\": int|null, "
            "\"date_text\": str|null}\n\n"
            "`date_text` = date brute telle que vue sur la couverture "
            "(ex. \"Mars 2024\", \"15 Janvier 2025\")."
        )
        self.ai_arbiter_prompt: str = (
            "Tu reçois deux extractions de métadonnées pour le même "
            "magazine : l'une venant du nom du fichier torrent (source "
            "PRIMAIRE), l'autre de l'OCR vision de la couverture "
            "(source SECONDAIRE, sert à compléter les trous).\n\n"
            "Règles :\n"
            "- Si `torrent` a une valeur non-null, garde-la.\n"
            "- Sinon utilise la valeur de `vision`.\n"
            "- Pour la date : convertis toute expression texte en "
            "year/month/day numériques.\n"
            "- Ne remplis JAMAIS une valeur `null` par une invention.\n\n"
            "Réponds avec un objet JSON strict :\n"
            "{\"title\": str|null, \"issue_number\": int|null, "
            "\"year\": int|null, \"month\": int|null, \"day\": int|null, "
            "\"is_hs\": bool, \"series_number\": int|null, "
            "\"confidence\": float}\n\n"
            "`confidence` entre 0 et 1 = ton estimation globale de la "
            "fiabilité du résultat."
        )

        # Search ranker (compare N releases et donne un avis).
        self.ai_ranker_enabled: bool = False
        # 3 modes : "ai_wins" (IA tranche), "ai_veto_only" (IA peut
        # refuser le top scorer mais ne modifie pas l'ordre), "ai_advisory"
        # (log seulement, ne change rien — mode observation par défaut).
        self.ai_ranker_mode: str = "ai_advisory"
        self.ai_ranker_batch_size: int = 5
        self.ai_ranker_top_k: int = 15  # candidats du scorer envoyés à l'IA
        self.ai_ranker_confidence_threshold: float = 0.6
        self.ai_ranker_prompt: str = (
            "Tu reçois une liste de releases candidates pour un "
            "magazine. Ton job : choisir la MEILLEURE correspondance ou "
            "refuser TOUS les candidats s'ils sont manifestement hors-"
            "sujet.\n\n"
            "Critères de choix (par ordre décroissant) :\n"
            "1. Le titre du magazine et le numéro d'issue correspondent\n"
            "2. La date de publication colle avec le numéro attendu\n"
            "3. Pas de mention parasite (best-of, compilation, etc.) "
            "sauf demande explicite\n\n"
            "Réponds avec un objet JSON strict :\n"
            "{\"picked_index\": int|null, \"confidence\": float, "
            "\"reason\": str}\n\n"
            "`picked_index` = 0-based index du candidat choisi, ou "
            "`null` si tu refuses toute la liste. `confidence` entre 0 "
            "et 1. `reason` = phrase courte expliquant ton choix."
        )

        self._load_yaml()
        self._apply_env_overrides()

    def _load_yaml(self) -> None:
        """Load configuration from YAML file if it exists."""
        if not self.config_path.exists():
            return

        with open(self.config_path) as f:
            data = yaml.safe_load(f) or {}

        self.port = data.get("port", self.port)
        self.log_level = data.get("log_level", self.log_level)
        self.api_key = data.get("api_key", self.api_key)
        self.auth_enabled = data.get("auth_enabled", self.auth_enabled)
        self.db_path = Path(data.get("db_path", str(self.db_path)))
        self.naming_template = data.get("naming_template", self.naming_template)

        metadata = data.get("metadata", {})
        self.google_books_api_key = metadata.get(
            "google_books_api_key", self.google_books_api_key
        )
        self.internet_archive_enabled = metadata.get(
            "internet_archive_enabled", self.internet_archive_enabled
        )
        self.annas_archive_enabled = metadata.get(
            "annas_archive_enabled", self.annas_archive_enabled
        )
        self.annas_archive_mirror = metadata.get(
            "annas_archive_mirror", self.annas_archive_mirror
        )

        bypass = data.get("bypass", {})
        self.flaresolverr_url = bypass.get(
            "flaresolverr_url", self.flaresolverr_url
        )
        self.flaresolverr_timeout_ms = bypass.get(
            "flaresolverr_timeout_ms", self.flaresolverr_timeout_ms
        )

        indexers = data.get("indexers", {})
        bookys = indexers.get("bookys", {})
        self.bookys_enabled = bookys.get("enabled", self.bookys_enabled)
        self.bookys_url = bookys.get("url", self.bookys_url).rstrip("/")
        self.bookys_username = bookys.get("username", self.bookys_username)
        self.bookys_password = bookys.get("password", self.bookys_password)
        tm = indexers.get("telecharger_magazines", {})
        self.telecharger_magazines_enabled = tm.get(
            "enabled", self.telecharger_magazines_enabled
        )
        self.telecharger_magazines_url = tm.get(
            "url", self.telecharger_magazines_url
        ).rstrip("/")

        download_clients = data.get("download_clients", {})
        jd = download_clients.get("jdownloader", {})
        self.jdownloader_enabled = jd.get(
            "enabled", self.jdownloader_enabled
        )
        self.jdownloader_folderwatch = jd.get(
            "folderwatch", self.jdownloader_folderwatch
        )
        self.jdownloader_output_path = jd.get(
            "output_path", self.jdownloader_output_path
        )
        self.jdownloader_output_path_in_jd2 = jd.get(
            "output_path_in_jd2", self.jdownloader_output_path_in_jd2
        )

        self.import_mode = data.get("import_mode", self.import_mode)
        self.download_path = data.get("download_path", self.download_path)

        ai = data.get("ai", {})
        self.ai_ollama_url = ai.get("ollama_url", self.ai_ollama_url)
        self.ai_ollama_timeout_s = ai.get("ollama_timeout_s", self.ai_ollama_timeout_s)
        enr = ai.get("enrichment", {})
        self.ai_enrichment_enabled = enr.get("enabled", self.ai_enrichment_enabled)
        self.ai_enrichment_mode = enr.get("mode", self.ai_enrichment_mode)
        self.ai_enrichment_vision_pages = enr.get(
            "vision_pages", self.ai_enrichment_vision_pages
        )
        self.ai_text_model = enr.get("text_model", self.ai_text_model)
        self.ai_vision_model = enr.get("vision_model", self.ai_vision_model)
        self.ai_text_prompt = enr.get("text_prompt", self.ai_text_prompt)
        self.ai_vision_prompt = enr.get("vision_prompt", self.ai_vision_prompt)
        self.ai_arbiter_prompt = enr.get("arbiter_prompt", self.ai_arbiter_prompt)
        rnk = ai.get("ranker", {})
        self.ai_ranker_enabled = rnk.get("enabled", self.ai_ranker_enabled)
        self.ai_ranker_mode = rnk.get("mode", self.ai_ranker_mode)
        self.ai_ranker_batch_size = rnk.get("batch_size", self.ai_ranker_batch_size)
        self.ai_ranker_top_k = rnk.get("top_k", self.ai_ranker_top_k)
        self.ai_ranker_confidence_threshold = rnk.get(
            "confidence_threshold", self.ai_ranker_confidence_threshold
        )
        self.ai_ranker_prompt = rnk.get("prompt", self.ai_ranker_prompt)

        scheduler = data.get("scheduler", {})
        self.rss_sync_interval = scheduler.get(
            "rss_sync_interval", self.rss_sync_interval
        )
        self.download_check_interval = scheduler.get(
            "download_check_interval", self.download_check_interval
        )
        self.history_purge_interval = scheduler.get(
            "history_purge_interval", self.history_purge_interval
        )
        self.forecast_refresh_interval = scheduler.get(
            "forecast_refresh_interval", self.forecast_refresh_interval
        )
        self.history_retention_days = scheduler.get(
            "history_retention_days", self.history_retention_days
        )

    def _apply_env_overrides(self) -> None:
        """Override config with PRESSARR__* environment variables."""
        prefix = "PRESSARR__"
        for key, value in os.environ.items():
            if not key.startswith(prefix):
                continue
            config_key = key[len(prefix):].lower()
            if config_key == "port":
                self.port = int(value)
            elif config_key == "log_level":
                self.log_level = value
            elif config_key == "api_key":
                self.api_key = value
            elif config_key == "auth_enabled":
                self.auth_enabled = value.lower() in ("true", "1", "yes")
            elif config_key == "db_path":
                self.db_path = Path(value)
            elif config_key == "config_path":
                pass  # Already handled in __init__
            elif config_key == "naming_template":
                self.naming_template = value

    def generate_api_key(self) -> str:
        """Generate a new API key and persist it to config."""
        self.api_key = secrets.token_hex(16)
        self.save()
        return self.api_key

    def save(self) -> None:
        """Save current configuration to YAML file."""
        self.config_path.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "port": self.port,
            "log_level": self.log_level,
            "api_key": self.api_key,
            "auth_enabled": self.auth_enabled,
            "db_path": str(self.db_path),
            "naming_template": self.naming_template,
            "import_mode": self.import_mode,
            "download_path": self.download_path,
            "metadata": {
                "google_books_api_key": self.google_books_api_key,
                "internet_archive_enabled": self.internet_archive_enabled,
                "annas_archive_enabled": self.annas_archive_enabled,
                "annas_archive_mirror": self.annas_archive_mirror,
            },
            "bypass": {
                "flaresolverr_url": self.flaresolverr_url,
                "flaresolverr_timeout_ms": self.flaresolverr_timeout_ms,
            },
            "indexers": {
                "bookys": {
                    "enabled": self.bookys_enabled,
                    "url": self.bookys_url,
                    "username": self.bookys_username,
                    "password": self.bookys_password,
                },
                "telecharger_magazines": {
                    "enabled": self.telecharger_magazines_enabled,
                    "url": self.telecharger_magazines_url,
                },
            },
            "download_clients": {
                "jdownloader": {
                    "enabled": self.jdownloader_enabled,
                    "folderwatch": self.jdownloader_folderwatch,
                    "output_path": self.jdownloader_output_path,
                    "output_path_in_jd2": self.jdownloader_output_path_in_jd2,
                },
            },
            "scheduler": {
                "rss_sync_interval": self.rss_sync_interval,
                "download_check_interval": self.download_check_interval,
                "history_purge_interval": self.history_purge_interval,
                "forecast_refresh_interval": self.forecast_refresh_interval,
                "history_retention_days": self.history_retention_days,
            },
            "ai": {
                "ollama_url": self.ai_ollama_url,
                "ollama_timeout_s": self.ai_ollama_timeout_s,
                "enrichment": {
                    "enabled": self.ai_enrichment_enabled,
                    "mode": self.ai_enrichment_mode,
                    "vision_pages": self.ai_enrichment_vision_pages,
                    "text_model": self.ai_text_model,
                    "vision_model": self.ai_vision_model,
                    "text_prompt": self.ai_text_prompt,
                    "vision_prompt": self.ai_vision_prompt,
                    "arbiter_prompt": self.ai_arbiter_prompt,
                },
                "ranker": {
                    "enabled": self.ai_ranker_enabled,
                    "mode": self.ai_ranker_mode,
                    "batch_size": self.ai_ranker_batch_size,
                    "top_k": self.ai_ranker_top_k,
                    "confidence_threshold": self.ai_ranker_confidence_threshold,
                    "prompt": self.ai_ranker_prompt,
                },
            },
        }
        with open(self.config_path, "w") as f:
            yaml.dump(data, f, default_flow_style=False, sort_keys=False)
