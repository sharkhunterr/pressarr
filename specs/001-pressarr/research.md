# Phase 0 Research: Pressarr

**Branch**: `001-pressarr` | **Date**: 2026-02-26 | **Plan**: [plan.md](plan.md)

---

## Topic 1: SQLAlchemy 2.0 Async with aiosqlite

### Decision

Use **SQLAlchemy 2.0** with `create_async_engine` and the **aiosqlite** driver. Connection string: `sqlite+aiosqlite:////config/pressarr.db`. Alembic async template (`alembic init -t async`). WAL mode via connection event listener. No ORM wrappers — use SQLAlchemy directly per Constitution Art. V.

### Rationale

- SQLAlchemy 2.0 is the only ORM supporting true async with SQLite via aiosqlite
- `Mapped[]` annotations provide full type safety (Art. IV §4.2)
- WAL mode enables concurrent reads without blocking writers
- aiosqlite is thread-based (fine for file-based SQLite — no socket to make non-blocking)

### Alternatives Considered

- **Tortoise ORM**: Less mature, smaller ecosystem, Django-style rather than SQL-expression-first
- **databases + encode/databases**: Lower level, no ORM, would require manual schema management
- **SQLModel**: Too tightly coupled, less control over async behavior

### Dependencies

```
sqlalchemy>=2.0,<2.1
aiosqlite>=0.20.0
alembic>=1.13
```

### Key Patterns

**Engine + Session Factory** (`backend/app/database.py`):

```python
engine = create_async_engine(
    "sqlite+aiosqlite:////config/pressarr.db",
    connect_args={"check_same_thread": False},
)

@event.listens_for(engine.sync_engine, "connect")
def set_sqlite_pragma(dbapi_connection, connection_record):
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.execute("PRAGMA busy_timeout=5000")
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()

async_session_factory = async_sessionmaker(engine, expire_on_commit=False)
```

**FastAPI Dependency** (`backend/app/dependencies.py`):

```python
async def get_db() -> AsyncSession:
    async with async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
```

**Alembic**: `alembic init -t async alembic` — uses `async_engine_from_config` + `connection.run_sync(do_run_migrations)`.

### Caveats

1. **`expire_on_commit=False` mandatory** — avoids `MissingGreenlet` on attribute access after commit
2. **WAL mode**: concurrent reads OK, writes still serialized — `busy_timeout=5000` prevents immediate "database is locked"
3. **`PRAGMA foreign_keys=ON`** must be set on every connection (off by default in SQLite)
4. **In-memory SQLite for tests**: `sqlite+aiosqlite://` with `StaticPool`
5. Docker: `/config` volume must include `-wal` and `-shm` sidecar files

---

## Topic 2: APScheduler with FastAPI

### Decision

Use **APScheduler 3.10+** (not 4.x) with `AsyncIOScheduler`. In-memory job store only — no `SQLAlchemyJobStore` (uses sync SQLAlchemy, conflicts with async engine). Jobs defined in code, re-registered on startup with `replace_existing=True`.

### Rationale

- APScheduler 3.x is stable and well-documented; 4.x has completely different API and is still pre-release
- In-memory store avoids sync/async SQLAlchemy conflicts
- All jobs are statically defined — no persistence needed
- Single uvicorn worker avoids duplicate job execution

### Alternatives Considered

- **APScheduler 4.x**: Unstable API, breaking changes, not production-ready
- **Celery + Redis**: Overkill for single-user app, adds infrastructure dependency
- **arq**: Less feature-complete, requires Redis
- **Huey**: Less async support

### Dependencies

```
APScheduler>=3.10,<4
```

### Key Patterns

**Lifespan integration** (`backend/app/main.py`):

```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    scheduler.add_job(rss_sync, IntervalTrigger(minutes=30),
                      id="rss_sync", replace_existing=True)
    scheduler.add_job(download_check, IntervalTrigger(seconds=30),
                      id="download_check", replace_existing=True)
    scheduler.add_job(history_cleanup, IntervalTrigger(hours=24),
                      id="history_cleanup", replace_existing=True)
    scheduler.start()
    yield
    scheduler.shutdown(wait=False)
```

