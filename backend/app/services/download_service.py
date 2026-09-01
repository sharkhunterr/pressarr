"""Download management service."""
import json
import logging
from dataclasses import asdict, dataclass
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.download_client import DownloadClient
from app.models.issue import Issue
from app.schemas.search import GrabResponse
from app.services.history_service import create_event

logger = logging.getLogger(__name__)

# Persistent file for grab registry (survives container restarts)
_GRAB_REGISTRY_PATH: Path | None = None


@dataclass
class _GrabInfo:
    """Tracks which issue or pack a download belongs to.

    ``issue_id`` peut être None : mode « manual grab différé » — l'issue
    n'existe pas encore et sera créée par le pipeline metadata pendant
    l'import à partir des valeurs finales du parser + IA + OCR + arbiter.

    ``release_title`` : titre du release tel que retourné par l'indexer
    au moment du grab. Propagé au IssueFile à l'import pour que la Fiche
    technique montre d'où vient le fichier — le nom du fichier physique
    est renommé selon le naming template, le release_title garde la
    provenance originale (« Le.Monde.Du.25.08.2026.FR.[PDF]-NoTag »).
    """
    issue_id: int | None
    magazine_id: int
    pack_id: int | None = None
    release_title: str | None = None


# download_id → list[GrabInfo] — populated at grab time, consumed at import time.
#
# Multi-target routing : un même torrent hash peut être demandé pour
# PLUSIEURS issues (arrive quand un tracker mappe N releases distincts
# → 1 seul magnet). L'import route intelligemment vers l'issue dont la
# publication_date match la date détectée par l'IA dans le PDF.
# Les autres candidates restent wanted → re-search ultérieur.
_grab_registry: dict[str, list[_GrabInfo]] = {}

# download_ids that have already been imported (prevents re-processing)
_processed_downloads: set[str] = set()

# Downloads currently being imported (post-download pipeline in flight).
# Used to dedupe : le monitor scheduler tick toutes les 30 s, mais un
# import complet (parse + IA text + vision + arbiter + copy + cover)
# peut prendre 60-180 s. Sans ce guard, un 2ᵉ / 3ᵉ import démarre en
# parallèle → race SQLite lock storm → AI enrichment se plante en
# `database is locked` → fallback parser → fichier renommé sans les
# métadonnées enrichies. Cleared à la fin (success OR failure) du
# process_downloaded_file.
_in_flight_downloads: set[str] = set()

# Same idea pour la dispatch des packs — l'analyse IA prend plusieurs
# minutes et bloque un tick de monitor. Sans ce garde, chaque tick suivant
# relançait TOUTE la dispatch (extract + IA sur N fichiers) →
# activités zombies "0% Analyse 1/32" empilées, Ollama saturé.
_pack_dispatch_in_flight: set[str] = set()

# Track whether the registry has been loaded from disk
_registry_loaded: bool = False

# Track consecutive import failures per download_id (avoids warning spam)
_import_fail_count: dict[str, int] = {}

# Maximum consecutive import failures before giving up on a download
MAX_IMPORT_FAILURES = 10


def _get_registry_path() -> Path:
    """Get the path for the persistent grab registry file."""
    global _GRAB_REGISTRY_PATH
    if _GRAB_REGISTRY_PATH is None:
        from app.dependencies import get_config
        config = get_config()
        _GRAB_REGISTRY_PATH = config.config_path.parent / "grab_registry.json"
    return _GRAB_REGISTRY_PATH


def _get_processed_path() -> Path:
    """Get the path for the persistent processed-downloads file."""
    return _get_registry_path().with_name("processed_downloads.json")


def _get_fail_count_path() -> Path:
    """Get the path for the persistent import fail count file."""
    return _get_registry_path().with_name("import_fail_counts.json")


def _save_registry() -> None:
    """Persist grab registry and processed set to disk.

    Format persistant : `{download_id: [GrabInfo, ...]}` (multi-target).
    Le loader tolère aussi l'ancien format `{download_id: GrabInfo}` pour
    rétrocompat (auto-promotion en liste 1-élément).
    """
    try:
        path = _get_registry_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        data = {
            k: [asdict(g) for g in lst]
            for k, lst in _grab_registry.items()
        }
        path.write_text(json.dumps(data, indent=2))
    except Exception:
        logger.warning("Could not save grab registry", exc_info=True)
    try:
        proc_path = _get_processed_path()
        proc_path.parent.mkdir(parents=True, exist_ok=True)
        proc_path.write_text(json.dumps(list(_processed_downloads)))
    except Exception:
        logger.warning("Could not save processed downloads", exc_info=True)
    try:
        fail_path = _get_fail_count_path()
        fail_path.parent.mkdir(parents=True, exist_ok=True)
        fail_path.write_text(json.dumps(_import_fail_count))
    except Exception:
        logger.warning("Could not save import fail counts", exc_info=True)


def _load_registry() -> None:
    """Load grab registry and processed set from disk on startup.

    Tolère 2 formats :
      - Legacy `{dl_id: {GrabInfo_dict}}` → promoted en liste 1-élément
      - New    `{dl_id: [{GrabInfo}, {GrabInfo}, …]}` → chargé tel quel
    """
    global _registry_loaded
    try:
        path = _get_registry_path()
        if path.exists():
            data = json.loads(path.read_text())
            for k, v in data.items():
                if k in _grab_registry:
                    continue
                if isinstance(v, list):
                    _grab_registry[k] = [_GrabInfo(**item) for item in v]
                elif isinstance(v, dict):
                    _grab_registry[k] = [_GrabInfo(**v)]  # legacy
            logger.info("Loaded %d entries from grab registry", len(data))
    except Exception:
        logger.warning("Could not load grab registry", exc_info=True)
    try:
        proc_path = _get_processed_path()
        if proc_path.exists():
            ids = json.loads(proc_path.read_text())
            _processed_downloads.update(ids)
            logger.info("Loaded %d processed download IDs", len(ids))
    except Exception:
        logger.warning("Could not load processed downloads", exc_info=True)
    try:
        fail_path = _get_fail_count_path()
        if fail_path.exists():
            counts = json.loads(fail_path.read_text())
            _import_fail_count.update(counts)
            logger.info("Loaded %d import fail counts", len(counts))
    except Exception:
        logger.warning("Could not load import fail counts", exc_info=True)
    _registry_loaded = True


def ensure_registry_loaded() -> None:
    """Ensure the grab/processed registries are loaded from disk.

    Safe to call multiple times — only loads once per process.
    """
    if not _registry_loaded:
        _load_registry()


def get_grab_info(download_id: str) -> _GrabInfo | None:
    """Look up grab metadata for a download. Renvoie la PREMIÈRE
    candidate (comportement legacy pré-multi-target)."""
    lst = _grab_registry.get(download_id) or []
    return lst[0] if lst else None


