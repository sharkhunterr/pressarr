# Pressarr Docker Deployment

**Automated magazine collection manager - Complete deployment guide**

This guide covers Docker deployment of Pressarr. For Docker Hub overview, see [DOCKERHUB.md](DOCKERHUB.md).

---

## Quick Start

### Option 1: Docker Compose (Recommended)

```bash
# Download docker-compose.yml
curl -o docker-compose.yml https://raw.githubusercontent.com/sharkhunterr/pressarr/main/docker/docker-compose.yml

# Start Pressarr
docker compose up -d

# View logs
docker compose logs -f pressarr
```

**Access**: http://localhost:8585

### Option 2: Docker Run

```bash
docker run -d \
  --name pressarr \
  -p 8585:8585 \
  -v $(pwd)/config:/config \
  -v $(pwd)/magazines:/magazines \
  -v $(pwd)/downloads:/downloads \
  -e TZ=Europe/Paris \
  --restart unless-stopped \
  sharkhunterr/pressarr:latest
```

---

## What's in the Image

The unified Pressarr image includes:

| Component | Description | Port |
|-----------|-------------|------|
| **Web UI** | React frontend (served as static) | 8585 |
| **API** | FastAPI backend | 8585 |
| **Database** | SQLite | - |

**Platforms**: `linux/amd64`, `linux/arm64`

---

## Configuration

### Docker Compose Example

```yaml
services:
  pressarr:
    image: sharkhunterr/pressarr:latest
    container_name: pressarr
    hostname: pressarr
    ports:
      - "8585:8585"
    volumes:
      - ./config:/config
      - ./magazines:/magazines
      - ./downloads:/downloads
    environment:
      - TZ=Europe/Paris
      - PRESSARR__LOG_LEVEL=info
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8585/api/v1/system/status"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 30s
```

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `PRESSARR__PORT` | `8585` | Server port |
| `PRESSARR__LOG_LEVEL` | `info` | Log level (debug, info, warning, error) |
| `PRESSARR__DB_PATH` | `/config/pressarr.db` | SQLite database path |
| `PRESSARR__CONFIG_PATH` | `/config/pressarr.yml` | YAML config path |
| `TZ` | `UTC` | Container timezone |

---

## Backup & Restore

### Via Volume

```bash
# Backup
docker run --rm \
  -v $(pwd)/config:/data \
  -v $(pwd):/backup \
  alpine tar czf /backup/pressarr-$(date +%Y%m%d).tar.gz -C /data .

# Restore
docker run --rm \
  -v $(pwd)/config:/data \
  -v $(pwd):/backup \
  alpine sh -c "cd /data && tar xzf /backup/pressarr-YYYYMMDD.tar.gz"
```

---

## Updates

```bash
# Pull latest image
docker compose pull

# Recreate container
docker compose up -d

# Clean old images
docker image prune -f
```

### Version Pinning

```yaml
services:
  pressarr:
    image: sharkhunterr/pressarr:v0.1.0  # Pin to specific version
```

---

## Development Setup

### Docker Compose Dev

```bash
# Start development environment with hot-reload
docker compose -f docker/docker-compose.dev.yml up

# Backend: http://localhost:8585 (with auto-reload)
# Frontend: http://localhost:5173 (Vite dev server)
# Adminer: http://localhost:8080 (database viewer)
```

### Build from Source

```bash
# Build the image
docker compose -f docker/docker-compose.yml build

# Or use the root Dockerfile
docker build -t pressarr:local .
```

---

## Troubleshooting

### Container Won't Start

Check logs: `docker compose logs pressarr`

Common issues:
- Port conflict: Change ports in compose file
- Permission: `chmod -R 755 ./config`
- Database locked: Stop all instances

### Services Can't Connect

**Mac/Windows**: Use `host.docker.internal` instead of `localhost`

**Linux**: Use your machine's IP (not `localhost`)

Test: `docker compose exec pressarr curl -I http://YOUR_SERVICE`

---

## Docker Files Overview

| File | Description |
|------|-------------|
| `Dockerfile` | Production multi-stage image (backend + frontend) |
| `backend.Dockerfile` | Backend-only production image |
| `backend.dev.Dockerfile` | Backend development with hot-reload |
| `frontend.Dockerfile` | Frontend-only production image (nginx) |
| `frontend.dev.Dockerfile` | Frontend development with Vite |
| `docker-compose.yml` | Production deployment |
| `docker-compose.dev.yml` | Development with hot-reload |
| `docker-compose.prod.yml` | Production with pre-built image |
| `docker-compose.unraid.yml` | Unraid-specific deployment |
| `nginx.conf` | Nginx reverse proxy configuration |
| `supervisord.conf` | Process supervisor for multi-process container |

---

## Resources

- **Docker Hub**: https://hub.docker.com/r/sharkhunterr/pressarr
- **GitHub**: https://github.com/sharkhunterr/pressarr

---

**Built with Docker for the *arr community**