**Job database access**: Jobs use `async_session_factory` directly (not `Depends(get_db)`) with their own try/except + rollback.

### Caveats

1. **`replace_existing=True`** essential to avoid duplicate-job errors on restart
2. **Single worker only** — multiple workers = duplicate job execution
3. **Jobs on event loop** — keep I/O-bound; use `asyncio.to_thread` for CPU-bound work
4. **APScheduler swallows exceptions** — every job must have explicit try/except with logging
5. **`shutdown(wait=False)`** for fast container exit on SIGTERM

---

## Topic 3: Google Books API for Magazines

### Decision

Use Google Books API as an **enrichment source** for magazine metadata (publisher, ISSN, description, cover images). NOT a primary source for issue discovery — the API has no issue enumeration endpoint.

### Rationale

- `printType=magazines` works to filter search results to periodicals
- Each magazine issue is a separate "volume" in Google Books — no parent-child relationship
- No endpoint to list all issues of a magazine title
- 1,000 requests/day quota (free tier) sufficient for enrichment, not for bulk discovery
- Good data: publisher, ISSN, description, publication date, cover images (thumbnail + small)

### Key API Patterns

**Search for magazine title**:
```
GET https://www.googleapis.com/books/v1/volumes?q=intitle:{title}&printType=magazines&maxResults=40&key={API_KEY}
```

**Search by ISSN**:
```
GET https://www.googleapis.com/books/v1/volumes?q=issn:{issn}&printType=magazines&key={API_KEY}
```

**Response fields** (per volume):
- `volumeInfo.title`, `volumeInfo.publisher`, `volumeInfo.publishedDate`
- `volumeInfo.description`, `volumeInfo.language`
- `volumeInfo.industryIdentifiers[]` — contains ISSN (type `ISSN`)
- `volumeInfo.imageLinks.thumbnail`, `volumeInfo.imageLinks.smallThumbnail`
- `volumeInfo.categories[]`

### Rate Limiting

- 1,000 requests/day (free tier), resets at midnight Pacific
- No per-second limit documented
- For Pressarr: batch metadata refreshes, cache aggressively (24h TTL)

### Integration Strategy

1. Used at magazine add time: search by title, get publisher/ISSN/description/cover
2. Periodic metadata refresh (configurable, default weekly)
3. NOT used for issue discovery — that comes from Prowlarr search + Internet Archive
4. Cache responses in `metadata_cache` table

---

## Topic 4: Internet Archive Magazine Rack

### Decision

Use Internet Archive's public APIs (Scrape API + Metadata API + Direct Download) as a primary source for both metadata and direct magazine acquisition. No authentication required. Rate limit: 1 req/sec.

### Rationale

- Magazine Rack collection (`magazine_rack`) contains 34,000+ digitized magazines
- No API key required for read-only operations
- Multiple file formats per item (PDF, EPUB, DjVu)
- Direct download — no external download client needed
- Cursor-based pagination for large result sets

### Key API Endpoints

| Purpose | Endpoint | Auth |
|---------|----------|------|
| Search (paginated) | `GET /services/search/v1/scrape?q=collection:magazine_rack+AND+title:({query})&fields=identifier,title,date,publisher,item_size&count=100` | No |
| Item metadata | `GET /metadata/{identifier}` | No |
| File download | `GET /download/{identifier}/{filename}` | No |
| Cover thumbnail | `GET /services/img/{identifier}` | No |

### Search Response

```json
{
  "items": [{
    "identifier": "NationalGeographic-2005-01",
    "title": "National Geographic January 2005",
    "date": "2005-01",
    "publisher": "National Geographic Partners",
    "item_size": 52428800
  }],
  "total": 342,
  "cursor": "W3siaWRlbnRpZmllciI6..."
}
```

### Metadata Response (key fields)

- `metadata.identifier`, `metadata.title`, `metadata.date`, `metadata.publisher`, `metadata.language`
- `files[].name`, `files[].format` ("Text PDF", "EPUB", "DjVu"), `files[].source` ("original" / "derivative"), `files[].size`

