#!/bin/bash
# Script pour générer tous les rapports de qualité de code et tests

set -e

echo "========================================"
echo "Pressarr - Génération des rapports"
echo "========================================"

cd "$(dirname "$0")/.."

# Créer le dossier de rapports
mkdir -p reports

# ============================================================================
# Backend Reports
# ============================================================================
if [ -d "backend" ]; then
    echo ""
    echo "🐍 Génération des rapports backend..."
    cd backend

    # Activate virtual environment if it exists
    if [ -f ".venv/bin/activate" ]; then
        source .venv/bin/activate
    fi

    if command -v ruff &> /dev/null; then
        # Rapport Ruff (linting)
        echo "  → Rapport Ruff (JSON)..."
        ruff check app/ --output-format=json > ../reports/ruff-report.json 2>&1 || true

        echo "  → Rapport Ruff (TXT)..."
        ruff check app/ --output-format=text > ../reports/ruff-report.txt 2>&1 || true

        # Rapport Ruff avec suggestions de corrections
        echo "  → Rapport Ruff avec suggestions..."
        ruff check app/ --output-format=text --show-fixes > ../reports/ruff-fixes.txt 2>&1 || true

        # Générer un fichier PATCH avec les corrections
        echo "  → Génération du patch de corrections..."
        ruff check app/ --fix --diff > ../reports/ruff-fixes.patch 2>&1 || true

        # Rapport Ruff format
        echo "  → Rapport Ruff format..."
        ruff format app/ --check --diff > ../reports/ruff-format-report.txt 2>&1 || true

        # Rapport de tests avec coverage
        echo "  → Tests et couverture..."
        pytest \
            --cov=app \
            --cov-report=xml:../reports/coverage.xml \
            --cov-report=html:../reports/htmlcov \
            --cov-report=term \
            --junitxml=../reports/junit.xml \
            -v > ../reports/pytest-output.txt 2>&1 || true

        # Résumé de la couverture
        echo "  → Résumé de couverture..."
        coverage report > ../reports/coverage-summary.txt 2>&1 || true

        echo "  ✅ Rapports backend générés"
    else
        echo "  ⚠️  Ruff non trouvé - rapports backend ignorés"
    fi

    cd ..
fi

# ============================================================================
# Frontend Reports
# ============================================================================
if [ -d "frontend" ]; then
    echo ""
    echo "🎨 Génération des rapports frontend..."
    cd frontend

    if command -v npm &> /dev/null; then
        # Rapport ESLint (JSON)
        echo "  → Rapport ESLint (JSON)..."
        npm run lint -- --format json --output-file ../reports/eslint-report.json 2>&1 || true

        # Rapport ESLint (TXT)
        echo "  → Rapport ESLint (TXT)..."
        npm run lint -- --format stylish > ../reports/eslint-report.txt 2>&1 || true

        # Rapport ESLint avec suggestions de corrections
        echo "  → Rapport ESLint avec suggestions..."
        npm run lint -- --format codeframe > ../reports/eslint-fixes.txt 2>&1 || true

        # Tests frontend
        echo "  → Tests frontend..."
        npm test -- --coverage --coverageReporters=text --coverageReporters=json-summary > ../reports/frontend-test-output.txt 2>&1 || echo "  ℹ️  Pas de tests configurés"

        echo "  ✅ Rapports frontend générés"
    else
        echo "  ⚠️  npm non trouvé - rapports frontend ignorés"
    fi

    cd ..
fi

# ============================================================================
# Résumé consolidé
# ============================================================================
echo ""
echo "📝 Génération du résumé consolidé..."

cat > reports/SUMMARY.md << EOF
# Pressarr - Rapport de Qualité de Code

Généré le: $(date '+%Y-%m-%d %H:%M:%S')

## 📊 Backend (Python)

### Linting (Ruff)
EOF

