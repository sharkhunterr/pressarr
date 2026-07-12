"""Scene magazine indexers — HTML scrapers for sites that
publish PDF/EPUB magazine releases pointing at file-hoster
links (1fichier, Uploaded, Nitroflare, …).

Distinct from ``app.indexers.prowlarr`` (torznab / torrent
indexers) because the data model is incompatible: scene
magazines don't have ``.torrent`` URIs, they have N hoster
links per release. See ``base.MagazineSceneRelease`` for the
shared shape.
"""

from app.indexers.magazine_scene.base import (
    HosterLink,
    MagazineSceneIndexerBase,
    MagazineSceneRelease,
)

__all__ = [
    "HosterLink",
    "MagazineSceneIndexerBase",
    "MagazineSceneRelease",
]