### File Format Priority

1. **PDF** (`Text PDF`) — most common, universal
2. **EPUB** — good for e-readers, smaller
3. **DjVu** — good compression, less universal

### Download Workflow

1. Fetch metadata: `GET /metadata/{identifier}`
2. Find best file: prefer `format: "Text PDF"` + `source: "original"`
3. Download: `GET /download/{identifier}/{file.name}` (follow redirects)

### Rate Limiting

| Operation | Rate | Rationale |
|-----------|------|-----------|
| Search/metadata | 1 req/sec | Safe baseline matching CDX limit |
| Downloads | 1 concurrent | Bandwidth-limited naturally |
| Bulk scanning | 0.5 req/sec | Background tasks |

- HTTP `429` → exponential backoff (5s start, double up to 300s)
- IP blocked for 1 hour if `429` ignored for >1 minute; block duration doubles on repeat
- Use `X-Accept-Reduced-Priority` header for graceful degradation

---

## Topic 5: Prowlarr API Integration

### Decision

Use Prowlarr's `/api/v1/search` endpoint for interactive search and RSS sync. Authenticate via `X-Api-Key` header. Search categories 7010 (Mags) + 7020 (Ebooks) for maximum coverage. Grab via `POST /api/v1/search` with full search result payload.

### Rationale

- Prowlarr unifies Newznab (usenet) and Torznab (torrent) into a single JSON API
- The `protocol` field distinguishes usenet vs torrent for routing to correct download client
- Categories: **7010 = Books/Mags** (magazines), **7020 = Books/Ebook** (may contain magazines too)
- Constitution Art. II §2.4 mandates Prowlarr as primary indexer source

### Category Correction

The constitution specifies category `7020`, but per the Newznab standard:
- **7010** = Books/Mags (Magazines)
- **7020** = Books/Ebook

**Resolution**: Search BOTH categories `7010,7020` for maximum coverage. Some indexers categorize magazines under either.

### Key API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/api/v1/search?query={term}&categories=7010&categories=7020&type=search` | Search |
| `POST` | `/api/v1/search` | Grab a release |
| `POST` | `/api/v1/search/bulk` | Bulk grab |
| `GET` | `/api/v1/indexer` | List configured indexers |

### Search Response (per result)

```json
{
  "guid": "unique-id",
  "title": "National Geographic - February 2026 (True PDF)",
  "size": 52428800,
  "age": 5,
  "seeders": 15,
  "leechers": 3,
  "indexerId": 3,
  "indexer": "NZBgeek",
  "downloadUrl": "https://...",
  "protocol": "usenet",
  "categories": [{"id": 7010, "name": "Books/Mags"}],
  "publishDate": "2026-02-21T00:00:00Z",
  "infoHash": null
}
```

**Protocol differences**:

| Field | Usenet | Torrent |
|-------|--------|---------|
| `protocol` | `"usenet"` | `"torrent"` |
| `seeders/leechers` | `null` | Integer |
| `infoHash` | `null` | String |

### Grab Request

`POST /api/v1/search` with the full search result object as body. Key fields: `guid` + `indexerId`.

### RSS Sync Pattern

Pressarr implements its own RSS sync by calling:
```
GET /api/v1/search?query=&categories=7010&categories=7020&type=search
```
with empty query to get latest releases, on a configurable interval (default 30 min).

### Authentication

`X-Api-Key: {api_key}` header on all `/api/v1/` requests.

---

## Topic 6: Download Client APIs

### Decision

Implement abstract base class with concrete implementations for 5 clients: Deluge, qBittorrent, Transmission (torrent) + SABnzbd, NZBGet (usenet). All use the label/category `pressarr`.

### Rationale

- These are the standard clients in the *arr ecosystem
- Each has a well-documented API suitable for automated integration
- Common interface: add, check progress, detect completion, remove

### Comparison Table