if [ -f "reports/ruff-report.txt" ]; then
    RUFF_ERRORS=$(grep -c "Found.*errors" reports/ruff-report.txt 2>/dev/null || echo "0")
    echo "- **Erreurs trouvées:** $RUFF_ERRORS" >> reports/SUMMARY.md
    echo "" >> reports/SUMMARY.md
    echo "\`\`\`" >> reports/SUMMARY.md
    head -50 reports/ruff-report.txt >> reports/SUMMARY.md
    echo "\`\`\`" >> reports/SUMMARY.md
else
    echo "⚠️ Rapport non généré" >> reports/SUMMARY.md
fi

cat >> reports/SUMMARY.md << 'EOF'

### Couverture de tests
EOF

if [ -f "reports/coverage-summary.txt" ]; then
    echo "\`\`\`" >> reports/SUMMARY.md
    cat reports/coverage-summary.txt >> reports/SUMMARY.md
    echo "\`\`\`" >> reports/SUMMARY.md
else
    echo "⚠️ Rapport non généré" >> reports/SUMMARY.md
fi

cat >> reports/SUMMARY.md << 'EOF'

## 🎨 Frontend (React/TypeScript)

### Linting (ESLint)
EOF

if [ -f "reports/eslint-report.txt" ]; then
    echo "\`\`\`" >> reports/SUMMARY.md
    head -50 reports/eslint-report.txt >> reports/SUMMARY.md
    echo "\`\`\`" >> reports/SUMMARY.md
else
    echo "⚠️ Rapport non généré" >> reports/SUMMARY.md
fi

cat >> reports/SUMMARY.md << 'EOF'

---

## 📁 Fichiers de rapports

### Backend
- `ruff-report.json` - Rapport Ruff au format JSON
- `ruff-report.txt` - Rapport Ruff au format texte
- `ruff-fixes.txt` - Suggestions de corrections Ruff
- `ruff-fixes.patch` - Fichier patch pour appliquer les corrections
- `ruff-format-report.txt` - Rapport Ruff format
- `coverage.xml` - Couverture de code (format Cobertura)
- `htmlcov/` - Rapport de couverture HTML
- `junit.xml` - Résultats de tests (format JUnit)

### Frontend
- `eslint-report.json` - Rapport ESLint au format JSON
- `eslint-report.txt` - Rapport ESLint au format texte
- `eslint-fixes.txt` - Suggestions de corrections ESLint

## 🔧 Commandes pour appliquer les corrections

### Backend
```bash
# Appliquer les corrections automatiques Ruff
cd backend && source .venv/bin/activate && ruff check app/ --fix --unsafe-fixes

# Appliquer le formatage Ruff
cd backend && source .venv/bin/activate && ruff format app/

# Ou appliquer le patch généré
patch -p1 < reports/ruff-fixes.patch
```

### Frontend
```bash
# Appliquer les corrections automatiques ESLint
cd frontend && npm run lint -- --fix
```

### Les deux
```bash
# Utiliser le script d'auto-fix
npm run fix
# ou
bash scripts/ci-auto-fix.sh
```
EOF

echo ""
echo "========================================"
echo "✅ Rapports générés avec succès!"
echo "========================================"
echo ""
echo "📁 Rapports disponibles dans: ./reports/"
echo ""
echo "Fichiers principaux:"
echo "  - reports/SUMMARY.md              Résumé consolidé"
echo "  - reports/ruff-fixes.patch        Patch pour corrections backend"
echo "  - reports/htmlcov/index.html      Rapport de couverture HTML"
echo ""
echo "Pour visualiser:"
echo "  cat reports/SUMMARY.md"
echo "  open reports/htmlcov/index.html  # ou xdg-open sur Linux"
echo ""
echo "Pour appliquer les corrections:"
echo "  npm run fix"
echo ""

# Afficher le résumé
if [ -f "reports/SUMMARY.md" ]; then
    echo "=== RÉSUMÉ ==="
    cat reports/SUMMARY.md | head -30
fi