def get_all_grab_infos(download_id: str) -> list[_GrabInfo]:
    """Retourne toutes les candidates pour un download_id (multi-target)."""
    return list(_grab_registry.get(download_id) or [])


def _route_grab_by_date(
    download_id: str,
    ai_date,
    tolerance_days: int = 0,
) -> tuple["_GrabInfo | None", list["_GrabInfo"]]:
    """Multi-target routing — choisit la candidate dont l'issue
    publication_date match `ai_date` (± tolerance).

    Retourne `(best_grab, others)` où :
      - best_grab : la meilleure candidate ou None si aucune match
      - others : les autres candidates (à laisser wanted pour re-search)

    Nécessite d'aller lire les issues en DB → à faire côté caller.
    Cette fonction fait juste le filtre sur la LISTE, le caller passe
    déjà les dates comme un dict {issue_id: publication_date}.
    """
    # Implémentation dans _try_import_item_locked (a besoin de la DB).
    raise NotImplementedError("route via caller with DB access")


def _pop_all_grabs(download_id: str) -> list[_GrabInfo]:
    """Retire et retourne toutes les candidates d'un download_id."""
    return _grab_registry.pop(download_id, [])


def dismiss_download(download_id: str) -> None:
    """Mark a download as dismissed — hides it from the queue and monitor.

    Does NOT remove the torrent from the download client.
    """
    _processed_downloads.add(download_id)
    _grab_registry.pop(download_id, None)
    _save_registry()
    logger.info("Dismissed download %s from queue", download_id)


def is_dismissed(download_id: str) -> bool:
    """Check if a download has been dismissed or already processed."""
    return download_id in _processed_downloads


def find_download_ids_for_issue(issue_id: int) -> list[str]:
    """Reverse lookup: find all download_ids registered for a given issue.
    Recherche l'issue dans TOUTES les candidates de chaque download
    (multi-target)."""
    ensure_registry_loaded()
    return [
        did for did, lst in _grab_registry.items()
        if any(g.issue_id == issue_id for g in lst)
    ]


async def grab_release(
    db: AsyncSession,
    issue_id: int | None = None,
    download_url: str = "",
    title: str = "",
    protocol: str = "torrent",
    guid: str = "",
    match_score: float | None = None,
    match_details: str | None = None,
    magazine_id: int | None = None,
) -> GrabResponse:
    """Envoie une release au client de téléchargement + trace le grab.

    Deux modes selon les args :

    - **avec ``issue_id``** : mode classique — bind l'issue existante,
      passe son status à ``snatched``, journalise l'event.

    - **sans ``issue_id``, avec ``magazine_id``** : mode « manual grab
      différé » — l'issue n'existe pas encore. Le pipeline d'import
      (parser + IA + OCR + arbiter) créera l'issue avec les métadonnées
      finales. On enregistre juste le magazine_id dans grab_registry
      pour que le monitor de download sache où router le fichier.
    """
    issue = None
    resolved_magazine_id = magazine_id
    resolved_issue_number: int | None = None

    if issue_id is not None:
        # Get issue
        result = await db.execute(
            select(Issue)
            .options(selectinload(Issue.magazine))
            .where(Issue.id == issue_id)
        )
        issue = result.scalars().first()
        if not issue:
            return GrabResponse(issue_id=issue_id, message="Issue not found")
        resolved_magazine_id = issue.magazine_id
        resolved_issue_number = issue.number

    if resolved_magazine_id is None:
        return GrabResponse(
            issue_id=issue_id or 0,
            message="grab_release: neither issue_id nor magazine_id",
        )

    # Find appropriate download client
    client_record = await _select_client(db, protocol)
    if not client_record:
        return GrabResponse(
            issue_id=issue_id or 0,
            message=f"No {protocol} download client configured",
        )

    # Activité — visible dans la sidebar/queue dès le début du grab.
    # Auto-clean à la fin (mark_done) ou en erreur (mark_error).
    from app.services import activity_service as _asvc
    activity_id: int | None = None
    _activity_title = (f"Grab · {title}")[:200] if title else "Grab release"
    try:
        activity_id = await _asvc.create(
            kind="grab",
            title=_activity_title,
            subtitle=f"{protocol} · {client_record.name}",
            magazine_id=resolved_magazine_id,
            issue_id=issue.id if issue else None,
            payload={
                "title": title,
                "protocol": protocol,
                "download_client": client_record.name,
                "guid": guid,
            },
        )
        logger.info("Grab activity created id=%s title=%r", activity_id, _activity_title)
    except Exception:
        logger.warning("Activity mirror (grab) failed", exc_info=True)

    # Send to download client
    try:
        client = _instantiate_client(client_record)
        if protocol == "torrent":
            download_id = await client.add_torrent(download_url, category="pressarr")
        else:
            download_id = await client.add_nzb(download_url, category="pressarr")

        # Register grab for later import tracking (multi-target routing).
        # Si N grabs distincts convergent vers le MÊME download_id (cas
        # tracker qui mappe N releases → 1 magnet), on ACCUMULE toutes
        # les candidates dans la liste. Au moment de l'import, on route
        # vers la candidate dont l'issue.publication_date match la date
        # détectée par l'IA dans le PDF téléchargé. Les non-matchées
        # restent wanted → re-search ultérieur avec un hash différent.
        if download_id:
            # Clear processed/fail state so monitor_downloads() will pick it up
            # again (handles re-grabbing the same torrent that was already imported
            # or gave up on).
            if download_id in _processed_downloads:
                _processed_downloads.discard(download_id)
                logger.info(
                    "Cleared processed state for re-grabbed download %s",
                    download_id,
                )
            _import_fail_count.pop(download_id, None)

            new_grab = _GrabInfo(
                issue_id=issue.id if issue else None,
                magazine_id=resolved_magazine_id,
                release_title=title,
            )
            existing_list = _grab_registry.get(download_id) or []
            # Dedup : si un grab identique (même issue/mag/pack) est déjà
            # présent, on ne l'ajoute pas 2 fois. Utile pour les re-grabs
            # manuels que l'user relance après échec (activity boutons).
            already = any(
                g.issue_id == new_grab.issue_id
                and g.magazine_id == new_grab.magazine_id
                and g.pack_id == new_grab.pack_id
                for g in existing_list
            )
            if not already:
                existing_list.append(new_grab)
                _grab_registry[download_id] = existing_list
                _save_registry()

            if len(existing_list) > 1:
                logger.info(
                    "Multi-target grab: download_id=%s a maintenant %d "
                    "candidates (routing à l'import selon date IA du PDF)",
                    download_id, len(existing_list),
                )
            elif issue:
                logger.info(
                    "Registered grab: download_id=%s → issue_id=%d, magazine_id=%d",
                    download_id, issue.id, resolved_magazine_id,
                )
            else:
                logger.info(
                    "Registered deferred grab: download_id=%s → magazine_id=%d "
                    "(issue à créer post-import via metadata pipeline)",
                    download_id, resolved_magazine_id,
                )

        # Update issue status ONLY quand on a une issue à toucher.
        if issue is not None:
            # Clear forecast flag so generate_forecasts won't delete it
            # while the download is in progress
            issue.status = "snatched"
            issue.is_forecast = False
            await db.flush()

        # Record history event
        await create_event(
            db,
            event_type="grab",
            magazine_id=resolved_magazine_id,
            issue_id=issue.id if issue else None,
            details=f"Grabbed: {title}",
            data={
                "release_title": title,
                "protocol": protocol,
                "download_id": download_id,
                "download_client": client_record.name,
                "guid": guid,
                "magazine_title": (
                    issue.magazine.title if (issue and issue.magazine) else None
                ),
                "issue_number": resolved_issue_number,
                "deferred_issue": issue is None,
                **({"match_score": round(match_score, 1)} if match_score is not None else {}),
                **({"match_details": match_details} if match_details else {}),
            },
        )

        # Invalidate smart matcher pattern cache so new grabs inform future matches
        from app.services.smart_matcher import invalidate_pattern_cache

        invalidate_pattern_cache(resolved_magazine_id)

        if activity_id is not None:
            try:
                await _asvc.update_meta(
                    activity_id,
                    payload_patch={
                        "download_id": download_id,
                        "message": f"Envoyé à {client_record.name}",
                    },
                )
                await _asvc.mark_done(
                    activity_id,
                    hint=f"Envoyé à {client_record.name} (download_id={download_id})",
                )
            except Exception:
                logger.debug("Activity finalize (grab done) failed", exc_info=True)

        return GrabResponse(
            issue_id=issue_id or 0,
            download_id=download_id,
            message=f"Sent to {client_record.name}",
        )
    except Exception as e:
        logger.error("Failed to grab release: %s", e, exc_info=True)
        if activity_id is not None:
            try:
                await _asvc.mark_error(activity_id, str(e))
            except Exception:
                pass
        return GrabResponse(issue_id=issue_id or 0, message=f"Grab failed: {e}")


