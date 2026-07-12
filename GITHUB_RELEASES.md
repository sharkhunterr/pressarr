# GitHub Releases - Pressarr

> Release notes for GitHub releases. The first `# vX.Y.Z` block is
> consumed by the release CI as the description posted to GitLab and
> GitHub. Edit this file BEFORE running `npm run release:full`.

---

# v0.2.0

## 📚 Magazine pipeline — ISSN cascade + scene grab + JDownloader 2

Full end-to-end magazine acquisition path : **discover** via an
ISSN-first metadata cascade, **grab** from scene indexers with a
Cloudflare-aware scraper, **download** through JDownloader 2, and
**import** back into your library — all automated with a
subscription vs one-shot flow.

> [!IMPORTANT]
> This release adds a new **FlareSolverr** dependency and expects a
> **JDownloader 2** container reachable from Pressarr. See
> `docker-compose` snippet below. Existing magazines are back-filled
> with the cascade at boot on first run; no migration needed but
> reserve a couple of minutes for the enrichment sweep.

---

### 🔎 ISSN-first metadata cascade

Metadata now flows through a proper cascade instead of a single
provider :

- **ZDB** (Zeitschriftendatenbank) — German serials authority.
- **Wikidata** — logos (P154 prioritised over P18), frequency
  (P2241 / P31), related publications, first-issued / ceased dates.
- **BnF** — French press authority via MARC 326 frequency field.
- **ISSN Portal** — canonical ISSN-L propagation.
- **Cross-reference** hits across providers via Wikidata identity
  with soft timeouts so a slow provider can't stall the cascade.

Every source is orchestrated with a **rank-first + canonical boost**
so real magazines rise above IA catalogue noise, and results without
an ISSN are dropped below verified ones. Multi-ISSN sibling lists
(print + online + CD-ROM) surface on the identity payload.

**Auto back-fill** : the cascade runs on every `POST /magazine` and
on boot for existing rows, so nothing has to be re-added by hand.

### 🎯 Scene indexers with Cloudflare bypass

Two new scrapers ship with proper release tables :

- **Bookys** — FlareSolverr-backed for Cloudflare bypass.
- **telecharger-magazines.org** — rewritten for the WordPress +
  liens-direct flow, with a friendlier error message when Cloudflare
  reports an origin outage.

Every scene grab produces a normalized release row (magazine +
issue + edition) and a full **history event** so you can audit what
was grabbed, when, and by which flow (manual / auto / RSS).

### ⏰ Auto-grab scheduler

- **Subscription vs one-shot** request type on the Magazine model.
- Subscription runs a periodic scan honouring your indexer set and
  quality profile ; one-shot fires once and stops.
- **Immediate back-catalogue grab** on add : when you subscribe to
  a title, Pressarr immediately searches the last N issues instead
  of waiting for the next scheduled tick.

### 🖥️ JDownloader 2 integration

Pressarr can now drive **JDownloader 2** directly for hosters that
need `.crawljob` file drops :

- **Dispatcher** writes one hoster URL per `.crawljob` (not all
  mirrors) so JD2 doesn't reject the payload.
- **downloadFolder** is the JD2-side path (container view), not
  Pressarr's — the folder-watch works out-of-the-box.
- **Booleans lowercased** in `.crawljob` and the hoster priority
  list demotes `frdl.io`.
- **Queue UI** — inspect + manage the JD2 queue directly from
  Pressarr : cancel, retry, prioritise.

### 📥 Scene importer

- Watches JD2's output folder → moves files into the library with
  the correct rename template.
- Flips the release status (`grabbed` → `imported`).
- Emits history events at every step (scene grab / auto-grab /
  import) so the timeline in the UI matches reality.

### 🎨 UI

- **MagazinePipelineSection** on the Magazine detail page shows the
  full grab / download / import status with a **Re-grab button**
  when the scene release is already present.
- **Queue page** merged all sources into a single list with
  **source badges** (no more tabs).
- **Settings → Indexers** absorbed the scene-magazine config into
  a single page.
- Magazine detail exposes `coverIsLogo`, multi-ISSN filter, full
  ISSN-L sibling list, publication status chip.

### 🐛 Fixes

