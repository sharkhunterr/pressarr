# Feature 006: Post-Download Import

**Branch:** 006-post-download-import
**Date:** 2026-02-25
**Status:** Draft

## Overview

Traiter automatiquement les fichiers téléchargés : les reconnaître via le parser de noms, les matcher avec l'issue attendue, les renommer selon le template configuré, les déplacer dans la bibliothèque, extraire la couverture, mettre à jour la base de données et envoyer les notifications.

## User Stories

### US-006.1: Détecter un fichier téléchargé terminé
**En tant que** système,
**je veux** détecter quand un fichier a fini d'être téléchargé,
**afin de** déclencher automatiquement le processus d'import.

**Critères d'acceptation :**
- [ ] Le système est notifié par le module de suivi des téléchargements quand un download est complété
- [ ] Le chemin du fichier téléchargé est récupéré
- [ ] Si le téléchargement contient un dossier avec plusieurs fichiers, le fichier magazine principal est identifié
- [ ] Le processus d'import démarre automatiquement sans intervention manuelle

### US-006.2: Parser et identifier le fichier
**En tant que** système,
**je veux** parser le nom du fichier téléchargé pour en extraire les informations,
**afin de** l'identifier et le rattacher à la bonne issue.

**Critères d'acceptation :**
- [ ] Le nom de fichier est analysé pour en extraire : titre, numéro, date, langue, qualité, format
- [ ] Le titre extrait est matché avec les magazines connus dans la bibliothèque
- [ ] Le numéro/date est matché avec l'issue attendue (celle qui a été "grabbed")
- [ ] Si le matching échoue, le fichier est placé en attente d'import manuel
- [ ] Le niveau de confiance du matching est enregistré

### US-006.3: Renommer et déplacer le fichier
**En tant que** système,
**je veux** renommer le fichier selon le template configuré et le déplacer dans la bibliothèque,
**afin de** maintenir une organisation cohérente.

**Critères d'acceptation :**
- [ ] Le fichier est renommé selon le template de nommage configuré
- [ ] Le fichier est placé dans le sous-dossier du magazine selon la politique configurée (copier par défaut, déplacer, ou copier+supprimer)
- [ ] Si le dossier de destination n'existe pas, il est créé automatiquement
- [ ] L'opération de déplacement est atomique : en cas d'erreur, le fichier original reste intact
- [ ] Les caractères interdits dans les noms de fichier sont nettoyés automatiquement

### US-006.4: Extraire la couverture
**En tant que** système,
**je veux** extraire la couverture du fichier importé si l'issue n'en a pas,
**afin de** enrichir visuellement la bibliothèque.

**Critères d'acceptation :**
- [ ] Si l'issue n'a pas de couverture, la première page du PDF est extraite comme image
- [ ] L'image est stockée au format standard dans le dossier de configuration
- [ ] Si l'extraction échoue (format non supporté, fichier corrompu), l'import continue sans erreur
- [ ] Les couvertures existantes ne sont pas écrasées

### US-006.5: Mettre à jour la base de données
**En tant que** système,
**je veux** mettre à jour la base de données après un import réussi,
**afin de** refléter l'état actuel de la bibliothèque.

**Critères d'acceptation :**
- [ ] Un enregistrement de fichier (IssueFile) est créé avec : chemin, format, qualité, taille, date d'import
- [ ] L'issue passe du statut "snatched" ou "downloading" à "available"
- [ ] Les compteurs du magazine parent sont mis à jour (issues disponibles)
- [ ] Un événement "imported" est enregistré dans l'historique

### US-006.6: Envoyer les notifications
**En tant que** système,
**je veux** envoyer une notification après un import réussi,
**afin d'** informer l'utilisateur que son magazine est disponible.

**Critères d'acceptation :**
- [ ] Les notifications configurées pour l'événement "import" sont envoyées
- [ ] La notification inclut : titre du magazine, numéro de l'issue, qualité du fichier
- [ ] La notification inclut la couverture si disponible
- [ ] Si l'envoi de notification échoue, l'import n'est pas annulé

## Functional Requirements

### FR-006.1: Pipeline d'import séquentiel
Le processus d'import DOIT suivre l'ordre : détection → parsing → matching → renommage → déplacement → couverture → base de données → notification.

### FR-006.2: Matching prioritaire par grab
Le matching DOIT d'abord tenter de trouver l'issue correspondant au "grab" enregistré. Si non trouvé, un matching par parsing de nom est tenté.

### FR-006.3: Import manuel de secours
Si le matching automatique échoue, le fichier DOIT être signalé à l'utilisateur pour un import manuel.

### FR-006.4: Upgrade automatique
Si une issue a déjà un fichier et qu'un nouveau fichier de meilleure qualité est importé, l'ancien fichier DOIT être remplacé (selon le profil de qualité).

### FR-006.5: Politique de traitement du fichier source
Après un import réussi, le fichier source DOIT être traité selon la politique configurée par l'utilisateur. Les modes disponibles sont : copier (défaut), déplacer, copier puis supprimer. Le mode par défaut est "copier" (le fichier source reste intact dans le dossier de téléchargement).

## Non-Functional Requirements

### NFR-006.1: Fiabilité
L'import ne DOIT JAMAIS perdre un fichier. En cas d'erreur à n'importe quelle étape, le fichier original DOIT rester accessible.

### NFR-006.2: Performance
L'import d'un fichier unique (hors extraction de couverture) DOIT se terminer en moins de 10 secondes.

## Edge Cases & Error Handling

- Si le fichier téléchargé est un archive (RAR, ZIP), les fichiers magazine à l'intérieur DOIVENT être extraits avant traitement.
- Si le dossier de destination est sur un volume réseau inaccessible, l'import échoue proprement et le fichier reste dans le dossier de téléchargement.
- Si le fichier téléchargé est corrompu (0 octets, format invalide), il est rejeté et l'issue repasse en "wanted".
- Si plusieurs fichiers magazine sont trouvés dans un même téléchargement, chacun est traité indépendamment.
- Si le fichier dépasse une taille configurable (défaut : pas de limite), un avertissement est émis mais l'import continue.

## Out of Scope

- Le parsing de noms de fichiers lui-même (Feature 013)
- Les clients de téléchargement (Feature 005)
- Le moteur de notifications (Feature 010)
- Le profil de qualité pour les upgrades (Feature 009)

## Clarifications

### Session 2026-02-25

- Q: Quelle est la politique par défaut pour le fichier source après import ? → A: Configurable (copier / déplacer / copier+supprimer), défaut = copier (le fichier source reste intact).

## Open Questions

Aucune.

## Dependencies

- Dépend de : Feature 002 (Issue Tracking), Feature 005 (Download Clients), Feature 013 (Filename Parser), Feature 010 (Notifications)
- Bloque : Aucune
