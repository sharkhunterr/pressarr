# Feature 008: Internet Archive Direct Download

**Branch:** 008-internet-archive-download
**Date:** 2026-02-25
**Status:** Draft

## Overview

Utiliser Internet Archive comme source de téléchargement gratuite et complémentaire aux indexeurs classiques. Les fichiers sont téléchargés directement via HTTP depuis la collection Magazine Rack, sans nécessiter de client de téléchargement externe.

## User Stories

### US-008.1: Rechercher des issues sur Internet Archive
**En tant que** utilisateur,
**je veux** rechercher des issues de magazine sur Internet Archive,
**afin de** trouver des numéros disponibles gratuitement.

**Critères d'acceptation :**
- [ ] Depuis la page d'une issue, un bouton permet de chercher sur Internet Archive
- [ ] La recherche cible la collection "magazinerack" d'Internet Archive
- [ ] Les résultats affichent : titre, date, format(s) disponible(s), taille
- [ ] Les résultats sont matchés avec l'issue consultée quand possible
- [ ] Si Internet Archive est indisponible, un message d'avertissement est affiché

### US-008.2: Matcher avec les issues manquantes
**En tant que** système,
**je veux** matcher automatiquement les résultats Internet Archive avec les issues manquantes,
**afin de** proposer des téléchargements gratuits pour compléter la collection.

**Critères d'acceptation :**
- [ ] Le système compare les résultats IA avec les issues au statut "wanted"
- [ ] Le matching se base sur le titre normalisé du magazine et la date/numéro de l'issue
- [ ] Les matchs trouvés sont signalés à l'utilisateur dans l'interface
- [ ] L'utilisateur peut déclencher le téléchargement d'un match en un clic

### US-008.3: Télécharger directement via HTTP
**En tant que** système,
**je veux** télécharger un fichier directement depuis Internet Archive via HTTP,
**afin de** ne pas nécessiter de client de téléchargement externe pour cette source.

**Critères d'acceptation :**
- [ ] Le téléchargement se fait en HTTP direct sans passer par un client externe
- [ ] La progression du téléchargement est suivie et affichée (%, vitesse, ETA)
- [ ] Le téléchargement peut être annulé par l'utilisateur
- [ ] L'issue passe au statut "downloading" pendant le téléchargement

### US-008.4: Respecter les rate limits
**En tant que** système,
**je veux** respecter les rate limits d'Internet Archive,
**afin de** ne pas être banni et contribuer au bon fonctionnement du service.

**Critères d'acceptation :**
- [ ] Maximum 1 requête de recherche par seconde vers Internet Archive
- [ ] Maximum 1 téléchargement concurrent depuis Internet Archive
- [ ] Les téléchargements sont mis en file d'attente si la limite est atteinte
- [ ] Un délai configurable est respecté entre les téléchargements (défaut : 5 secondes)

### US-008.5: Intégrer dans le pipeline d'import standard
**En tant que** système,
**je veux** que les fichiers téléchargés depuis Internet Archive passent par le même pipeline d'import,
**afin de** garantir un traitement cohérent (renommage, déplacement, couverture).

**Critères d'acceptation :**
- [ ] Après téléchargement, le fichier est traité par le pipeline d'import standard (Feature 006)
- [ ] Le renommage et le déplacement suivent le même template que les autres sources
- [ ] La couverture est extraite si absente
- [ ] L'historique enregistre la source comme "Internet Archive"

## Functional Requirements

### FR-008.1: Client HTTP dédié
Le téléchargement depuis Internet Archive DOIT utiliser un client HTTP intégré à Pressarr, distinct des clients de téléchargement externes.

### FR-008.2: Gestion de la file d'attente
Les téléchargements Internet Archive DOIVENT être gérés dans une file d'attente séparée avec respect strict des rate limits.

### FR-008.3: Reprise de téléchargement
Si un téléchargement est interrompu (redémarrage de Pressarr), il DOIT pouvoir être repris là où il s'était arrêté (HTTP Range si supporté par le serveur).

### FR-008.4: Priorité des sources
Internet Archive DOIT être utilisable comme source complémentaire. Les résultats Prowlarr DOIVENT être prioritaires si les deux sources trouvent la même issue.

## Non-Functional Requirements

### NFR-008.1: Respect d'Internet Archive
Le système DOIT se comporter en bon citoyen : respecter les rate limits, inclure un User-Agent identifiable, ne pas contourner les restrictions.

### NFR-008.2: Pas de dépendance
Internet Archive DOIT être une source optionnelle. Pressarr DOIT fonctionner normalement même si Internet Archive est désactivé ou indisponible.

## Edge Cases & Error Handling

- Si Internet Archive retourne une erreur 429 (Too Many Requests), le système DOIT attendre le délai indiqué avant de réessayer.
- Si un fichier est incomplet après téléchargement (taille ne correspond pas), le fichier est supprimé et le téléchargement est réessayé (max 3 fois).
- Si le format disponible sur IA n'est pas un format magazine supporté, le résultat est ignoré.
- Si la connexion est perdue pendant le téléchargement, une reprise est tentée après reconnexion.
- Si Internet Archive change sa structure d'API, un log d'erreur explicite est émis.

## Out of Scope

- Crawling systématique d'Internet Archive
- Téléchargement de contenus autres que les magazines
- Métadonnées récupérées depuis Internet Archive (Feature 003)

## Open Questions

Aucune.

## Dependencies

- Dépend de : Feature 000 (Foundation), Feature 001 (Magazine), Feature 003 (Metadata — recherche IA), Feature 006 (Post-Download Import)
- Bloque : Aucune
