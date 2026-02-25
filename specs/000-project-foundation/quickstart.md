# Quickstart: Project Foundation

**Feature**: 000-project-foundation
**Date**: 2026-02-25

## Prérequis

- Python 3.12+
- Node.js 20+
- Docker (optionnel, pour le build de l'image)

## Démarrage rapide (développement)

### 1. Backend

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Démarrer le serveur de développement
uvicorn app.main:app --reload --port 8585
```

### 2. Frontend

```bash
cd frontend
npm install

# Démarrer le serveur de développement Vite
npm run dev
```

Le frontend de développement tourne sur le port Vite (5173) et proxy les appels /api/* vers le backend (8585).

### 3. Vérification

```bash
# L'API de santé doit répondre
curl http://localhost:8585/api/v1/system/status

# Réponse attendue :
# {"version":"0.1.0","uptime":5,"startTime":"...","magazineCount":0,"issueCount":0,"issueFileCount":0}
```

## Build Docker

```bash
docker build -t pressarr:dev .

docker run -d \
  --name pressarr \
  -p 8585:8585 \
  -v ./config:/config \
  -v ./magazines:/magazines \
  -v ./downloads:/downloads \
  pressarr:dev
```

## Configuration

Le fichier `/config/pressarr.yml` est auto-généré au premier démarrage :

```yaml
server:
  port: 8585
  host: "0.0.0.0"

api_key: "auto-generated-32-hex-chars"

paths:
  config: "/config"
  magazines: "/magazines"
  downloads: "/downloads"

logging:
  level: "info"
```

Toute clé peut être surchargée par variable d'environnement :

```bash
PRESSARR__SERVER__PORT=9090       # → server.port = 9090
PRESSARR__LOGGING__LEVEL=debug    # → logging.level = debug
```

## Tests

```bash
cd backend
pytest tests/ -v
```

## Critères de validation Feature 000

- [ ] `uvicorn app.main:app` démarre sans erreur
- [ ] `/config/pressarr.db` est créé automatiquement au premier démarrage
- [ ] `/config/pressarr.yml` est créé avec une API key auto-générée
- [ ] `GET /api/v1/system/status` retourne 200 avec version et uptime
- [ ] Le frontend affiche "Pressarr" avec un dark theme sur http://localhost:8585
- [ ] `docker build` produit une image fonctionnelle
- [ ] Les volumes /config, /magazines, /downloads sont montables