async def grab_pack_release(
    db: AsyncSession,
    pack_id: int,
    download_url: str,
    title: str,
    protocol: str,
    guid: str,
) -> dict:
    """Send a pack torrent to the download client.

    Similar to grab_release() but for packs (no issue/magazine association).
    The pack_id is stored in _GrabInfo so _process_completed_item() can
    detect it and route to pack dispatch instead of single-file import.
    """
    client_record = await _select_client(db, protocol)
    if not client_record:
        return {"pack_id": pack_id, "message": f"No {protocol} download client configured"}

    from app.services import activity_service as _asvc
    activity_id: int | None = None
    _pg_title = (f"Pack grab · {title}")[:200] if title else "Pack grab"
    try:
        activity_id = await _asvc.create(
            kind="pack_grab",
            title=_pg_title,
            subtitle=f"{protocol} · {client_record.name}",
            payload={
                "pack_id": pack_id,
                "title": title,
                "protocol": protocol,
                "download_client": client_record.name,
                "guid": guid,
            },
        )
        logger.info(
            "Pack grab activity created id=%s pack_id=%d title=%r",
            activity_id, pack_id, _pg_title,
        )
    except Exception:
        logger.warning("Activity mirror (pack_grab) failed", exc_info=True)

    try:
        client = _instantiate_client(client_record)
        if protocol == "torrent":
            download_id = await client.add_torrent(download_url, category="pressarr")
        else:
            download_id = await client.add_nzb(download_url, category="pressarr")

        if download_id:
            if download_id in _processed_downloads:
                _processed_downloads.discard(download_id)
            _import_fail_count.pop(download_id, None)

            new_grab = _GrabInfo(
                issue_id=0,
                magazine_id=0,
                pack_id=pack_id,
                release_title=title,
            )
            existing_list = _grab_registry.get(download_id) or []
            already = any(g.pack_id == pack_id for g in existing_list)
            if not already:
                existing_list.append(new_grab)
                _grab_registry[download_id] = existing_list
                _save_registry()
            logger.info(
                "Registered pack grab: download_id=%s → pack_id=%d "
                "(candidates=%d)",
                download_id, pack_id, len(existing_list),
            )

        await create_event(
            db,
            event_type="grab",
            pack_id=pack_id,
            details=f"Grabbed pack: {title}",
            data={
                "release_title": title,
                "protocol": protocol,
                "download_id": download_id,
                "download_client": client_record.name,
                "guid": guid,
                "pack_id": pack_id,
            },
        )

        if activity_id is not None:
            try:
                await _asvc.update_meta(
                    activity_id,
                    payload_patch={"download_id": download_id},
                )
                await _asvc.mark_done(
                    activity_id,
                    hint=f"Envoyé à {client_record.name} — attend fin téléchargement puis dispatch",
                )
                logger.info(
                    "Pack grab activity id=%s marked done (download_id=%s)",
                    activity_id, download_id,
                )
            except Exception:
                logger.warning(
                    "Activity finalize (pack_grab done) failed", exc_info=True,
                )

        return {
            "pack_id": pack_id,
            "download_id": download_id,
            "message": f"Sent to {client_record.name}",
        }
    except Exception as e:
        logger.error("Failed to grab pack release: %s", e, exc_info=True)
        if activity_id is not None:
            try:
                await _asvc.mark_error(activity_id, str(e))
            except Exception:
                logger.warning(
                    "Activity finalize (pack_grab error) failed", exc_info=True,
                )
        return {"pack_id": pack_id, "message": f"Grab failed: {e}"}


async def _select_client(db: AsyncSession, protocol: str) -> DownloadClient | None:
    # Tri : d'abord `is_default` (True gagne), puis priority asc, puis id asc
    # pour un fallback déterministe. Sans le tri sur `is_default`, deux
    # clients à priority égale (cas typique après setup UI où le user coche
    # « Default » sur le nouveau mais oublie de baisser la priority de
    # l'ancien) tombent en ordre indéfini → le grab se retrouve routé au
    # hasard. Ex. observé : Deluge (isDefault=false, priority=1) choisi
    # à la place de qBittorrent (isDefault=true, priority=1) → timeout.
    result = await db.execute(
        select(DownloadClient).where(
            DownloadClient.protocol == protocol,
        ).order_by(
            DownloadClient.is_default.desc(),
            DownloadClient.priority.asc(),
            DownloadClient.id.asc(),
        )
    )
    return result.scalars().first()


