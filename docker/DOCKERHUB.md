# 📚 Pressarr - Magazine Collection Manager

[![GitHub](https://img.shields.io/github/v/tag/sharkhunterr/pressarr?label=version&color=7C3AED)](https://github.com/sharkhunterr/pressarr/releases)
[![Docker Pulls](https://img.shields.io/docker/pulls/sharkhunterr/pressarr?color=2496ED)](https://hub.docker.com/r/sharkhunterr/pressarr)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](https://github.com/sharkhunterr/pressarr/blob/main/LICENSE)

**Automated magazine collection manager for the *arr ecosystem** — Monitor, search, download, rename, and organize your periodical collection automatically.

---

## 🚀 Quick Start

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
    restart: unless-stopped
```

```bash
docker compose up -d
```

**Access**: http://localhost:8585

---

## ✨ Features

**📚 Magazine Library Management**
- Search & add magazines with cover art and metadata
- Completion statistics and quality profiles per title
- Batch monitoring and file renaming templates
- Multi-language filename parser (FR/EN/DE/ES/IT)

**🔮 Calendar Forecast**
- Frequency-based predictions for future issues
- Visual calendar with grid and agenda views
- Delayed issue detection with 6-month lookahead

**🔍 Search & Download**
- Prowlarr integration with multi-indexer support
- Quality-based scoring and auto-grab
- RSS sync every 30 minutes

**📥 Download Clients**
- Torrent: qBittorrent, Deluge, Transmission
- Usenet: SABnzbd, NZBGet
- Direct: Internet Archive

**🔔 Notifications**
- Discord, Gotify, Telegram, Webhook

**🖥️ Modern Interface**
- 2 languages (EN, FR)
- Light/Dark themes
- Real-time download progress via WebSocket

---

## ⚙️ Configuration

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `PRESSARR__PORT` | `8585` | Server port |
| `PRESSARR__LOG_LEVEL` | `info` | Log level |
| `PRESSARR__DB_PATH` | `/config/pressarr.db` | Database path |
| `PRESSARR__CONFIG_PATH` | `/config/pressarr.yml` | Config file path |
| `TZ` | `UTC` | Container timezone |

### Volumes

| Path | Description |
|------|-------------|
| `/config` | Database, YAML config, API key |
| `/magazines` | Organized magazine library |
| `/downloads` | Temporary download directory |

---

## 🏷️ Available Tags

| Tag | Description |
|-----|-------------|
| `latest` | Latest stable release |
| `v0.x.x` | Specific version |

```bash
docker pull sharkhunterr/pressarr:latest
```

---

## 🔄 Update

```bash
docker compose pull
docker compose up -d
docker image prune -f
```

---

## 🛠️ Technical Stack

| Layer | Technologies |
|-------|--------------|
| Backend | Python 3.12, FastAPI, SQLAlchemy 2.0, APScheduler |
| Frontend | React 18, TypeScript 5, Tailwind CSS, Vite |
| Data | SQLite (aiosqlite), WebSocket real-time |

**Platforms**: `linux/amd64`, `linux/arm64`

---

## 🔗 Links

- [📖 Documentation](https://github.com/sharkhunterr/pressarr#readme)
- [🐛 Report Issues](https://github.com/sharkhunterr/pressarr/issues)
- [⭐ Star on GitHub](https://github.com/sharkhunterr/pressarr)

---

## 📄 License

MIT License - [LICENSE](https://github.com/sharkhunterr/pressarr/blob/main/LICENSE)

---

<div align="center">

**Built with Claude Code 🤖 for the *arr community 📚**

</div>