| Feature | Deluge | qBittorrent | Transmission | SABnzbd | NZBGet |
|---------|--------|-------------|--------------|---------|--------|
| **API** | JSON-RPC | REST | JSON-RPC | REST (query params) | JSON-RPC |
| **Base URL** | `/json` (8112) | `/api/v2` (8080) | `/transmission/rpc` (9091) | `/api` (8080) | `/jsonrpc` (6789) |
| **Auth** | Password → cookie | User+pass → SID cookie | 409 challenge → session header | API key in URL | HTTP Basic |
| **Add** | `core.add_torrent_url` | `POST /torrents/add` | `torrent-add` | `mode=addurl` | `append` |
| **Category** | Label plugin | `category` param | `labels` array (v3.0+) | `cat` param | `Category` param |
| **Progress** | 0-100 float | 0.0-1.0 float | 0.0-1.0 float | 0-100 int | Computed |
| **Speed** | bytes/s | bytes/s | bytes/s | string "1.3 M" | bytes/s (global) |
| **Done** | `state=="Seeding"` | `progress==1.0` | `status==6` | Moves to history | Moves to history |
| **Remove** | `core.remove_torrent` | `POST /torrents/delete` | `torrent-remove` | `mode=queue&name=delete` | `editqueue("GroupDelete")` |

### Abstract Interface

```python
class DownloadClient(ABC):
    async def test_connection(self) -> bool: ...
    async def add_download(self, url: str, category: str) -> str: ...  # returns ID
    async def get_status(self, download_id: str) -> DownloadStatus: ...
    async def remove_download(self, download_id: str, delete_files: bool) -> bool: ...
```

**Normalized `DownloadStatus`**: id, name, status (enum: queued/downloading/paused/completed/failed), progress (0-100), speed (bytes/s), eta (seconds), size (bytes), output_path (after completion).

### Key Integration Notes

- **Deluge**: Label plugin must be enabled; need `web.connect` before `core.*` calls
- **qBittorrent**: Create category before first use; progress 0.0-1.0 (multiply by 100)
- **Transmission**: 409 challenge on first request; labels require v3.0+ (RPC v16)
- **SABnzbd**: Completion = item moves from queue to history; `storage` field gives final path
- **NZBGet**: Positional params only in JSON-RPC; progress must be computed; `DestDir` for final path

---

## Topic 7: PDF Cover Extraction & Fuzzy Matching

### Decision: PyMuPDF for Cover Extraction

Use **PyMuPDF** (`pymupdf`) for extracting cover images from PDF magazine files. Zero system dependencies, native JPEG output, pre-built wheels for amd64+arm64.

### Rationale

- No system packages needed (unlike pdf2image which requires `poppler-utils`)
- Native `tobytes("jpg")` — no Pillow dependency
- Built-in zoom/resize via Matrix
- Fastest renderer (C++ MuPDF engine)
- Works with `python:3.12-slim` Docker images

### Alternatives Considered

| Library | Verdict | Reason |
|---------|---------|--------|
| **pdf2image** | Eliminated | Requires `poppler-utils` system package |
| **pikepdf** | Eliminated | Cannot render pages to images |
| **pypdf** | Eliminated | Cannot render pages to images |

### Key Pattern

```python
async def extract_cover(pdf_path: Path, output_path: Path, max_width: int = 500) -> bool:
    """Extract first page as JPEG. Runs in thread executor (CPU-bound)."""
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, partial(_extract_sync, pdf_path, output_path, max_width))

def _extract_sync(pdf_path, output_path, max_width):
    doc = pymupdf.open(str(pdf_path))
    page = doc[0]
    zoom = min(1.0, max_width / page.rect.width)
    pix = page.get_pixmap(matrix=pymupdf.Matrix(zoom, zoom))
    output_path.write_bytes(pix.tobytes("jpg", jpg_quality=85))
    doc.close()
```

### Decision: rapidfuzz for Fuzzy Matching

Use **rapidfuzz** for fuzzy title matching. 10-50x faster than thefuzz, zero dependencies, `score_cutoff` for early termination.

### Key Pattern