def _instantiate_client(record: DownloadClient):
    """Instantiate a download client from the DB record.

    The DownloadClient model stores connection details as individual columns:
    host, port, use_ssl, username, password, api_key.
    """
    client_type = record.client_type.lower()

    if client_type == "deluge":
        from app.download_clients.deluge import DelugeClient
        return DelugeClient(
            host=record.host,
            port=record.port,
            password=record.password or "",
            use_ssl=record.use_ssl,
        )
    elif client_type == "qbittorrent":
        from app.download_clients.qbittorrent import QBittorrentClient
        return QBittorrentClient(
            host=record.host,
            port=record.port,
            username=record.username or "admin",
            password=record.password or "",
            use_ssl=record.use_ssl,
        )
    elif client_type == "transmission":
        from app.download_clients.transmission import TransmissionClient
        return TransmissionClient(
            host=record.host,
            port=record.port,
            username=record.username,
            password=record.password,
            use_ssl=record.use_ssl,
        )
    elif client_type == "sabnzbd":
        from app.download_clients.sabnzbd import SABnzbdClient
        return SABnzbdClient(
            host=record.host,
            port=record.port,
            api_key=record.api_key or "",
            use_ssl=record.use_ssl,
        )
    elif client_type == "nzbget":
        from app.download_clients.nzbget import NZBGetClient
        return NZBGetClient(
            host=record.host,
            port=record.port,
            username=record.username or "nzbget",
            password=record.password or "",
            use_ssl=record.use_ssl,
        )
    else:
        raise ValueError(f"Unknown client type: {client_type}")


def _instantiate_client_from_dict(cfg: dict):
    """Instantiate a download client from an eagerly-loaded config dict.

    Used by monitor_downloads and trigger_import to avoid lazy-loading
    ORM attributes after a session rollback (MissingGreenlet).
    """
    client_type = cfg["client_type"].lower()

    if client_type == "deluge":
        from app.download_clients.deluge import DelugeClient
        return DelugeClient(
            host=cfg["host"], port=cfg["port"],
            password=cfg["password"] or "", use_ssl=cfg["use_ssl"],
        )
    elif client_type == "qbittorrent":
        from app.download_clients.qbittorrent import QBittorrentClient
        return QBittorrentClient(
            host=cfg["host"], port=cfg["port"],
            username=cfg["username"] or "admin",
            password=cfg["password"] or "", use_ssl=cfg["use_ssl"],
        )
    elif client_type == "transmission":
        from app.download_clients.transmission import TransmissionClient
        return TransmissionClient(
            host=cfg["host"], port=cfg["port"],
            username=cfg["username"], password=cfg["password"],
            use_ssl=cfg["use_ssl"],
        )
    elif client_type == "sabnzbd":
        from app.download_clients.sabnzbd import SABnzbdClient
        return SABnzbdClient(
            host=cfg["host"], port=cfg["port"],
            api_key=cfg["api_key"] or "", use_ssl=cfg["use_ssl"],
        )
    elif client_type == "nzbget":
        from app.download_clients.nzbget import NZBGetClient
        return NZBGetClient(
            host=cfg["host"], port=cfg["port"],
            username=cfg["username"] or "nzbget",
            password=cfg["password"] or "", use_ssl=cfg["use_ssl"],
        )
    else:
        raise ValueError(f"Unknown client type: {client_type}")


def _apply_path_mapping(path_str: str, remote_path: str | None, local_path: str | None) -> str:
    """Apply remote→local path mapping (like Radarr/Sonarr Remote Path Mapping).

    If the download client reports save_path=/data/complete and the mapping is
    remote=/data/complete → local=/downloads, the result is /downloads.
    """
    if not remote_path or not local_path:
        return path_str
    # Normalize: ensure trailing slash for prefix matching
    remote = remote_path.rstrip("/") + "/"
    if path_str.startswith(remote) or path_str.rstrip("/") + "/" == remote:
        mapped = path_str.replace(remote_path.rstrip("/"), local_path.rstrip("/"), 1)
        logger.info("Path mapping: %s → %s", path_str, mapped)
        return mapped
    return path_str


def _resolve_save_path(item, remote_path: str | None = None, local_path: str | None = None) -> Path | None:
    """Resolve the exact file/folder path for a torrent item.

    Strict mode: returns ONLY base_path/torrent_name.
    No fallback, no directory scanning. If the exact path doesn't exist,
    returns None so the caller reports an error.
    """
    mapped_save_path = _apply_path_mapping(item.save_path, remote_path, local_path)
    base_path = Path(mapped_save_path)
    torrent_name = item.name if item.name else None

    if not torrent_name:
        logger.warning("No torrent name provided, cannot resolve path")
        return None

    torrent_path = base_path / torrent_name
    if torrent_path.exists():
        return torrent_path

    logger.warning(
        "Torrent file not found at exact path: %s "
        "(base=%s, name=%s). Check volume mounts and Remote Path Mapping.",
        torrent_path, base_path, torrent_name,
    )
    return None


def _collect_importable_files(save_path: Path) -> list[Path]:
    """Return the torrent file(s) to import.

    - If save_path is a supported file → return it directly.
    - If save_path is a directory (multi-file torrent) → return only
      the supported files inside that specific torrent folder.
    """
    supported = {".pdf", ".epub", ".cbr", ".cbz"}
    if save_path.is_file():
        if save_path.suffix.lower() in supported:
            return [save_path]
        return []
    if save_path.is_dir():
        return [f for f in save_path.rglob("*") if f.is_file() and f.suffix.lower() in supported]
    return []


