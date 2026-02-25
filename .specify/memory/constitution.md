<!--
  Sync Impact Report
  ==================
  Version change: N/A → 1.0.0 (initial creation)
  Modified principles: None (initial creation)
  Added sections:
    - Article I: Architecture Modulaire
    - Article II: Compatibilite Ecosysteme *arr
    - Article III: Tests d'Abord (Test-First)
    - Article IV: Async-First et Type Safety
    - Article V: Simplicite et Anti-Over-Engineering
    - Article VI: Docker-Native et Self-Hosted
    - Article VII: UI Sombre et Coherente
    - Article VIII: Gestion des Erreurs et Resilience
    - Article IX: Conventions de Nommage et Structure
    - Article X: Gouvernance et Amendements
  Removed sections: None
  Templates requiring updates:
    - .specify/templates/plan-template.md: ✅ No update needed (Constitution Check
      section is generic and will be filled per-feature)
    - .specify/templates/spec-template.md: ✅ No update needed (spec structure is
      compatible with constitution principles)
    - .specify/templates/tasks-template.md: ✅ No update needed (task phases align
      with constitution workflow)
  Follow-up TODOs: None
-->

# Pressarr Constitution

**Version**: 1.0.0 | **Ratified**: 2026-02-25 | **Last Amended**: 2026-02-25

Ce document definit les principes NON-NEGOCIABLES du projet Pressarr. Toute
contribution, feature ou refactoring DOIT respecter ces articles. En cas de
conflit entre une pratique et la constitution, la constitution prime.

---

## Article I : Architecture Modulaire

Le projet est organise en modules clairement separes avec des responsabilites
bien definies.

### Section 1.1 : Separation Backend/Frontend

Le repertoire `backend/` contient TOUTE la logique serveur. JAMAIS de logique
metier dans le frontend. Le frontend est un consommateur pur de l'API.

### Section 1.2 : Modules par Domaine Metier

Chaque domaine metier (magazines, issues, calendar, downloads, metadata) a son
propre module dans `services/`. Un service = un fichier = un domaine.

### Section 1.3 : Clients Externes Isoles

Les dependances externes (Prowlarr API, Deluge API, Google Books API, Internet
Archive) sont isolees dans des clients dedies (`indexers/`, `download_clients/`,
`metadata/`). Chaque client externe implemente une interface abstraite (`base.py`)
pour permettre le remplacement.

### Section 1.4 : Separation Modeles/Schemas

Les modeles SQLAlchemy (`models/`) sont separes des schemas Pydantic
(`schemas/`). JAMAIS de melange ORM/API dans un meme objet.

### Section 1.5 : Communication Frontend-Backend

Le frontend communique UNIQUEMENT via l'API REST `/api/v1/*` et le WebSocket
`/ws`. JAMAIS d'acces direct a la DB ou aux services depuis le frontend.

---

## Article II : Compatibilite Ecosysteme *arr

Pressarr DOIT s'integrer nativement dans l'ecosysteme *arr existant.

### Section 2.1 : Conventions API

L'API REST suit les conventions Sonarr/Radarr : `/api/v1/{resource}` pour les
ressources, `POST /api/v1/command` pour les actions asynchrones.

### Section 2.2 : Compatibilite Widgets

Les reponses API sont compatibles avec les widgets Homepage, Homarr et Organizr.

### Section 2.3 : Labels Download Client

Le download client utilise le label/categorie `pressarr` dans tous les clients
(Deluge, qBittorrent, SABnzbd, etc.).

### Section 2.4 : Prowlarr comme Source Primaire

Prowlarr est le point d'entree PRIMAIRE pour les recherches d'indexeurs. Les
connexions directes Newznab/Torznab sont un fallback uniquement.

### Section 2.5 : Constantes Ecosysteme

- La categorie indexeur par defaut est `7020` (Magazines).
- Le port par defaut est `8585`.
- La configuration suit le pattern Docker standard de l'ecosysteme *arr :
  volumes `/config`, `/magazines`, `/downloads`.

---

## Article III : Tests d'Abord (Test-First)

Tout code significatif DOIT avoir des tests correspondants AVANT ou PENDANT
l'implementation.

### Section 3.1 : Couverture Minimum par Composant

- Le parser de noms de fichiers magazines DOIT avoir au minimum 25 cas de test
  couvrant tous les patterns.
- Les providers de metadonnees DOIVENT avoir des tests avec des reponses HTTP
  mockees.
- Les endpoints API DOIVENT avoir des tests d'integration avec une DB SQLite en
  memoire.
