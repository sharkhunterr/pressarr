# GitHub Releases - Pressarr

> Release notes for GitHub releases

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