- Scene query normalisation for tricky titles.
- Wikidata related-publications lookups parallelised + cascade
  timeout bumped so slow queries don't fail the whole flow.
- Magazine ranking : catalogue noise without ISSN pushed below real
  magazines.
- BnF frequency + verified-only filter.

---

### 📦 New runtime dependencies

Update your compose file :

```yaml
services:
  flaresolverr:
    image: ghcr.io/flaresolverr/flaresolverr:latest
    environment:
      - LOG_LEVEL=info
    restart: unless-stopped
    ports:
      - "8191:8191"

  jdownloader2:
    image: jaymoulin/jdownloader:latest
    volumes:
      - ./jd2-config:/opt/JDownloader/cfg
      - /path/to/downloads:/opt/JDownloader/Downloads
    restart: unless-stopped

  pressarr:
    environment:
      - PRESSARR_FLARESOLVERR_URL=http://flaresolverr:8191
      - PRESSARR_JD2_URL=http://jdownloader2:3129
      - PRESSARR_JD2_FOLDERWATCH=/opt/JDownloader/cfg/folderwatch
```

Point Pressarr's `.crawljob` output at the JD2 folderwatch path
(default `/opt/JDownloader/cfg/folderwatch`, mounted read-write on
both sides).

---

# v0.1.0

## 📚 Pressarr v0.1.0 - Initial Release

First public release of Pressarr, the automated magazine collection manager for the *arr ecosystem.

### ✨ What's New

**📚 Magazine Library Management**
- Search & add magazines with cover art and metadata
- Completion statistics and quality profiles per title
- Batch monitoring and file renaming templates
- Multi-language filename parser (FR/EN/DE/ES/IT)

**🔮 Calendar Forecast**
- Frequency-based predictions for future issues
- Visual calendar with grid and agenda views
- Confirmed vs predicted issues tracking
- Delayed issue detection with 6-month lookahead

**🔍 Search & Download Pipeline**
- Prowlarr integration with multi-indexer support
- Quality-based scoring and auto-grab best release
- RSS sync every 30 minutes
- Smart import with automatic renaming and organization

**📥 Download Clients**
- Torrent: qBittorrent, Deluge, Transmission
- Usenet: SABnzbd, NZBGet
- Direct: Internet Archive (no client needed)

**🔔 Notifications**
- Discord, Gotify, Telegram, Webhook
- Alerts on grab, download, import, and errors

**📂 Smart Import Pipeline**
- Automatic filename parsing (multilingual)
- Fuzzy title matching against known magazines
- Quality detection (TruePDF, Retail, Scan...)
- Cover extraction from PDF (first page)

**🏗️ Metadata Sources**
- Google Books API for magazine metadata
- Internet Archive Magazine Rack collection

**🖥️ Modern Web Interface**
- 2 languages (English, French)
- Dark theme support
- Fully responsive design
- Real-time download progress via WebSocket

### 🛠️ Technical Stack

| Layer | Technologies |
|-------|--------------|
| Backend | Python 3.12, FastAPI, SQLAlchemy 2.0, APScheduler |
| Frontend | React 18, TypeScript 5, Tailwind CSS, Vite |
| Data | SQLite (aiosqlite), WebSocket real-time |
| DevOps | Docker, GitLab CI/CD |

### 🐳 Docker Quick Start

```yaml
services:
  pressarr:
    image: sharkhunterr/pressarr:latest
    ports:
      - "8585:8585"
    volumes:
      - ./config:/config
      - ./magazines:/magazines
      - ./downloads:/downloads
    environment:
      - TZ=Europe/Paris
```

### 🔗 Links

- [🐳 Docker Hub](https://hub.docker.com/r/sharkhunterr/pressarr)
- [📖 Documentation](https://github.com/sharkhunterr/pressarr#readme)
- [🐛 Report Issues](https://github.com/sharkhunterr/pressarr/issues)

---

# Instructions

1. Go to https://github.com/sharkhunterr/pressarr/releases/new
2. **Tag**: Use the version tag
3. **Target**: `main`
4. **Title**: Copy the title from the version section
5. **Description**: Copy everything from `## 📚 Pressarr` to the end of the section
6. **Publish release**

> The script `npm run release:full` automatically takes the FIRST version section (the one at the top)