```python
from rapidfuzz import fuzz, process

MATCH_THRESHOLD = 80  # FR-024: minimum 80% similarity

def normalize_title(title: str) -> str:
    """Normalize: accents, separators, articles, ampersand, case."""
    text = re.sub(r"[._\-]+", " ", title)
    text = unicodedata.normalize("NFD", text)
    text = "".join(c for c in text if unicodedata.category(c) != "Mn")
    text = text.replace("&", "et")
    text = re.sub(r"\b(le|la|les|the|a|an)\b", "", text, flags=re.IGNORECASE)
    return " ".join(text.lower().split())

def match_magazine_title(parsed_title: str, known_titles: list[str]) -> tuple[str, float] | None:
    result = process.extractOne(parsed_title, known_titles,
                                scorer=fuzz.WRatio, processor=normalize_title,
                                score_cutoff=MATCH_THRESHOLD)
    return (result[0], result[1]) if result else None
```

### Docker Impact

| Library | pip install | Size | ARM64 | Alpine |
|---------|------------|------|-------|--------|
| PyMuPDF | `PyMuPDF` | ~15-20MB | Yes | No (use slim) |
| rapidfuzz | `rapidfuzz` | ~2-3MB | Yes | Yes |

---

## Topic 8: Metadata Patterns (from Reading Glasses)

### Decision

Adopt **rreading-glasses**' pluggable provider interface, read-through caching, and async progressive loading patterns. Diverge by implementing multi-source aggregation instead of single-source-at-a-time.

### Context

