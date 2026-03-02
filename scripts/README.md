# Scripts de Release et Déploiement Pressarr

Ce dossier contient les scripts d'automatisation pour les releases, pushs Git et déploiements Docker.

## 📦 Commandes de Release

### Release standard (GitLab uniquement)
```bash
npm run release              # Patch release (0.1.0 → 0.1.1)
npm run release:patch        # Équivalent à ci-dessus
npm run release:minor        # Minor release (0.1.0 → 0.2.0)
npm run release:major        # Major release (0.1.0 → 1.0.0)
```

**Ce que ça fait :**
- ✅ Bump version dans `package.json` et `version.py`
- ✅ Génère/met à jour `CHANGELOG.md`
- ✅ Crée un commit de release
- ✅ Crée un tag git
- ✅ Push vers GitLab avec les tags
- ✅ Crée une release GitLab avec le contenu de `GITHUB_RELEASES.md`

### Release vers GitHub
```bash
npm run release:github       # Release GitLab + GitHub
```

**Ce que ça fait :**
- ✅ Tout ce que fait `npm run release`
- ✅ Push aussi vers le remote GitHub
- ✅ Crée une release GitHub avec le contenu de `GITHUB_RELEASES.md`

**Prérequis :**
- Remote GitHub configuré : `git remote add github https://github.com/sharkhunterr/pressarr.git`
- CLI GitHub installé : `brew install gh` ou https://cli.github.com/
- Authentifié : `gh auth login`

### Release avec déploiement Docker
```bash
npm run release:deploy       # Release + trigger CI Docker deploy
npm run release:full         # Release GitLab + GitHub + Docker deploy
```

**Ce que ça fait :**
- ✅ Tout ce que fait `npm run release` ou `release:github`
- ✅ Ajoute `-o ci.variable="DEPLOY=true"` au push GitLab
- ✅ Déclenche le pipeline GitLab CI avec déploiement Docker Hub

### Dry run
```bash
npm run release:dry          # Simule une release sans rien modifier
```

## 🚀 Commandes de Push

### Push simple
```bash
npm run push                 # Push vers GitLab (origin)
npm run push:github          # Push vers GitHub uniquement
npm run push:all             # Push vers GitLab ET GitHub
```

### Push avancé
```bash
npm run push:tags            # Push uniquement les tags
npm run push:notags          # Push sans les tags
```

### Options combinables
```bash
node scripts/push.js --all --force        # Force push vers tous les remotes
node scripts/push.js --github --no-tags   # Push GitHub sans tags
```

## 🐳 Commandes Docker

### Build local
```bash
npm run docker:build         # Build l'image Docker localement
```

### Déploiement Docker Hub
```bash
npm run docker:deploy        # Build + push vers Docker Hub (linux/amd64)
npm run docker:deploy:multi  # Build + push multi-plateforme (amd64 + arm64)
```

**Ce que ça fait :**
- ✅ Build l'image Docker
- ✅ Tag avec la version courante et `latest`
- ✅ Push vers Docker Hub (`sharkhunterr/pressarr`)

**Prérequis :**
- Docker en cours d'exécution
- Authentifié Docker Hub : `docker login`
- Pour multi-plateforme : `docker buildx` configuré

## 📝 Workflow Complet de Release

### 1. Mettre à jour les release notes
Éditez `GITHUB_RELEASES.md` avec les changements de la prochaine version :

```markdown
## [v0.2.0] - 2026-03-01

### ✨ Features
- Ajout du système de release automatisé

### 🐛 Bug Fixes
- Correction du problème de migrations Alembic

### 🚀 Improvements
- Optimisation du temps de démarrage Docker
```

### 2. Faire la release

**Option A - Release GitLab uniquement (rapide) :**
```bash
npm run release
```

**Option B - Release complète (GitLab + GitHub + Docker) :**
```bash
npm run release:full
```

**Option C - Release personnalisée :**
```bash
# Version mineure, push GitLab et GitHub, pas de Docker
node scripts/release.js minor --github
```

### 3. Vérifier le déploiement

- **GitLab** : Vérifier les releases GitLab
- **GitHub** : https://github.com/sharkhunterr/pressarr/releases
- **Docker Hub** : https://hub.docker.com/r/sharkhunterr/pressarr
- **GitLab CI** : Vérifier les pipelines

## 🔧 Configuration

### Ajouter le remote GitHub
```bash
git remote add github https://github.com/sharkhunterr/pressarr.git
```

### Installer les CLI nécessaires

**GitHub CLI (pour releases GitHub) :**
```bash
# macOS
brew install gh

# Linux
sudo apt install gh  # Debian/Ubuntu
sudo dnf install gh  # Fedora

# Authentification
gh auth login
```

**GitLab CLI (pour releases GitLab) :**
```bash
# macOS
brew install glab

# Linux
sudo apt install glab  # Debian/Ubuntu

# Authentification
glab auth login
```

## 🎯 Exemples d'Utilisation

### Scénario 1 : Hotfix rapide (patch)
```bash
# 1. Corriger le bug et commit
git add .
git commit -m "fix: correction urgente"

# 2. Release patch (0.1.0 → 0.1.1)
npm run release

# 3. Vérifier sur GitLab
```

### Scénario 2 : Nouvelle fonctionnalité
```bash
# 1. Développer la feature et commit
git add .
git commit -m "feat: nouvelle fonctionnalité"

# 2. Mettre à jour GITHUB_RELEASES.md
# 3. Release mineure complète
npm run release:minor --github --deploy
```

### Scénario 3 : Push de travail en cours
```bash
# Push vers GitLab sans créer de release
npm run push

# Push vers tous les remotes
npm run push:all
```

### Scénario 4 : Déploiement Docker manuel
```bash
# Build et test local
npm run docker:build

# Déployer vers Docker Hub
npm run docker:deploy
```

## 📄 Structure des Fichiers

```
scripts/
├── release.js           # Script de release principal
├── push.js              # Script de push Git
├── docker-deploy.js     # Script de déploiement Docker
├── version-updater.js   # Updater pour version.py
├── ci-auto-fix.sh       # Auto-fix CI/CD
├── fix-linting.sh       # Fix linting local
├── run-backend-tests.sh # Tests backend
├── run-backend-lint.sh  # Lint backend
├── run-backend-fix.sh   # Fix backend
├── setup-backend.sh     # Setup backend
├── generate-reports.sh  # Génération des rapports
└── README.md            # Cette documentation
```

## 🆘 Dépannage

### Erreur "glab not found" ou "gh not found"
Les releases GitLab/GitHub seront skippées si les CLI ne sont pas installées. Installez-les si besoin.

### Erreur "remote not configured"
Ajoutez le remote manquant :
```bash
git remote add github https://github.com/sharkhunterr/pressarr.git
```

### Erreur "Working directory not clean"
Committez ou stash vos changements avant de faire une release :
```bash
git status
git add .
git commit -m "votre message"
```

### Docker "not logged in"
Authentifiez-vous sur Docker Hub :
```bash
docker login
```