- La logique de calendar forecast DOIT avoir des tests pour chaque type de
  frequence (weekly, biweekly, monthly, bimonthly, quarterly, annual).

### Section 3.2 : Framework et Style de Tests

Les tests utilisent `pytest` et `pytest-asyncio`. Preferer les tests
d'integration realistes (vraie DB SQLite, vrais appels HTTP mockes) aux tests
unitaires purs avec mocks excessifs.

### Section 3.3 : Politique de Couverture

Pas de couverture minimale imposee, mais chaque service critique a au moins un
test de happy path et un test d'erreur.

---

## Article IV : Async-First et Type Safety

Tout code I/O DOIT etre asynchrone. Tout code DOIT etre type.

### Section 4.1 : Async Obligatoire

Toute fonction qui fait de l'I/O (DB, HTTP, fichiers) DOIT etre `async`.

### Section 4.2 : Type Hints Obligatoires

Les type hints Python sont OBLIGATOIRES sur toutes les signatures de fonctions
et les retours. Pas de `Any` sauf justification explicite.

### Section 4.3 : Validation Pydantic

Les schemas Pydantic v2 sont utilises pour TOUTE validation de donnees
entrantes/sortantes de l'API.

### Section 4.4 : SQLAlchemy 2.0 Style

Utiliser le style SQLAlchemy 2.0 (`select()`, `Session.execute()`). PAS le
legacy query style (`session.query()`).

### Section 4.5 : Client HTTP Unique

HTTPX est le client HTTP unique (pas `requests`, pas `aiohttp`). Async par
defaut.

### Section 4.6 : Injection de Dependances

FastAPI `Depends()` pour l'injection de dependances. PAS de singletons globaux
ni d'imports de modules pour l'etat partage.

---

## Article V : Simplicite et Anti-Over-Engineering

Le code DOIT rester simple et direct. Pas d'abstraction prematuree.

### Section 5.1 : Utilisation Directe des Frameworks

Utiliser les features du framework directement (FastAPI, SQLAlchemy, Pydantic).
Ne PAS les wrapper dans des couches d'abstraction custom.

### Section 5.2 : Un Fichier par Concept

Un seul fichier par concept. Pas de fichiers separes pour les exceptions, les
constantes ou les enums d'un meme module.

### Section 5.3 : Pas de Patterns Enterprise

Pas de patterns Enterprise Java (Factory, AbstractFactory, Builder, etc.) sauf
si absolument necessaire et justifie dans un commentaire de code.

### Section 5.4 : Implementation Simple d'Abord

Commencer avec l'implementation la plus simple possible. Refactorer uniquement
quand la complexite est prouvee par un besoin reel.

### Section 5.5 : Profondeur d'Appel Limitee

Maximum 3 niveaux d'appel entre l'endpoint API et la DB :
route -> service -> repository/query.

### Section 5.6 : Fonctions Courtes et Focalisees

Les fonctions font UNE chose. Si une fonction depasse 50 lignes, la decouper.

### Section 5.7 : Pas de Future-Proofing

Ne pas coder pour des features qui n'existent pas encore. Resoudre le probleme
actuel, pas un probleme hypothetique.

---

## Article VI : Docker-Native et Self-Hosted

Pressarr est concu pour tourner en conteneur Docker sur un NAS/serveur
self-hosted.

### Section 6.1 : Image Standalone

Le Dockerfile DOIT produire une image fonctionnelle standalone (backend +
frontend servi statiquement).

### Section 6.2 : Configuration YAML + Env

La configuration est YAML (`/config/pressarr.yml`) avec override par variables
d'environnement (`PRESSARR__*`).

### Section 6.3 : Chemins Configurables

Tous les chemins sont configurables via volumes Docker : `/config`, `/magazines`,
`/downloads`.

### Section 6.4 : SQLite dans /config

La base de donnees SQLite est dans `/config/pressarr.db`. Pas de serveur de DB
externe requis.

### Section 6.5 : Logs Rotationnes

Les logs vont dans `/config/logs/` et sont rotationnes automatiquement.

### Section 6.6 : Zero-Config au Premier Demarrage

Le premier demarrage DOIT fonctionner sans aucune configuration prealable :
auto-generation de l'API key, creation DB, migration automatique.

### Section 6.7 : Pas de Dependance Cloud

Pas de dependance a un service cloud. Tout fonctionne en local/LAN.

---

## Article VII : UI Sombre et Coherente

Le frontend DOIT avoir un dark theme par defaut coherent avec l'esthetique *arr.

### Section 7.1 : Palette de Couleurs