async def _mirror_download_to_activity(item, cfg: dict) -> None:
    """Miroir de l'état torrent → Activity DB (kind=download).

    Créé la première fois qu'un torrent est vu par le monitor.
    Update la progression à chaque tick. mark_done quand le torrent
    passe en completed (l'import prend le relais avec sa propre
    activity kind=import). Dédup via external_id=download_id — le
    même torrent qu'on croise 100 fois n'est pas 100 rows.
    """
    from app.services import activity_service as _asvc

    download_id = item.download_id
    if not download_id:
        return

    grab_list = _grab_registry.get(download_id) or []
    grab = grab_list[0] if grab_list else None  # activity attachée à 1ère candidate
    aid = await _asvc.create(
        kind="download",
        title=item.name or "Torrent",
        subtitle=f"{cfg['name']} · {item.status}",
        magazine_id=(grab.magazine_id if grab and grab.magazine_id else None),
        issue_id=(grab.issue_id if grab and grab.issue_id else None),
        external_id=download_id,
        payload={
            "download_id": download_id,
            "download_client": cfg["name"],
            "protocol": "torrent",
            "size": item.size,
        },
    )

    # Cas terminal — le torrent est fini. mark_done, l'import prendra
    # la suite avec sa propre activity.
    if item.status == "completed":
        try:
            await _asvc.mark_done(
                aid, hint=f"{item.name} — attend import"
            )
        except Exception:
            logger.debug("mark_done download failed", exc_info=True)
        return

    if item.status in ("failed", "error"):
        try:
            await _asvc.mark_error(aid, f"status={item.status}")
        except Exception:
            pass
        return

    # En cours — update progress + status_message.
    try:
        progress_pct = float(item.progress or 0.0) * 100
        speed_kb = int((item.speed or 0) / 1024)
        eta_s = int(item.eta or 0)
        eta_str = ""
        if eta_s > 0 and eta_s < 86400 * 30:
            if eta_s > 3600:
                eta_str = f" · ETA {eta_s // 3600}h{(eta_s % 3600) // 60:02d}"
            else:
                eta_str = f" · ETA {eta_s // 60}m{eta_s % 60:02d}s"
        await _asvc.update_progress(
            aid,
            progress_pct,
            status_message=f"{item.status} — {speed_kb} KB/s{eta_str}",
        )
    except Exception:
        logger.debug("update_progress download failed", exc_info=True)


async def monitor_downloads(db: AsyncSession) -> None:
    """Poll all download clients, detect completed downloads, trigger import."""
    # Ensure grab registry + processed set are loaded from disk
    ensure_registry_loaded()

    result = await db.execute(select(DownloadClient))
    clients = result.scalars().all()

    # Eagerly read all client attributes to avoid lazy-loading after rollback
    client_configs = [
        {
            "name": cr.name,
            "client_type": cr.client_type,
            "host": cr.host,
            "port": cr.port,
            "use_ssl": cr.use_ssl,
            "username": cr.username,
            "password": cr.password,
            "api_key": cr.api_key,
            "category": cr.category,
            "remote_path": cr.remote_path,
            "local_path": cr.local_path,
        }
        for cr in clients
    ]

    for cfg in client_configs:
        try:
            client = _instantiate_client_from_dict(cfg)
            items = await client.get_all(category=cfg["category"])

            # Collect download_ids seen from get_all so we know which
            # grab_registry entries were NOT returned (label missing, etc.)
            seen_download_ids: set[str] = set()

            for item in items:
                if item.download_id:
                    seen_download_ids.add(item.download_id)
                # Miroir vers Activity DB — chaque torrent actif est
                # tracké dans /activity avec sa progression live. Sinon
                # entre le grab et l'import, l'utilisateur ne voit rien.
                if item.download_id and item.download_id not in _processed_downloads:
                    try:
                        await _mirror_download_to_activity(item, cfg)
                    except Exception:
                        logger.debug("mirror download failed", exc_info=True)

                # Skip already-processed/dismissed downloads entirely
                if item.download_id and item.download_id in _processed_downloads:
                    continue
                logger.debug(
                    "Monitor: %s status=%s save_path=%s name=%s",
                    item.download_id, item.status, item.save_path, item.name,
                )
                if item.status == "completed" and item.save_path:
                    await _process_completed_item(db, item, cfg)

            # Fallback: check grab_registry entries not returned by get_all.
            # This handles cases where the Label plugin is not available or
            # the label was not applied to the torrent.
            for download_id, _grab_list in list(_grab_registry.items()):
                if download_id in seen_download_ids:
                    continue
                if download_id in _processed_downloads:
                    continue
                try:
                    item = await client.get_status(download_id)
                    if not item:
                        continue
                    logger.info(
                        "Monitor (fallback): %s status=%s save_path=%s name=%s",
                        item.download_id, item.status, item.save_path, item.name,
                    )
                    if item.status == "completed" and item.save_path:
                        await _process_completed_item(db, item, cfg)
                except Exception:
                    logger.debug(
                        "Monitor: fallback check failed for %s", download_id, exc_info=True,
                    )

        except Exception:
            logger.warning(
                "Monitor error for %s", cfg["name"], exc_info=True
            )


async def _process_completed_item(db: AsyncSession, item, cfg: dict) -> None:
    """Process a single completed download item (import + commit)."""
    # Check if this download belongs to a pack.
    # `_grab_registry.get()` renvoie maintenant `list[_GrabInfo]`
    # (multi-target). Un pack a toujours 1 seule GrabInfo par download_id
    # (les packs sont uniques par nature), donc on prend la 1ère de la liste.
    grab_list = _grab_registry.get(item.download_id) if item.download_id else None
    first_grab = grab_list[0] if grab_list else None
    if first_grab and first_grab.pack_id:
        await _process_pack_download(db, item, first_grab, cfg)
        return

    try:
        import_result = await _try_import_item(
            db, item,
            remote_path=cfg["remote_path"],
            local_path=cfg["local_path"],
        )
        # Commit after each successful import to isolate DB state
        if import_result.get("success"):
            await db.commit()
            # Broadcast WebSocket update so frontend refreshes
            try:
                from app.api.v1.websocket import manager as ws_manager
                await ws_manager.broadcast(
                    "library:updated",
                    {"magazineId": import_result.get("magazine_id")},
                )
            except Exception:
                logger.debug("WebSocket broadcast failed", exc_info=True)
    except Exception:
        logger.warning(
            "Monitor: import failed for %s", item.download_id, exc_info=True
        )
        try:
            await db.rollback()
        except Exception:
            pass