[rreading-glasses](https://github.com/blampe/rreading-glasses) is the community replacement for Readarr's metadata service. It handles book metadata (not magazines), but its architecture solves the same problem: normalizing data from multiple upstream sources into a self-hosted media management application.

### Patterns to Adopt

#### 1. Abstract Metadata Provider Interface

rreading-glasses uses a `Getter` interface that abstracts all metadata sources. Pressarr adaptation:

```python
class MetadataProvider(ABC):
    async def search_magazine(self, query: str) -> list[MagazineSearchResult]: ...
    async def get_magazine(self, provider_id: str) -> MagazineMetadata | None: ...
    async def get_issues(self, provider_id: str) -> list[IssueMetadata]: ...
    async def get_cover(self, provider_id: str) -> str | None: ...
```

Implementations: `google_books.py`, `internet_archive.py` (in `backend/app/metadata/`).

#### 2. Multi-Source Aggregation (diverges from rreading-glasses)

rreading-glasses uses one-source-at-a-time. Pressarr needs simultaneous multi-source because:
- Google Books has structured metadata (ISSN, publisher, covers)
- Internet Archive has the actual files and Magazine Rack collection
- Spec requires aggregation + deduplication (US-001)

```python
class MetadataService:
    async def search(self, query: str) -> list[MagazineSearchResult]:
        tasks = [p.search_magazine(query) for p in self.providers]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        return self._merge_and_deduplicate(results)  # By normalized title + ISSN
```

#### 3. Read-Through Metadata Caching

Cache raw provider responses in SQLite (`metadata_cache` table with JSON blob + TTL). Benefits:
- No schema migrations when upstream APIs change
- Cache invalidation via TTL (re-fetch after expiry)
- Normalized data in main `magazine`/`issue` tables

#### 4. Async Progressive Loading

When a user adds a magazine:
1. Return immediately with available metadata
2. Spawn background task to fetch full issue lists from all providers
3. Update UI via WebSocket as data arrives
4. Matches spec requirement for fast search results

#### 5. Cover Image Priority

Unlike rreading-glasses (URL-only), Pressarr needs local storage:
1. **Local extracted cover** (PDF first page via PyMuPDF) — highest priority
2. **Provider cover** (Google Books thumbnail, IA cover) — fallback
3. **Placeholder** with magazine title — last resort

#### 6. Data Model Mapping

| rreading-glasses | Pressarr | Notes |
|-----------------|----------|-------|
| Work | Magazine | Abstract concept of a periodical title |
| Edition | Issue | Specific numbered instance |
| Author | Publisher | Magazine's "author" is its publisher |
| ISBN-13 | ISSN | Standard serial identifier |

### Patterns NOT to Adopt

- **Postgres**: SQLite is correct for Pressarr (Art. VI §6.4)
- **Single-source model**: Pressarr needs multi-source aggregation
- **GraphQL clients**: Google Books and IA use REST
- **Goodreads/Hardcover**: Zero magazine content

---

## Summary Table

| Topic | Decision | Key Dependency | Docker Impact |
|-------|----------|---------------|---------------|
| Database | SQLAlchemy 2.0 async + aiosqlite + WAL | `sqlalchemy`, `aiosqlite`, `alembic` | /config volume |
| Scheduler | APScheduler 3.10+ in-memory store | `APScheduler` | Single worker |
| Google Books | Enrichment source (not issue discovery) | `httpx` | None |
| Internet Archive | Primary acquisition + metadata, 1 req/sec | `httpx` | None |
| Prowlarr | Categories 7010+7020, X-Api-Key header | `httpx` | None |
| Download Clients | 5 clients, abstract interface, `pressarr` label | `httpx` | None |
| Cover Extraction | PyMuPDF, `run_in_executor` for async | `PyMuPDF` | ~15-20MB wheel |
| Fuzzy Matching | rapidfuzz, 80% threshold, WRatio scorer | `rapidfuzz` | ~2-3MB wheel |
| Metadata Patterns | rreading-glasses: abstract provider + multi-source aggregation + cache + progressive load | — | — |

---

## Sources

### SQLAlchemy & APScheduler
- [SQLAlchemy 2.0 Async Documentation](https://docs.sqlalchemy.org/en/20/orm/extensions/asyncio.html)
- [aiosqlite on PyPI](https://pypi.org/project/aiosqlite/)
- [Alembic Async Template](https://github.com/sqlalchemy/alembic/blob/main/alembic/templates/async/env.py)
- [APScheduler 3.x User Guide](https://apscheduler.readthedocs.io/en/3.x/userguide.html)
- [SQLite WAL Mode](https://sqlite.org/wal.html)

### Google Books
- [Google Books API Documentation](https://developers.google.com/books/docs/v1/using)
- [Google Books Volume Resource](https://developers.google.com/books/docs/v1/reference/volumes)

### Internet Archive
- [Internet Archive Developer Portal](https://archive.org/developers/index-apis.html)
- [Item Metadata API](https://archive.org/developers/md-read.html)
- [The Magazine Rack Collection](https://archive.org/details/magazine_rack)
- [IA Rate Limiting Blog Post](https://blog.archive.org/2023/05/29/let-us-serve-you-but-dont-bring-us-down/)

### Prowlarr
- [Prowlarr API Docs](https://prowlarr.com/docs/api/)
- [Prowlarr Search Wiki](https://wiki.servarr.com/prowlarr/search)
- [Newznab API Categories](https://inhies.github.io/Newznab-API/categories/)
- [golift/starr Go Package](https://pkg.go.dev/golift.io/starr/prowlarr)

### Download Clients
- [Deluge Web JSON-RPC API](https://deluge.readthedocs.io/en/latest/reference/webapi.html)
- [qBittorrent WebUI API](https://github.com/qbittorrent/qBittorrent/wiki/WebUI-API-(qBittorrent-5.0))
- [Transmission RPC Spec](https://github.com/transmission/transmission/blob/main/docs/rpc-spec.md)
- [SABnzbd API Reference](https://sabnzbd.org/wiki/configuration/4.5/api)
- [NZBGet API Reference](https://nzbget.net/api/)

### PDF & Fuzzy Matching
- [PyMuPDF Documentation](https://pymupdf.readthedocs.io/en/latest/)
- [RapidFuzz GitHub](https://github.com/rapidfuzz/RapidFuzz)

### Metadata Patterns
- [blampe/rreading-glasses](https://github.com/blampe/rreading-glasses)
- [rreading-glasses Go Package](https://pkg.go.dev/github.com/blampe/rreading-glasses)
- [Readarr Retired - Servarr Wiki](https://wiki.servarr.com/readarr)