Dark theme par defaut. Palette `zinc-900`/`zinc-950` pour les backgrounds,
`zinc-100` pour le texte. Couleur d'accent : `#E85D04` (orange chaud,
"press orange").

### Section 7.2 : Composants shadcn/ui

Composants `shadcn/ui` exclusivement. Pas de UI custom sauf necessite absolue
documentee.

### Section 7.3 : Etats de Page Obligatoires

Chaque page a un etat loading (skeletons), un etat vide, et un etat erreur.

### Section 7.4 : Grille Responsive

Responsive : 4 colonnes desktop, 2 tablette, 1 mobile pour les grilles.
Les couvertures de magazines sont au ratio 3:4.

### Section 7.5 : Code Couleur des Status Badges

Les status badges suivent un code couleur strict :
- Vert : available
- Orange : wanted
- Rouge : missing
- Violet : snatched
- Bleu : downloading
- Gris : upcoming/skipped

---

## Article VIII : Gestion des Erreurs et Resilience

Les erreurs des services externes ne DOIVENT JAMAIS crasher Pressarr.

### Section 8.1 : Try/Except Obligatoire

Les appels aux APIs externes (Prowlarr, Google Books, IA, download clients)
sont TOUJOURS dans un `try/except`.

### Section 8.2 : Degradation Gracieuse

Un service externe indisponible = log warning + skip. JAMAIS une 500 cote
Pressarr.

### Section 8.3 : Continuite des Taches Planifiees

Les scheduled tasks (RSS sync, search, forecast) continuent meme si un magazine
ou une source echoue. Un echec unitaire ne bloque pas le batch.

### Section 8.4 : Retry avec Backoff

Les telechargements echoues sont retentes avec backoff exponentiel (maximum 3
tentatives).

### Section 8.5 : Codes HTTP Appropries

L'API retourne des codes HTTP appropries : `201 Created`, `404 Not Found`,
`409 Conflict`, `422 Validation Error`.

### Section 8.6 : Logging Contextuel

Les erreurs sont loguees avec contexte : `magazine_id`, `issue_id`,
`provider_name`, URL appelee.

---

## Article IX : Conventions de Nommage et Structure

Le code suit des conventions strictes pour la lisibilite et la maintenabilite.

### Section 9.1 : Conventions Python

- `snake_case` pour les fonctions et variables.
- `PascalCase` pour les classes.
- `UPPER_CASE` pour les constantes.

### Section 9.2 : Nommage des Fichiers

Un module = un fichier. Le nom du fichier = le concept principal
(`magazine_service.py`, pas `services.py`).

### Section 9.3 : Conventions API

`/api/v1/{resource}` en kebab-case (sauf exceptions ecosysteme *arr). Noms de
ressources au singulier (`/magazine`, `/issue`).

### Section 9.4 : Conventions Git

- Commits : Conventional Commits (`feat:`, `fix:`, `docs:`, `refactor:`,
  `test:`, `chore:`).
- Branches : `feature/{nom}`, `fix/{nom}`, `docs/{nom}`.

### Section 9.5 : Documentation dans le Code

Chaque fichier Python a un docstring de module expliquant son role. Les TODO
dans le code sont autorises UNIQUEMENT avec un lien vers une issue GitHub.

---

## Article X : Gouvernance et Amendements

La constitution est un document vivant qui evolue avec le projet.

### Section 10.1 : Primaute de la Constitution

La constitution PRIME sur toutes les autres pratiques. En cas de conflit entre
une pratique et la constitution, la constitution gagne.

### Section 10.2 : Procedure d'Amendement

Les amendements necessitent :
- Documentation de la raison du changement.
- Evaluation de l'impact sur le code existant.

### Section 10.3 : Versionnage des Amendements

Chaque amendement est date et versionne dans ce document selon le semantic
versioning :
- MAJOR : suppression ou redefinition incompatible d'un principe.
- MINOR : ajout d'un nouveau principe ou expansion materielle.
- PATCH : clarifications, corrections de formulation.

### Section 10.4 : Deviations Autorisees

Les deviations de la constitution sont autorisees UNIQUEMENT si documentees et
justifiees dans le code par un commentaire explicite referancant l'article
concerne.

### Section 10.5 : Versionnage avec le Code

La constitution est commitee dans le repo et versionnee avec le code source.

---

## Historique des Amendements

| Version | Date       | Description                        | Articles Impactes |
|---------|------------|------------------------------------|-------------------|
| 1.0.0   | 2026-02-25 | Creation initiale de la constitution | Tous              |

<!-- Template pour les futurs amendements :
| X.Y.Z   | YYYY-MM-DD | Description du changement          | Art. N, Art. M    |
-->