async def _process_pack_download(
    db: AsyncSession, item, grab: _GrabInfo, cfg: dict
) -> None:
    """Process a completed pack download via the new pack_dispatch_service.

    L'ancien flux (preview_dispatch + dispatch_files + broadcast WS) est
    remplacé par un pipeline unique qui :
      - extrait les archives (zip/rar/7z/tar) le cas échéant,
      - crée une row ``pack_dispatch_file`` par fichier,
      - lance l'IA (deep par défaut, shallow si toggle OFF),
      - décide seul si auto-import possible, sinon laisse en pending_user.

    Le frontend ne reçoit plus un modal éphémère — il retrouve tout
    dans l'onglet Dispatch du pack (persistant), avec badge count des
    pending_user.

    **Anti-double-fire** : l'analyse IA prend plusieurs minutes (jusqu'à
    30 min sur 32 fichiers). Pendant ce temps, le monitor scheduler
    ticke toutes les 30-60 s et retrouve le download toujours "completed"
    dans le client. Sans garde, chaque tick relançait TOUTE la dispatch
    → activités zombies, IA en boucle, DB thrashing. On combine :
      1. ``_pack_dispatch_in_flight`` : set en mémoire — early-return
         si un dispatch est déjà en cours pour ce download_id.
      2. ``_processed_downloads.add`` AVANT l'analyse — ne serait-ce
         que pour dire au monitor "n'y retourne pas", même en cas de
         crash du process (l'entrée reste au reboot via _save_registry).
    """
    from app.database import async_session_factory
    from app.dependencies import get_config
    from app.services.pack_dispatch_service import process_pack_download

    pack_id = grab.pack_id
    download_id = item.download_id or ""

    if download_id in _pack_dispatch_in_flight:
        logger.debug(
            "Monitor: pack dispatch already in-flight for %s — skip",
            download_id,
        )
        return

    logger.info(
        "Monitor: pack download %s → pack_dispatch_service (pack_id=%d)",
        download_id, pack_id,
    )

    save_path = _resolve_save_path(
        item, remote_path=cfg["remote_path"], local_path=cfg["local_path"]
    )
    if not save_path:
        logger.warning("Monitor: pack download path not found for %s", download_id)
        return

    # Marque processed AVANT l'analyse pour bloquer les prochains ticks.
    # Si l'analyse crash / hang, une action manuelle sera nécessaire
    # (delete _processed_downloads.json + restart), mais c'est bien
    # mieux que 6 dispatchs zombies qui saturent Ollama.
    if download_id:
        _pack_dispatch_in_flight.add(download_id)
        _processed_downloads.add(download_id)
        _save_registry()

    try:
        stats = await process_pack_download(
            db,
            pack_id=pack_id,
            download_id=download_id,
            save_path=save_path,
            config=get_config(),
            session_factory=async_session_factory,
        )
    except Exception:
        logger.exception("Monitor: pack dispatch failed for pack_id=%d", pack_id)
        return
    finally:
        _pack_dispatch_in_flight.discard(download_id)

    # History event pour trace
    try:
        await create_event(
            db,
            event_type="import",
            pack_id=pack_id,
            details=(
                f"Pack dispatch: {stats['auto_imported']}/{stats['files']} "
                f"auto-importés · {stats['pending_user']} en attente"
            ),
            data={
                "pack_id": pack_id,
                "download_id": download_id,
                **stats,
            },
        )
        await db.commit()
    except Exception:
        logger.warning("history event pack dispatch failed", exc_info=True)

    try:
        from app.api.v1.websocket import manager as ws_manager
        await ws_manager.broadcast(
            "pack:dispatch_ready",
            {"packId": pack_id, "downloadId": download_id, **stats},
        )
        await ws_manager.broadcast("library:updated", {})
    except Exception:
        pass

    # Retire de la grab_registry (déjà processed marqué au début).
    if download_id:
        _grab_registry.pop(download_id, None)
        _import_fail_count.pop(item.download_id, None)
        _save_registry()


async def _try_import_item(
    db: AsyncSession,
    item,
    force: bool = False,
    remote_path: str | None = None,
    local_path: str | None = None,
    override_issue_id: int | None = None,
    override_magazine_id: int | None = None,
) -> dict:
    """Try to import a completed download item. Returns import result dict."""
    from app.dependencies import get_config
    from app.services.import_service import process_downloaded_file

    # Skip already-processed downloads (unless forced)
    if not force and item.download_id and item.download_id in _processed_downloads:
        logger.debug("Skipping already-processed download %s", item.download_id)
        return {"success": False, "message": "Already processed"}

    # Dedup : un import déjà en cours pour ce download → skip pour
    # ne pas lancer 2 pipelines en parallèle sur le même fichier
    # (SQLite lock storm + fichiers copiés 2× + doublons issues).
    if item.download_id and item.download_id in _in_flight_downloads:
        logger.debug(
            "Skipping in-flight download %s (already being imported)",
            item.download_id,
        )
        return {"success": False, "message": "Import already in flight"}
    if item.download_id:
        _in_flight_downloads.add(item.download_id)
    try:
        return await _try_import_item_locked(
            db, item, force=force,
            remote_path=remote_path, local_path=local_path,
            override_issue_id=override_issue_id,
            override_magazine_id=override_magazine_id,
        )
    finally:
        if item.download_id:
            _in_flight_downloads.discard(item.download_id)


