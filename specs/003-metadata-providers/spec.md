# Feature 003: Metadata Providers

**Branch:** 003-metadata-providers
**Date:** 2026-02-25
**Status:** Draft

## Overview

Récupérer les métadonnées des magazines (titre, éditeur, pays, fréquence, ISSN, couverture, description) depuis des sources externes. Ces métadonnées enrichissent la bibliothèque et permettent l'identification précise des magazines et de leurs issues.

## User Stories

### US-003.1: Rechercher via Google Books
**En tant que** système,
**je veux** rechercher un titre de magazine via Google Books API (catégorie magazines),
**afin de** récupérer les métadonnées de base (titre, éditeur, description, couverture).

**Critères d'acceptation :**
- [ ] La recherche retourne les magazines correspondant au terme de recherche
- [ ] Les résultats incluent : titre, éditeur, description, URL de couverture, identifiants (ISBN/ISSN si disponible)
- [ ] Les résultats sont filtrés pour ne retourner que les périodiques (pas les livres)
- [ ] Si l'API est indisponible, un message d'avertissement est retourné sans bloquer l'application
- [ ] Les résultats sont mis en cache pour éviter les appels redondants

### US-003.2: Enrichir via le portail ISSN
**En tant que** système,
**je veux** enrichir un magazine via le portail ISSN,
**afin de** obtenir des métadonnées complémentaires (éditeur officiel, pays, fréquence de publication).

**Critères d'acceptation :**
- [ ] Si un ISSN est connu pour un magazine, le portail ISSN est interrogé
- [ ] Les données récupérées incluent : éditeur, pays de publication, fréquence
- [ ] Les données du portail ISSN complètent (sans écraser) les données existantes
- [ ] Si le portail est indisponible, les métadonnées existantes sont conservées sans erreur

### US-003.3: Rechercher sur Internet Archive
**En tant que** système,
**je veux** chercher des issues de magazines sur la collection Magazine Rack d'Internet Archive,
**afin de** identifier les numéros disponibles gratuitement.

**Critères d'acceptation :**
- [ ] La recherche cible la collection "magazinerack" d'Internet Archive
- [ ] Les résultats incluent : identifiant IA, titre, date, format disponible, URL de téléchargement
- [ ] Les résultats sont matchés avec les issues connues du magazine dans la bibliothèque
- [ ] Le rate limit est respecté (maximum 1 requête par seconde vers Internet Archive)

### US-003.4: Extraire une couverture depuis un PDF
**En tant que** système,
**je veux** extraire la couverture depuis la première page d'un fichier PDF téléchargé,
**afin de** afficher une couverture pour les issues qui n'en ont pas.

**Critères d'acceptation :**
- [ ] La première page du PDF est convertie en image (format JPEG ou PNG)
- [ ] L'image est redimensionnée au ratio 3:4 et à une taille raisonnable (max 500px de large)
- [ ] L'image extraite est stockée dans le dossier de configuration
- [ ] Si l'extraction échoue (fichier corrompu, pas un PDF), aucune erreur n'est propagée

### US-003.5: Agréger et dédupliquer les résultats
**En tant que** système,
**je veux** agréger les résultats de recherche de toutes les sources de métadonnées,
**afin de** présenter une liste unifiée et sans doublons à l'utilisateur.

**Critères d'acceptation :**
- [ ] Les résultats de toutes les sources actives sont combinés
- [ ] Les doublons sont détectés par correspondance de titre normalisé et/ou ISSN
- [ ] Le résultat agrégé prend la meilleure donnée de chaque source (ex: couverture de Google Books, fréquence de ISSN)
- [ ] L'ordre d'affichage privilégie les résultats les plus complets

### US-003.6: Rafraîchir périodiquement les métadonnées
**En tant que** système,
**je veux** rafraîchir automatiquement les métadonnées des magazines à intervalle régulier,
**afin de** maintenir les informations à jour (nouvelles couvertures, changement d'éditeur).

**Critères d'acceptation :**
- [ ] Un rafraîchissement automatique est déclenché selon un intervalle configurable (défaut : 7 jours)
- [ ] Le rafraîchissement n'écrase pas les données modifiées manuellement par l'utilisateur
- [ ] Si un rafraîchissement échoue pour un magazine, les suivants continuent normalement
- [ ] Le dernier rafraîchissement réussi est enregistré par magazine

## Functional Requirements

### FR-003.1: Interface de provider abstraite
Chaque source de métadonnées DOIT implémenter une interface commune permettant d'ajouter de nouvelles sources sans modifier le code existant.

### FR-003.2: Activation par source
Chaque source de métadonnées DOIT pouvoir être activée ou désactivée individuellement dans la configuration.

### FR-003.3: Cache des résultats
Les résultats des recherches DOIVENT être mis en cache pour éviter les appels redondants aux APIs externes. La durée du cache DOIT être configurable.

### FR-003.4: Gestion des clés API
Les sources nécessitant une clé API (Google Books) DOIVENT fonctionner uniquement quand la clé est configurée. L'absence de clé DOIT désactiver silencieusement la source.

### FR-003.5: Stockage des couvertures
Les images de couverture DOIVENT être stockées localement dans le dossier de configuration après récupération, pour ne pas dépendre de la disponibilité des sources.

## Non-Functional Requirements

### NFR-003.1: Résilience aux pannes
L'indisponibilité d'une source de métadonnées ne DOIT JAMAIS empêcher l'utilisation de Pressarr. Les sources indisponibles sont ignorées avec un log d'avertissement.

### NFR-003.2: Respect des rate limits
Les appels aux APIs externes DOIVENT respecter les rate limits de chaque fournisseur.

### NFR-003.3: Latence de recherche
La recherche agrégée DOIT retourner des résultats dans un délai de 10 secondes maximum, même si certaines sources sont lentes (timeout individuel par source).

## Edge Cases & Error Handling

- Si aucune source n'est configurée/activée, la recherche retourne une liste vide avec un message explicatif.
- Si la clé API Google Books est invalide, la source est désactivée avec un log d'erreur.
- Si un PDF est protégé par mot de passe, l'extraction de couverture échoue silencieusement.
- Si Internet Archive retourne des résultats dans une langue inattendue, ils sont quand même inclus.
- Si le cache de métadonnées devient obsolète et que la source est indisponible, les données en cache sont conservées.

## Out of Scope

- Configuration des sources dans l'interface (Feature 012)
- Téléchargement depuis Internet Archive (Feature 008)
- Utilisation des métadonnées pour le parsing de noms (Feature 013)

## Clarifications

### Session 2026-02-25

- Q: Google Books API quotas — rotation de clés nécessaire ? → A: Non, le quota gratuit standard (1000 requêtes/jour) est suffisant pour un usage self-hosted individuel. Pas de rotation de clés prévue. Le cache des résultats réduit les appels. (Résolu par défaut raisonnable.)

## Open Questions

Aucune.

## Dependencies

- Dépend de : Feature 000 (Project Foundation)
- Bloque : Feature 001 (Magazine Management — recherche), Feature 008 (Internet Archive Download)
