"""SQLAlchemy ORM models."""

from app.models.magazine import Magazine
from app.models.issue import Issue
from app.models.issue_file import IssueFile
from app.models.quality_profile import QualityProfile, QualityProfileItem
from app.models.download_client import DownloadClient
from app.models.notification import Notification
from app.models.history import History
from app.models.blocklist import Blocklist
from app.models.root_folder import RootFolder
from app.models.indexer_config import IndexerConfig
from app.models.metadata_cache import MetadataCache

__all__ = [
    "Magazine", "Issue", "IssueFile",
    "QualityProfile", "QualityProfileItem",
    "DownloadClient", "Notification",
    "History", "Blocklist",
    "RootFolder", "IndexerConfig", "MetadataCache",
]