async def _try_import_item_locked(
    db: AsyncSession,
    item,
    force: bool = False,
    remote_path: str | None = None,
    local_path: str | None = None,
    override_issue_id: int | None = None,
    override_magazine_id: int | None = None,
) -> dict:
    """Actual import logic — always executes inside the in-flight lock
    guarantee provided by ``_try_import_item``."""
    from app.dependencies import get_config
    from app.services.import_service import process_downloaded_file

    config = get_config()
    save_path = _resolve_save_path(item, remote_path=remote_path, local_path=local_path)

    logger.info(
        "Monitor: completed download %s — resolved_path=%s, name=%s, "
        "original_save_path=%s, remote_path=%s, local_path=%s",
        item.download_id, save_path, item.name,
        item.save_path, remote_path, local_path,
    )

    # Resolve grab info for history events — 1ère candidate suffit
    # (le routing intelligent multi-target se fait dans process_downloaded_file).
    _grab_hist_list = _grab_registry.get(item.download_id) if item.download_id else None
    grab = _grab_hist_list[0] if _grab_hist_list else None
    hist_magazine_id = override_magazine_id or (grab.magazine_id if grab else None)
    hist_issue_id = override_issue_id or (grab.issue_id if grab else None)

    if not save_path:
        # Track consecutive failures — log WARNING only the first few times,
        # then switch to DEBUG to avoid spamming the log every 30 seconds.
        fail_count = _import_fail_count.get(item.download_id, 0) + 1
        _import_fail_count[item.download_id] = fail_count
        _save_registry()
        if fail_count >= MAX_IMPORT_FAILURES:
            logger.warning(
                "Monitor: giving up on download %s after %d failed path resolutions. "
                "Check volume mounts or Remote Path Mapping.",
                item.download_id, fail_count,
            )
            mapped = _apply_path_mapping(item.save_path, remote_path, local_path)
            expected = f"{mapped}/{item.name}" if item.name else mapped
            await create_event(
                db, "error",
                magazine_id=hist_magazine_id,
                issue_id=hist_issue_id,
                details=f"Import failed: file not accessible after {fail_count} attempts",
                data={
                    "error": "path_not_found",
                    "download_id": item.download_id,
                    "download_name": item.name,
                    "expected_path": expected,
                    "remote_path": remote_path,
                    "local_path": local_path,
                    "attempts": fail_count,
                },
            )
            _processed_downloads.add(item.download_id)
            _import_fail_count.pop(item.download_id, None)
            _save_registry()
            return {"success": False, "message": f"Gave up after {fail_count} path resolution failures"}
        log_fn = logger.warning if fail_count <= 3 else logger.debug
        log_fn(
            "Monitor: path %s (+ name=%s) does not exist in container! "
            "Check volume mounts or Remote Path Mapping. "
            "Deluge save_path=%s, remote_path=%s, local_path=%s (attempt #%d)",
            item.save_path, item.name, item.save_path, remote_path, local_path,
            fail_count,
        )
        mapped = _apply_path_mapping(item.save_path, remote_path, local_path)
        expected = f"{mapped}/{item.name}" if item.name else mapped
        return {
            "success": False,
            "message": (
                f"File not found: {expected} "
                f"(remote_path={remote_path!r}, local_path={local_path!r})"
            ),
        }

    files = _collect_importable_files(save_path)
    logger.info("Monitor: found %d importable files: %s", len(files), [f.name for f in files])

    if not files:
        logger.warning("Monitor: no supported files found in %s", save_path)
        await create_event(
            db, "error",
            magazine_id=hist_magazine_id,
            issue_id=hist_issue_id,
            details="Import failed: no supported files in download",
            data={
                "error": "no_supported_files",
                "download_id": item.download_id,
                "download_name": item.name,
                "path": str(save_path),
            },
        )
        # Mark as processed so we don't retry every 30 seconds
        if item.download_id:
            _processed_downloads.add(item.download_id)
            _save_registry()
        return {"success": False, "message": f"No supported files in {save_path}"}

    # Resolve issue/magazine association:
    # 1. Override params (from queue item metadata) take priority
    # 2. Then grab registry (from grab time)
    # 3. Fallback: filename parsing in process_downloaded_file
    issue_id = override_issue_id
    magazine_id = override_magazine_id
    grab_release_title: str | None = None
    grab_pack_id: int | None = None

    # Multi-target routing : le registry peut contenir PLUSIEURS
    # candidates pour ce download_id (cas tracker qui mappe N releases
    # → 1 magnet). On passe TOUTES les candidates à process_downloaded_file
    # qui décidera de la routing selon la date détectée par l'IA vision.
    grab_candidates: list[_GrabInfo] = []
    if item.download_id:
        grab_candidates = list(_grab_registry.get(item.download_id) or [])

    if not issue_id and grab_candidates:
        # Défaut : la 1ère candidate (comportement legacy quand 1 seule).
        # L'import re-décide dynamiquement si multi-target.
        first = grab_candidates[0]
        issue_id = first.issue_id
        magazine_id = first.magazine_id
        grab_release_title = first.release_title
        grab_pack_id = first.pack_id
    elif grab_candidates:
        # Override queue_item : on garde son issue_id, récupère juste
        # release_title/pack_id depuis la 1ère candidate.
        first = grab_candidates[0]
        grab_release_title = first.release_title
        grab_pack_id = first.pack_id

    if len(grab_candidates) > 1:
        logger.info(
            "Monitor: multi-target grab (%d candidates) pour download %s — "
            "routing selon date IA au moment de l'import",
            len(grab_candidates), item.download_id,
        )
    elif issue_id:
        logger.info(
            "Monitor: issue association — issue_id=%d, magazine_id=%s (source=%s)",
            issue_id, magazine_id,
            "queue_item" if override_issue_id else "grab_registry",
        )
    else:
        logger.info("Monitor: no issue association, will use filename parsing")

    # Multi-target : sérialise les candidates pour que process_downloaded_file
    # puisse re-router selon la date IA. Format transmis :
    # `[{issue_id, magazine_id, release_title}, …]`.
    grab_candidates_serialized: list[dict] | None = None
    if len(grab_candidates) > 1:
        grab_candidates_serialized = [
            {
                "issue_id": g.issue_id,
                "magazine_id": g.magazine_id,
                "release_title": g.release_title,
                "pack_id": g.pack_id,
            }
            for g in grab_candidates
        ]

    imported_any = False
    last_result = {}
    for f in files:
        result_info = await process_downloaded_file(
            db, f, config,
            magazine_id=magazine_id,
            issue_id=issue_id,
            source_type=("pack" if grab_pack_id else "torrent"),
            source_pack_id=grab_pack_id,
            source_release_title=grab_release_title,
            grab_candidates=grab_candidates_serialized,
        )
        logger.info(
            "Monitor: import result for %s: %s",
            f.name, result_info,
        )
        last_result = result_info
        if result_info.get("success"):
            imported_any = True

    # Rejets DÉFINITIFS — un retry n'aidera JAMAIS. Le fichier
    # physique ne va pas changer. Chaque retry re-tourne l'IA vision
    # (~7 min) pour rien.
    #
    # Cas :
    #   « Not a quality upgrade »   = déjà importé même qualité
    #   « Rejected: content title » = contamination magazine (L'Équipe
    #                                  dans Le Monde)
    #   « Rejected: content date »  = contamination date (30/31 dans
    #                                  issue 27/08)
    #
    # Marquer processed immédiatement pour arrêter le loop de retries
    # toutes les 30 s.
    _last_msg = str(last_result.get("message") or "")
    if not imported_any and item.download_id and (
        _last_msg == "Not a quality upgrade"
        or _last_msg.startswith("Rejected:")
    ):
        reason_label = (
            "already imported at same quality"
            if _last_msg == "Not a quality upgrade"
            else "content contamination detected"
        )
        logger.info(
            "Monitor: %s — %s, marking processed (no retry)",
            item.download_id, reason_label,
        )
        _processed_downloads.add(item.download_id)
        _import_fail_count.pop(item.download_id, None)
        _grab_registry.pop(item.download_id, None)
        _save_registry()
        if magazine_id:
            last_result["magazine_id"] = magazine_id
        return last_result

    # Track business-logic failures (e.g. "not a quality upgrade")
    if not imported_any and item.download_id:
        fail_count = _import_fail_count.get(item.download_id, 0) + 1
        _import_fail_count[item.download_id] = fail_count
        _save_registry()
        if fail_count >= MAX_IMPORT_FAILURES:
            logger.warning(
                "Monitor: giving up on download %s after %d failed import attempts: %s",
                item.download_id, fail_count, last_result.get("message", "unknown"),
            )
            await create_event(
                db, "error",
                magazine_id=hist_magazine_id,
                issue_id=hist_issue_id,
                details=f"Import failed: {last_result.get('message', 'unknown reason')}",
                data={
                    "error": "import_failed",
                    "download_id": item.download_id,
                    "download_name": item.name,
                    "reason": last_result.get("message", "unknown"),
                    "attempts": fail_count,
                },
            )
            _processed_downloads.add(item.download_id)
            _import_fail_count.pop(item.download_id, None)
            _save_registry()

    # Mark as processed and clean up registry
    # (download stays in client for seeding / user management)
    if imported_any and item.download_id:
        # Multi-target : le fichier physique unique de ce hash a été
        # importé sur UNE issue. Les AUTRES candidates du registry
        # (issues de la même liste, non satisfaites) doivent être
        # remises en `wanted` — un futur search cherchera un release
        # avec un hash DIFFÉRENT pour elles.
        satisfied_issue_id = last_result.get("issue_id")
        candidates = list(_grab_registry.get(item.download_id) or [])
        unsatisfied_issue_ids = [
            g.issue_id for g in candidates
            if g.issue_id is not None and g.issue_id != satisfied_issue_id
        ]
        if unsatisfied_issue_ids:
            from sqlalchemy import update as _update
            from app.models.issue import Issue as _Issue
            try:
                await db.execute(
                    _update(_Issue)
                    .where(
                        _Issue.id.in_(unsatisfied_issue_ids),
                        _Issue.status == "snatched",
                    )
                    .values(status="wanted")
                )
                await db.commit()
                logger.info(
                    "Multi-target : %d candidate(s) non satisfaite(s) "
                    "(issue_ids %s) remises en wanted pour re-search",
                    len(unsatisfied_issue_ids), unsatisfied_issue_ids,
                )
            except Exception:  # noqa: BLE001
                logger.warning(
                    "reset des candidates non satisfaites échoué",
                    exc_info=True,
                )

        _processed_downloads.add(item.download_id)
        _grab_registry.pop(item.download_id, None)
        _import_fail_count.pop(item.download_id, None)
        _save_registry()

    # Always include magazine_id in result for WebSocket broadcast
    if magazine_id:
        last_result["magazine_id"] = magazine_id

    return last_result


