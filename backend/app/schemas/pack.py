"""Pack Pydantic schemas."""

from datetime import datetime

from app.schemas import CamelModel


class PackPatternResource(CamelModel):
    id: int
    pack_id: int
    pattern: str
    source: str | None = None
    uploader: str | None = None
    last_seen_at: datetime
    created_at: datetime


class PackPatternCreateResource(CamelModel):
    pattern: str
    source: str | None = None
    uploader: str | None = None


class PackRuleResource(CamelModel):
    id: int
    pack_id: int
    rule_type: str
    pattern: str


class PackRuleCreateResource(CamelModel):
    rule_type: str
    pattern: str


class PackStatistics(CamelModel):
    pattern_count: int = 0
    rule_count: int = 0
    total_grabs: int = 0
    last_grab_date: datetime | None = None


class PackResource(CamelModel):
    id: int
    name: str
    name_slug: str
    description: str | None = None
    search_query: str
    recurrence: str
    auto_search: bool
    auto_grab: bool
    auto_import: bool
    deep_ai_analysis: bool = True
    auto_create_missing_magazines: bool = False
    preview_before_import: bool = False
    default_new_magazine_frequency: str = "weekly"
    monitored: bool
    quality_profile_id: int
    root_folder_id: int
    added_at: datetime
    last_searched_at: datetime | None = None
    patterns: list[PackPatternResource] = []
    rules: list[PackRuleResource] = []
    statistics: PackStatistics = PackStatistics()


class PackCreateResource(CamelModel):
    name: str
    description: str | None = None
    search_query: str
    recurrence: str = "none"
    auto_search: bool = False
    auto_grab: bool = False
    auto_import: bool = False
    deep_ai_analysis: bool = True
    auto_create_missing_magazines: bool = False
    preview_before_import: bool = False
    default_new_magazine_frequency: str = "weekly"
    monitored: bool = True
    quality_profile_id: int
    root_folder_id: int


class PackUpdateResource(CamelModel):
    name: str | None = None
    description: str | None = None
    search_query: str | None = None
    recurrence: str | None = None
    auto_search: bool | None = None
    auto_grab: bool | None = None
    auto_import: bool | None = None
    deep_ai_analysis: bool | None = None
    auto_create_missing_magazines: bool | None = None
    preview_before_import: bool | None = None
    default_new_magazine_frequency: str | None = None
    monitored: bool | None = None
    quality_profile_id: int | None = None
    root_folder_id: int | None = None


class PackDispatchFileResource(CamelModel):
    """Fichier extrait d'un pack, analysé par le pipeline IA.

    Contient l'analyse (extracted_metadata), le match auto (magazine +
    score + source), les propositions (proposed_magazine_data) et
    l'action user (user_action)."""
    id: int
    pack_id: int
    download_id: str
    filename: str
    path: str
    size: int = 0
    status: str  # pending_analysis | analyzed | pending_user | imported | ignored | error
    error_message: str | None = None
    ai_run_id: int | None = None
    extracted_metadata: dict | None = None
    matched_magazine_id: int | None = None
    matched_magazine_title: str | None = None
    match_score: float | None = None
    match_source: str | None = None
    # confirmed | doubt | rejected | None (pas encore évalué)
    confidence: str | None = None
    proposed_magazine_data: dict | None = None
    user_action: str | None = None
    user_action_magazine_id: int | None = None
    resolved_issue_id: int | None = None
    created_at: datetime
    analyzed_at: datetime | None = None
    resolved_at: datetime | None = None


class PackDispatchResolveRequest(CamelModel):
    """Décision utilisateur pour un fichier pending_user."""
    action: str  # assign_existing | create_magazine | ignore
    magazine_id: int | None = None
    magazine_data: dict | None = None
    # Metadata éditées manuellement avant résolution — override le
    # extracted_metadata de l'analyse IA. Utile quand l'IA a mal
    # détecté (ex. date erronée). Champs supportés : title, issue_number,
    # year, month, day, issn.
    metadata_overrides: dict | None = None


class PackDispatchMetadataUpdate(CamelModel):
    """Édition manuelle des metadata extraites d'un fichier de dispatch.
    Merge shallow — seuls les champs fournis sont écrasés."""
    title: str | None = None
    issue_number: int | None = None
    year: int | None = None
    month: int | None = None
    day: int | None = None
    issn: str | None = None
