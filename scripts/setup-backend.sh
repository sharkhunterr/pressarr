#!/bin/bash
# Script d'initialisation du backend Python

set -e

echo "🐍 Configuration du backend Python..."

cd "$(dirname "$0")/../backend"

# Créer l'environnement virtuel s'il n'existe pas
if [ ! -d ".venv" ]; then
    echo "📦 Création de l'environnement virtuel..."
    python3 -m venv .venv
fi

# Activer l'environnement virtuel
source .venv/bin/activate

# Mettre à jour pip
echo "📦 Mise à jour de pip..."
pip install --upgrade pip

# Installer les dépendances
echo "📦 Installation des dépendances..."
pip install -r requirements.txt

# Installer les dépendances de développement
echo "📦 Installation des dépendances de développement..."
pip install -r requirements-dev.txt

echo "✅ Backend configuré avec succès!"
echo ""
echo "Pour activer l'environnement virtuel:"
echo "  cd backend"
echo "  source .venv/bin/activate"