async def trigger_import(
    db: AsyncSession,
    download_id: str,
    issue_id: int | None = None,
    magazine_id: int | None = None,
) -> dict:
    """Manually trigger import for a specific download by its ID.

    When issue_id/magazine_id are provided (from the queue item metadata),
    they take priority over the grab registry lookup.
    """
    # Load all clients upfront to avoid lazy-loading issues after rollback
    result = await db.execute(select(DownloadClient))
    clients = list(result.scalars().all())
    # Eagerly read all attributes we need before any potential rollback
    client_configs = [
        {
            "name": cr.name,
            "client_type": cr.client_type,
            "host": cr.host,
            "port": cr.port,
            "use_ssl": cr.use_ssl,
            "username": cr.username,
            "password": cr.password,
            "api_key": cr.api_key,
            "remote_path": cr.remote_path,
            "local_path": cr.local_path,
        }
        for cr in clients
    ]

    for cfg in client_configs:
        try:
            client = _instantiate_client_from_dict(cfg)
            status = await client.get_status(download_id)
            if status and status.save_path:
                # Rollback any failed transaction before attempting import
                try:
                    await db.rollback()
                except Exception:
                    pass
                return await _try_import_item(
                    db, status, force=True,
                    remote_path=cfg["remote_path"],
                    local_path=cfg["local_path"],
                    override_issue_id=issue_id,
                    override_magazine_id=magazine_id,
                )
        except Exception:
            logger.warning(
                "trigger_import error for %s", cfg["name"], exc_info=True
            )
            # Ensure session is usable for next iteration
            try:
                await db.rollback()
            except Exception:
                pass

    return {"success": False, "message": f"Download {download_id} not found in any client"}


async def _resolve_download_path(db: AsyncSession, download_id: str) -> Path | None:
    """Resolve the filesystem path for a download by its ID.

    Queries all configured download clients to find the download and return
    its resolved save path. Used by pack dispatch endpoints.
    """
    result = await db.execute(select(DownloadClient))
    clients = result.scalars().all()
    client_configs = [
        {
            "client_type": cr.client_type,
            "host": cr.host,
            "port": cr.port,
            "use_ssl": cr.use_ssl,
            "username": cr.username,
            "password": cr.password,
            "api_key": cr.api_key,
            "remote_path": cr.remote_path,
            "local_path": cr.local_path,
        }
        for cr in clients
    ]

    for cfg in client_configs:
        try:
            client = _instantiate_client_from_dict(cfg)
            status = await client.get_status(download_id)
            if status and status.save_path:
                return _resolve_save_path(
                    status,
                    remote_path=cfg["remote_path"],
                    local_path=cfg["local_path"],
                )
        except Exception:
            logger.debug("_resolve_download_path: error for client", exc_info=True)

    return None


async def cleanup_orphaned_snatched(db: AsyncSession) -> int:
    """Reset issues stuck in 'snatched' for >48h with no active download.

    Returns the number of issues reset to 'wanted'.
    """
    from datetime import UTC, datetime, timedelta

    from app.models.history import History

    ensure_registry_loaded()
    cutoff = datetime.now(UTC) - timedelta(hours=48)

    # Find all snatched + monitored issues
    result = await db.execute(
        select(Issue).where(
            Issue.status == "snatched",
            Issue.monitored == True,  # noqa: E712
        )
    )
    snatched_issues = list(result.scalars().all())
    if not snatched_issues:
        return 0

    # Collect all active download_ids from clients
    client_result = await db.execute(select(DownloadClient))
    clients = client_result.scalars().all()
    active_download_ids: set[str] = set()

    for cr in clients:
        try:
            client = _instantiate_client(cr)
            items = await client.get_all(category=cr.category)
            for item in items:
                if item.download_id:
                    active_download_ids.add(item.download_id)
        except Exception:
            logger.debug("cleanup: failed to poll %s", cr.name, exc_info=True)

    reset_count = 0
    for issue in snatched_issues:
        download_ids = find_download_ids_for_issue(issue.id)
        has_active = any(did in active_download_ids for did in download_ids)
        has_registry = len(download_ids) > 0

        if not has_active and not has_registry:
            # No record at all — orphaned
            issue.status = "wanted"
            reset_count += 1
            logger.info(
                "Reset orphaned snatched issue id=%d (no registry entry) to wanted",
                issue.id,
            )
        elif has_registry and not has_active:
            # Registry entry exists but download gone from client — check age
            grab_event = (await db.execute(
                select(History).where(
                    History.issue_id == issue.id,
                    History.event_type == "grab",
                ).order_by(History.date.desc()).limit(1)
            )).scalars().first()
            grab_date = grab_event.date if grab_event else None
            if grab_date and hasattr(grab_date, "tzinfo") and grab_date.tzinfo is None:
                grab_date = grab_date.replace(tzinfo=UTC)
            if not grab_event or (grab_date and grab_date < cutoff):
                issue.status = "wanted"
                for did in download_ids:
                    _grab_registry.pop(did, None)
                _save_registry()
                reset_count += 1
                logger.info(
                    "Reset orphaned snatched issue id=%d (grab >48h, download gone) to wanted",
                    issue.id,
                )

    if reset_count:
        await db.flush()

    return reset_count
