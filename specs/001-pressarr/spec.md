# Pressarr — Automated Magazine Collection Manager

**Branch:** 001-pressarr
**Date:** 2026-02-26
**Status:** Draft

## 1. Vision & Overview

Pressarr est un gestionnaire automatisé de magazines numériques conçu pour l'écosystème self-hosted *arr. Il permet aux collectionneurs de périodiques de surveiller leurs magazines préférés, de rechercher et télécharger automatiquement les nouveaux numéros, et d'organiser leur bibliothèque de manière structurée. Pressarr comble le vide laissé par Sonarr (séries TV) et Radarr (films) pour le domaine des magazines et périodiques. Sa fonctionnalité distinctive de Calendar Forecast prédit les futures parutions et déclenche automatiquement leur acquisition dès disponibilité.

### Ce que Pressarr est

- Un gestionnaire de collection de magazines numériques (PDF, EPUB, CBR, CBZ)
- Un outil de surveillance et téléchargement automatique de périodiques
- Un organisateur de fichiers avec renommage et classement automatique
- Un prédicteur de parutions futures basé sur la fréquence de publication
- Une application web self-hosted intégrée à l'écosystème *arr

### Ce que Pressarr n'est PAS

- Pas un lecteur de magazines (pas de visionneuse intégrée)
- Pas un gestionnaire de livres ou d'ebooks (voir Readarr/Calibre)
- Pas un gestionnaire de comics (voir Mylar3)
- Pas un archiveur de journaux quotidiens
- Pas un service cloud — tout tourne en local

## 2. Personas

### Utilisateur

Personne qui utilise Pressarr via l'interface web pour gérer sa collection de magazines. Il ajoute des magazines à surveiller, consulte sa bibliothèque, vérifie les numéros manquants, et déclenche manuellement des recherches quand nécessaire. Il veut une expérience visuelle agréable (couvertures, calendrier) et un minimum d'intervention manuelle.

### Administrateur

Personne qui installe et configure Pressarr sur son serveur. Il connecte Prowlarr pour les indexeurs, configure les clients de téléchargement, paramètre les notifications, et gère les profils de qualité. Il interagit principalement avec les pages de configuration et s'attend à retrouver les conventions de l'écosystème *arr qu'il connaît déjà.

### Système

Pressarr agissant de manière autonome via ses tâches planifiées. Il vérifie les flux RSS à intervalles réguliers, détecte les nouvelles releases, déclenche les téléchargements, importe les fichiers terminés, renomme et organise les fichiers, et envoie les notifications. Il doit être résilient aux pannes des services externes et ne jamais crasher.

### Dashboard externe

Homepage, Homarr, Organizr ou tout autre consommateur de l'API Pressarr. Il interroge l'API pour afficher des widgets résumant l'état de la collection (nombre de magazines, issues manquantes, file d'attente de téléchargement). Il s'attend à des réponses compatibles avec les conventions Sonarr/Radarr.

## 3. User Stories

### 3.1 Gestion des magazines

#### US-001 : Rechercher un magazine

**En tant qu'** utilisateur,
**je veux** rechercher un magazine par son titre via les sources de métadonnées,
**afin de** trouver le magazine que je souhaite ajouter à ma bibliothèque.

**Critères d'acceptation :**
- [ ] Un champ de recherche permet de saisir un titre de magazine
- [ ] Les résultats affichent le titre, l'éditeur, le pays et la couverture quand disponible
- [ ] Les résultats provenant de différentes sources sont agrégés et dédupliqués
- [ ] Si aucune source n'est disponible, un message d'erreur explicite est affiché
- [ ] Les magazines déjà dans la bibliothèque sont marqués visuellement dans les résultats
- [ ] Les résultats s'affichent en moins de 5 secondes (hors latence réseau des fournisseurs)

#### US-002 : Ajouter un magazine à la bibliothèque

**En tant qu'** utilisateur,
**je veux** ajouter un magazine à ma bibliothèque avec ses paramètres,
**afin de** commencer à surveiller et télécharger ses numéros.

**Critères d'acceptation :**
- [ ] L'utilisateur peut sélectionner un résultat de recherche et l'ajouter
- [ ] L'utilisateur peut ajouter manuellement un magazine non référencé (saisie du titre, fréquence, dossier)
- [ ] Lors de l'ajout, l'utilisateur configure : le dossier de destination, le profil de qualité, la fréquence de publication, l'état de monitoring (activé/désactivé), et la date de début de monitoring
- [ ] La date de début de monitoring détermine à partir de quelle issue le système recherche activement les numéros manquants (les issues antérieures restent "missing" et non "wanted")
- [ ] Après l'ajout, le système récupère la liste des issues connues depuis les sources de métadonnées configurées
- [ ] Après l'ajout, le magazine apparaît dans la bibliothèque avec le statut approprié et ses issues peuplées
- [ ] Un magazine ne peut pas être ajouté en double (même titre normalisé + même ISSN)
- [ ] L'utilisateur peut optionnellement déclencher une recherche automatique des numéros manquants à l'ajout

#### US-003 : Voir la bibliothèque de magazines

**En tant qu'** utilisateur,
**je veux** voir la liste de mes magazines dans une grille de couvertures,
**afin de** avoir une vue d'ensemble de ma collection.

**Critères d'acceptation :**
- [ ] Les magazines sont affichés dans une grille responsive (4 colonnes desktop, 2 tablette, 1 mobile)
- [ ] Chaque carte affiche la couverture (ratio 3:4), le titre et le nombre d'issues disponibles/totales
- [ ] Un badge de statut coloré indique l'état global du magazine (vert=complet, orange=issues manquantes, gris=non monitoré)
- [ ] Les magazines peuvent être triés (par titre, date d'ajout, prochaine parution)
- [ ] Les magazines peuvent être filtrés (par statut de monitoring, par complétude)
- [ ] Un état vide affiche un message invitant à ajouter un premier magazine
- [ ] La page affiche jusqu'à 200 magazines sans dégradation perceptible des performances

#### US-004 : Voir le détail d'un magazine

**En tant qu'** utilisateur,
**je veux** voir la page de détail d'un magazine,
**afin de** consulter ses informations et ses issues.

**Critères d'acceptation :**
- [ ] La page affiche les métadonnées du magazine (titre, éditeur, pays, ISSN, fréquence, description)
- [ ] La couverture est affichée en grand format
- [ ] La liste des issues connues est affichée, groupée par année
- [ ] Les paramètres actuels du magazine sont visibles (dossier, profil qualité, monitoring)
- [ ] Un indicateur de progression affiche le ratio issues disponibles / issues totales

#### US-005 : Modifier les paramètres d'un magazine

**En tant qu'** utilisateur,
**je veux** modifier les paramètres d'un magazine existant,
**afin de** ajuster sa configuration sans le supprimer.

**Critères d'acceptation :**
- [ ] L'utilisateur peut modifier : le dossier de destination, le profil de qualité, la fréquence de publication, l'état de monitoring, les termes de recherche
- [ ] Les modifications sont sauvegardées immédiatement
- [ ] Un changement de dossier de destination propose optionnellement de déplacer les fichiers existants
- [ ] Les fichiers existants ne sont JAMAIS déplacés sans confirmation explicite de l'utilisateur

#### US-006 : Supprimer un magazine

**En tant qu'** utilisateur,
**je veux** supprimer un magazine de ma bibliothèque,
**afin de** ne plus le surveiller.

**Critères d'acceptation :**
- [ ] Une confirmation est demandée avant la suppression
- [ ] L'utilisateur peut choisir de supprimer uniquement l'entrée en base OU de supprimer aussi les fichiers sur le disque
- [ ] Après suppression, le magazine n'apparaît plus dans la bibliothèque
- [ ] Les téléchargements en cours pour ce magazine sont annulés

#### US-007 : Rafraîchir les métadonnées d'un magazine

**En tant qu'** utilisateur,
**je veux** rafraîchir les métadonnées d'un magazine depuis les sources externes,
**afin de** mettre à jour ses informations (éditeur, description, couverture).

**Critères d'acceptation :**
- [ ] Un bouton "Rafraîchir" est disponible sur la page de détail du magazine
- [ ] Le rafraîchissement interroge toutes les sources de métadonnées configurées
- [ ] Les nouvelles informations remplacent les anciennes (sauf le titre)
- [ ] Si les sources sont indisponibles, un message informe l'utilisateur sans perdre les données existantes

#### US-008 : Ajouter un magazine manuellement

**En tant qu'** utilisateur,
**je veux** ajouter un magazine qui n'apparaît dans aucune source de métadonnées,
**afin de** pouvoir surveiller des magazines rares ou locaux.

**Critères d'acceptation :**
- [ ] Un formulaire permet de saisir manuellement : titre, fréquence, dossier de destination
- [ ] Les champs optionnels sont : éditeur, pays, ISSN, description
- [ ] Le magazine est créé avec les mêmes fonctionnalités qu'un magazine trouvé via la recherche

### 3.2 Gestion des issues et fichiers

#### US-009 : Lister les issues d'un magazine

**En tant qu'** utilisateur,
**je veux** voir la liste des issues d'un magazine avec leur statut,
**afin de** savoir quels numéros je possède et lesquels sont manquants.

**Critères d'acceptation :**
- [ ] Les issues sont listées avec leur numéro, date de parution, et statut
- [ ] Les issues sont groupées par année
- [ ] Les statuts possibles sont : available (fichier présent), wanted (recherché activement), missing (manquant, non monitoré), downloading (en cours de téléchargement), snatched (envoyé au client), upcoming (prévu par le forecast), skipped (ignoré par l'utilisateur)
- [ ] Chaque statut a un badge de couleur distinct (vert, orange, rouge, bleu, violet, gris)

#### US-010 : Gérer le monitoring des issues

**En tant qu'** utilisateur,
**je veux** marquer des issues comme monitored ou non-monitored,
**afin de** contrôler précisément quels numéros je veux acquérir.

**Critères d'acceptation :**
- [ ] L'utilisateur peut changer le monitoring d'une issue individuellement
- [ ] L'utilisateur peut changer le monitoring de plusieurs issues en batch (sélection multiple)
- [ ] Une issue non-monitored n'est pas recherchée automatiquement
- [ ] Les boutons "Monitor All" et "Unmonitor All" sont disponibles au niveau du magazine

#### US-011 : Importer manuellement un fichier

**En tant qu'** utilisateur,
**je veux** importer manuellement un fichier magazine et le rattacher à une issue,
**afin de** ajouter des fichiers que je possède déjà en dehors du circuit de téléchargement.

**Critères d'acceptation :**
- [ ] L'utilisateur peut sélectionner un fichier depuis un chemin sur le serveur
- [ ] Le système propose un matching automatique avec les issues connues
- [ ] L'utilisateur peut confirmer ou corriger le matching proposé
- [ ] Le fichier est renommé et déplacé selon le template de nommage configuré

#### US-012 : Scanner un dossier existant

**En tant qu'** utilisateur,
**je veux** scanner le dossier d'un magazine pour détecter les fichiers déjà présents,
**afin de** synchroniser ma bibliothèque physique avec la base de données.

**Critères d'acceptation :**
- [ ] Le système scanne récursivement le dossier du magazine
- [ ] Les fichiers trouvés sont parsés (nom de fichier) pour extraire les informations
- [ ] Les fichiers sont matchés avec les issues connues quand possible
- [ ] Les fichiers non matchés sont signalés pour action manuelle
- [ ] Le scan ne déplace ni ne renomme aucun fichier (lecture seule)

#### US-013 : Renommer les fichiers existants

**En tant qu'** utilisateur,
**je veux** renommer et réorganiser les fichiers d'un magazine selon le template configuré,
**afin de** uniformiser le nommage de ma bibliothèque.

**Critères d'acceptation :**
- [ ] Un bouton "Renommer" est disponible au niveau du magazine (renomme toutes les issues)
- [ ] Un aperçu des changements est affiché avant confirmation
- [ ] L'utilisateur confirme explicitement avant tout renommage
- [ ] Les fichiers sont renommés et déplacés selon le template en vigueur

#### US-014 : Supprimer un fichier d'issue

**En tant qu'** utilisateur,
**je veux** supprimer le fichier associé à une issue,
**afin de** libérer de l'espace disque pour un numéro que je ne veux plus garder.

**Critères d'acceptation :**
- [ ] Une confirmation est demandée avant la suppression
- [ ] Le fichier est supprimé du disque
- [ ] L'issue repasse au statut "missing" ou "wanted" selon son monitoring
- [ ] Les métadonnées de l'issue sont conservées en base

#### US-015 : Voir les détails d'un fichier

**En tant qu'** utilisateur,
**je veux** voir les détails d'un fichier rattaché à une issue,
**afin de** connaître sa qualité et ses caractéristiques.

**Critères d'acceptation :**
- [ ] Les informations affichées incluent : taille, format (PDF/EPUB/CBR/CBZ), qualité détectée, date d'import, chemin complet
- [ ] Si le fichier est un PDF, la couverture extraite est affichée

#### US-016 : Gérer les hors-séries

**En tant qu'** utilisateur,
**je veux** pouvoir ajouter et gérer des hors-séries pour un magazine,
**afin de** suivre les numéros spéciaux hors numérotation normale.

**Critères d'acceptation :**
- [ ] Une issue peut être marquée comme "hors-série"
- [ ] Les hors-séries sont visuellement distingués des numéros réguliers
- [ ] Les hors-séries ne sont pas pris en compte dans le forecast de parution
- [ ] Les hors-séries participent aux compteurs de complétude du magazine

### 3.3 Recherche et téléchargement

#### US-017 : Configurer la connexion à Prowlarr

**En tant qu'** administrateur,
**je veux** configurer la connexion à mon instance Prowlarr,
**afin de** permettre à Pressarr de rechercher des magazines sur mes indexeurs.

**Critères d'acceptation :**
- [ ] Le formulaire demande : URL de Prowlarr, clé API
- [ ] Un bouton "Test" vérifie la connexion et affiche succès ou erreur détaillée
- [ ] La catégorie de recherche par défaut est "Magazines" (catégorie 7020)
- [ ] La configuration est persistée et utilisée pour toutes les recherches

#### US-018 : Rechercher manuellement une issue

**En tant qu'** utilisateur,
**je veux** rechercher manuellement une issue spécifique sur les indexeurs,
**afin de** trouver un numéro précis quand la recherche automatique n'a pas abouti.

**Critères d'acceptation :**
- [ ] Un bouton "Rechercher" est disponible au niveau de chaque issue
- [ ] Les résultats sont classés par score de pertinence décroissant
- [ ] Chaque résultat affiche : titre, taille, qualité détectée, nombre de seeds/peers (torrent) ou âge (usenet), nom de l'indexeur, score
- [ ] L'utilisateur peut grabber manuellement une release spécifique

#### US-019 : Rechercher automatiquement les issues manquantes

**En tant qu'** utilisateur,
**je veux** lancer une recherche automatique pour toutes les issues manquantes d'un magazine,
**afin de** remplir ma collection en un clic.

**Critères d'acceptation :**
- [ ] Un bouton "Rechercher les manquants" est disponible au niveau du magazine
- [ ] Le système recherche chaque issue monitored ayant le statut "wanted" ou "missing"
- [ ] Les meilleures releases sont automatiquement grabbées selon le profil de qualité
- [ ] Un résumé des actions effectuées est affiché à la fin

#### US-020 : Le système synchronise les flux RSS

**En tant que** système,
**je veux** vérifier les flux RSS des indexeurs à intervalles réguliers,
**afin de** détecter les nouvelles releases de magazines dès leur publication.

**Critères d'acceptation :**
- [ ] Le système interroge Prowlarr pour les nouvelles releases toutes les 30 minutes (configurable)
- [ ] Les releases matchant des issues monitored sont automatiquement évaluées
- [ ] La meilleure release (selon le score et le profil qualité) est automatiquement grabbée
- [ ] Si aucune release ne satisfait le profil qualité minimum, aucune action n'est prise
- [ ] Les releases déjà évaluées ne sont pas re-traitées

#### US-021 : Grabber une release manuellement

**En tant qu'** utilisateur,
**je veux** choisir et grabber manuellement une release parmi les résultats de recherche,
**afin de** forcer le téléchargement d'une version spécifique.

**Critères d'acceptation :**
- [ ] Le grab envoie la release au client de téléchargement configuré
- [ ] L'issue passe au statut "snatched"
- [ ] Une notification est envoyée si configurée
- [ ] Si le client de téléchargement est indisponible, un message d'erreur explicite est affiché

#### US-022 : Configurer un client de téléchargement

**En tant qu'** administrateur,
**je veux** configurer un ou plusieurs clients de téléchargement,
**afin de** permettre à Pressarr d'envoyer et suivre les téléchargements.

**Critères d'acceptation :**
- [ ] Les clients supportés sont : Deluge, qBittorrent, Transmission (torrents), SABnzbd, NZBGet (usenet)
- [ ] Le formulaire demande : type, nom, URL, identifiants, catégorie/label
- [ ] Un bouton "Test" vérifie la connexion
- [ ] Plusieurs clients peuvent être configurés, un est marqué "par défaut" par protocole (torrent/usenet)
- [ ] La catégorie/label par défaut est "pressarr"

#### US-023 : Suivre la progression d'un téléchargement

**En tant qu'** utilisateur,
**je veux** suivre la progression d'un téléchargement en temps réel,
**afin de** savoir quand mes fichiers seront prêts.

**Critères d'acceptation :**
- [ ] La file d'attente affiche pour chaque téléchargement : nom, progression (%), vitesse, temps restant estimé, statut
- [ ] Les informations se mettent à jour sans rechargement de page
- [ ] Le polling du client de téléchargement se fait toutes les 5 secondes quand la page queue est visible

#### US-024 : Annuler un téléchargement

**En tant qu'** utilisateur,
**je veux** annuler un téléchargement en cours,
**afin de** libérer de la bande passante ou corriger une erreur.

**Critères d'acceptation :**
- [ ] Un bouton d'annulation est disponible pour chaque téléchargement actif
- [ ] L'annulation supprime le téléchargement du client externe
- [ ] L'issue repasse au statut "wanted"
- [ ] L'utilisateur peut optionnellement ajouter la release à la blocklist

#### US-025 : Le système importe automatiquement les fichiers terminés

**En tant que** système,
**je veux** détecter automatiquement la fin d'un téléchargement et lancer l'import,
**afin de** ranger les fichiers dans la bibliothèque sans intervention humaine.

**Critères d'acceptation :**
- [ ] Le système vérifie l'état des téléchargements toutes les 30 secondes
- [ ] Quand un téléchargement est terminé, le pipeline d'import se déclenche automatiquement
- [ ] Si l'import réussit, l'issue passe au statut "available"
- [ ] Si l'import échoue, l'erreur est loguée et une notification est envoyée

#### US-026 : Configurer le scoring de recherche

**En tant qu'** administrateur,
**je veux** comprendre comment les résultats de recherche sont classés,
**afin de** m'assurer que le système choisit les meilleures releases.

**Critères d'acceptation :**
- [ ] Le score prend en compte : correspondance du titre, qualité vs profil, taille du fichier, nombre de seeds (torrent) ou âge (usenet), préférence de langue
- [ ] Le scoring est déterministe (même entrée = même score)
- [ ] Les releases en blocklist sont exclues des résultats

### 3.4 Pipeline d'import post-téléchargement

#### US-027 : Le système parse les noms de fichiers

**En tant que** système,
**je veux** analyser le nom d'un fichier téléchargé pour en extraire les informations,
**afin de** l'associer automatiquement à la bonne issue.

**Critères d'acceptation :**
- [ ] Le parser extrait : titre du magazine, numéro, volume, date (mois + année), langue, qualité, format, flag hors-série, groupe de release
- [ ] Le parser gère les séparateurs multiples : points, espaces, underscores, tirets
- [ ] Le parser reconnaît les mois en français, anglais, allemand, espagnol et italien
- [ ] Le parser gère le format "Science.et.Vie.N1285.Mars.2025.FRENCH.PDF" et les variantes courantes

#### US-028 : Le système matche les fichiers avec les issues

**En tant que** système,
**je veux** associer un fichier parsé avec l'issue correspondante dans la base,
**afin de** lier le fichier physique à l'entrée de la bibliothèque.

**Critères d'acceptation :**
- [ ] Le matching utilise une correspondance fuzzy sur le titre du magazine
- [ ] Le matching utilise le numéro et/ou la date de parution pour identifier l'issue
- [ ] Si plusieurs issues matchent, la meilleure correspondance est choisie
- [ ] Si aucune issue ne matche, le fichier est signalé pour traitement manuel

#### US-029 : Le système renomme et déplace les fichiers

**En tant que** système,
**je veux** renommer et déplacer le fichier importé selon le template configuré,
**afin de** maintenir une organisation cohérente de la bibliothèque.

**Critères d'acceptation :**
- [ ] Le fichier est renommé selon le template de nommage configuré
- [ ] Le fichier est déplacé du dossier de téléchargement vers le dossier bibliothèque du magazine
- [ ] Si le dossier de destination n'existe pas, il est créé automatiquement
- [ ] Les permissions du fichier sont préservées

#### US-030 : Le système extrait les couvertures

**En tant que** système,
**je veux** extraire la couverture d'un fichier PDF importé,
**afin de** l'afficher dans l'interface.

**Critères d'acceptation :**
- [ ] La première page du PDF est convertie en image JPEG
- [ ] L'image est redimensionnée à un maximum de 500px de large
- [ ] L'image est stockée localement dans le dossier de configuration
- [ ] Si l'extraction échoue (PDF corrompu, non-PDF), un placeholder est utilisé

#### US-031 : Le système notifie après import

**En tant que** système,
**je veux** envoyer une notification après chaque import réussi,
**afin d'** informer l'utilisateur que sa collection a été mise à jour.

**Critères d'acceptation :**
- [ ] Les notifications configurées sont envoyées pour l'événement "import"
- [ ] La notification inclut : titre du magazine, numéro de l'issue, qualité du fichier
- [ ] Si la couverture est disponible, elle est incluse dans la notification (quand le canal le supporte)

#### US-032 : Le système gère le template de nommage

**En tant qu'** administrateur,
**je veux** configurer le template de nommage des fichiers,
**afin de** définir comment les fichiers sont renommés à l'import.

**Critères d'acceptation :**
- [ ] Le template utilise des variables : {titre_magazine}, {numero}, {annee}, {mois}, {qualite}, {format}
- [ ] Un template par défaut est fourni : `{titre_magazine} - N{numero} ({annee}-{mois}).{format}`
- [ ] Un aperçu en temps réel montre un exemple de renommage avec le template actuel
- [ ] Le template est validé (pas de caractères interdits pour le filesystem)

### 3.5 Calendar et prévisions

#### US-033 : Voir le calendrier

**En tant qu'** utilisateur,
**je veux** voir un calendrier mensuel avec les issues connues et les prévisions,
**afin de** planifier mes acquisitions et anticiper les parutions.

**Critères d'acceptation :**
- [ ] Le calendrier affiche un mois complet avec navigation mois précédent/suivant
- [ ] Les issues confirmées (existantes en base) sont affichées avec un style solide
- [ ] Les prévisions (issues futures estimées) sont affichées avec un style pointillé/dashed
- [ ] Chaque entrée affiche le titre du magazine et la couverture miniature
- [ ] L'utilisateur peut cliquer sur une entrée pour accéder au détail de l'issue

#### US-034 : Le système génère les prévisions

**En tant que** système,
**je veux** générer automatiquement des prévisions de parution pour les 6 prochains mois,
**afin de** remplir le calendrier et anticiper les recherches.

**Critères d'acceptation :**
- [ ] Les prévisions sont basées sur la fréquence du magazine et la date de la dernière issue connue
- [ ] Les fréquences supportées sont : weekly, biweekly, monthly, bimonthly, quarterly, semiannual, annual
- [ ] Les prévisions sont recalculées quand une nouvelle issue est importée
- [ ] Les prévisions déjà passées mais non satisfaites sont marquées "delayed" après 7 jours

#### US-035 : Réconcilier prévisions et issues réelles

**En tant que** système,
**je veux** réconcilier automatiquement les prévisions avec les issues réellement téléchargées,
**afin de** garder le calendrier à jour et précis.

**Critères d'acceptation :**
- [ ] Quand une issue est importée, la prévision correspondante est automatiquement remplacée
- [ ] La correspondance se fait sur le numéro et/ou la date de parution (fenêtre de +/- 7 jours)
- [ ] Les prévisions non réconciliées restent visibles comme "manquantes" après leur date estimée

#### US-036 : Skipper une prévision

**En tant qu'** utilisateur,
**je veux** ignorer une prévision spécifique,
**afin de** marquer un numéro que je ne souhaite pas acquérir.

**Critères d'acceptation :**
- [ ] Un bouton "Skip" est disponible sur chaque prévision du calendrier
- [ ] La prévision skippée passe au statut "skipped" (badge gris)
- [ ] Une prévision skippée n'est pas recherchée automatiquement

#### US-037 : Magazines à fréquence irrégulière

**En tant qu'** utilisateur,
**je veux** que les magazines à fréquence "irregular" soient gérés correctement,
**afin de** ne pas avoir de fausses prévisions.

**Critères d'acceptation :**
- [ ] Aucune prévision n'est générée pour les magazines "irregular"
- [ ] Le calendrier n'affiche que les issues confirmées pour ces magazines
- [ ] Le monitoring et la recherche manuelle restent disponibles

#### US-038 : Vue agenda du calendrier

**En tant qu'** utilisateur,
**je veux** voir une vue agenda (liste chronologique) en plus de la vue calendrier,
**afin de** consulter rapidement les prochaines parutions.

**Critères d'acceptation :**
- [ ] La vue agenda liste les issues et prévisions par date croissante
- [ ] Le switch entre vue calendrier et vue agenda est disponible
- [ ] Les filtres (par magazine, par statut) s'appliquent aux deux vues

### 3.6 Internet Archive comme source de téléchargement

#### US-039 : Chercher sur Internet Archive

**En tant qu'** utilisateur,
**je veux** chercher des issues de magazines sur la collection Magazine Rack d'Internet Archive,
**afin de** trouver des numéros anciens ou rares en téléchargement direct gratuit.

**Critères d'acceptation :**
- [ ] Un bouton "Rechercher sur Internet Archive" est disponible au niveau d'une issue ou d'un magazine
- [ ] La recherche interroge la collection "magazinerack" d'Internet Archive
- [ ] Les résultats affichent : titre, date, format, taille
- [ ] Le rate limiting est respecté (maximum 1 requête par seconde vers IA)

#### US-040 : Matching automatique IA

**En tant que** système,
**je veux** matcher automatiquement les résultats Internet Archive avec les issues manquantes,
**afin de** proposer des téléchargements pour les numéros recherchés.

**Critères d'acceptation :**
- [ ] Le système compare les résultats IA avec les issues monitored en statut "wanted"
- [ ] Le matching utilise le titre du magazine et la date/numéro de l'issue
- [ ] Les résultats matchés sont proposés à l'utilisateur ou grabbés automatiquement selon la configuration

#### US-041 : Télécharger depuis Internet Archive

**En tant qu'** utilisateur,
**je veux** télécharger directement un fichier depuis Internet Archive,
**afin de** ne pas avoir besoin d'un client de téléchargement externe pour ces fichiers.

**Critères d'acceptation :**
- [ ] Le téléchargement est effectué directement par Pressarr (pas de client externe)
- [ ] La progression du téléchargement est visible dans la file d'attente
- [ ] Le fichier téléchargé passe par le pipeline d'import standard (parsing, matching, renommage)
- [ ] Le rate limiting Internet Archive est respecté pendant le téléchargement

#### US-042 : Configurer Internet Archive

**En tant qu'** administrateur,
**je veux** activer ou désactiver Internet Archive comme source,
**afin de** contrôler si Pressarr utilise cette source.

**Critères d'acceptation :**
- [ ] Un toggle permet d'activer/désactiver Internet Archive dans les paramètres de métadonnées
- [ ] Quand désactivé, aucune recherche n'est effectuée vers Internet Archive
- [ ] Par défaut, Internet Archive est activé

### 3.7 Profils de qualité

#### US-043 : Créer un profil de qualité

**En tant qu'** administrateur,
**je veux** créer un profil de qualité définissant les niveaux acceptables,
**afin de** contrôler la qualité des fichiers téléchargés.

**Critères d'acceptation :**
- [ ] Le profil a un nom et une liste ordonnée de niveaux de qualité
- [ ] Les niveaux prédéfinis sont : Unknown, Scan, PDF-LQ, PDF-HQ, Retail, TruePDF
- [ ] L'ordre définit la hiérarchie (TruePDF > Retail > PDF-HQ > Scan, etc.)
- [ ] Un profil par défaut est fourni à l'installation

#### US-044 : Définir un cutoff de qualité

**En tant qu'** administrateur,
**je veux** définir un seuil (cutoff) dans le profil de qualité,
**afin d'** arrêter de chercher mieux une fois qu'un fichier atteint ce seuil.

**Critères d'acceptation :**
- [ ] Le cutoff est un niveau de qualité dans la hiérarchie
- [ ] Une fois qu'un fichier atteint ou dépasse le cutoff, le système arrête de chercher des upgrades pour cette issue
- [ ] Le cutoff peut être modifié à tout moment

#### US-045 : Le scoring intègre la qualité

**En tant que** système,
**je veux** intégrer le profil de qualité du magazine dans le calcul du score de recherche,
**afin de** favoriser les releases de meilleure qualité.

**Critères d'acceptation :**
- [ ] Les releases dont la qualité est en dessous du minimum du profil sont exclues
- [ ] Les releases de meilleure qualité reçoivent un score plus élevé
- [ ] Les releases au-dessus du cutoff ne sont pas prises en compte si un fichier au cutoff existe déjà

#### US-046 : Upgrade automatique de qualité

**En tant que** système,
**je veux** remplacer automatiquement un fichier par une version de meilleure qualité,
**afin de** toujours avoir la meilleure version disponible dans la bibliothèque.

**Critères d'acceptation :**
- [ ] Quand une release de meilleure qualité est trouvée pour une issue dont le fichier est sous le cutoff, le système la grabbe
- [ ] L'ancien fichier est remplacé par le nouveau après import réussi
- [ ] L'ancien fichier est supprimé définitivement
- [ ] Une notification est envoyée pour l'upgrade

#### US-047 : Gérer les profils de qualité

**En tant qu'** administrateur,
**je veux** modifier et supprimer des profils de qualité,
**afin de** adapter les critères au fil du temps.

**Critères d'acceptation :**
- [ ] Un profil peut être modifié (réordonner les niveaux, changer le cutoff)
- [ ] Un profil ne peut pas être supprimé s'il est utilisé par au moins un magazine
- [ ] Le profil par défaut ne peut pas être supprimé (mais peut être modifié)

### 3.8 Notifications

#### US-048 : Configurer une notification Discord

**En tant qu'** administrateur,
**je veux** configurer un webhook Discord,
**afin de** recevoir des notifications dans un canal Discord.

**Critères d'acceptation :**
- [ ] Le formulaire demande : URL du webhook, nom (optionnel)
- [ ] Un bouton "Test" envoie une notification de test
- [ ] Les notifications incluent un embed avec couverture quand disponible

#### US-049 : Configurer une notification Gotify

**En tant qu'** administrateur,
**je veux** configurer un serveur Gotify,
**afin de** recevoir des notifications push sur mes appareils.

**Critères d'acceptation :**
- [ ] Le formulaire demande : URL du serveur, token d'application, priorité
- [ ] Un bouton "Test" envoie une notification de test

#### US-050 : Configurer une notification Telegram

**En tant qu'** administrateur,
**je veux** configurer un bot Telegram,
**afin de** recevoir des notifications via Telegram.

**Critères d'acceptation :**
- [ ] Le formulaire demande : token du bot, chat ID
- [ ] Un bouton "Test" envoie une notification de test
- [ ] Les notifications incluent la couverture quand disponible (envoi d'image)

#### US-051 : Configurer un webhook générique

**En tant qu'** administrateur,
**je veux** configurer un webhook HTTP générique,
**afin d'** intégrer Pressarr avec n'importe quel service externe.

**Critères d'acceptation :**
- [ ] Le formulaire demande : URL, méthode HTTP (POST/PUT), headers custom (optionnels)
- [ ] Le payload est envoyé en JSON avec toutes les informations de l'événement
- [ ] Un bouton "Test" envoie un événement de test

#### US-052 : Choisir les événements de notification

**En tant qu'** administrateur,
**je veux** choisir quels événements déclenchent chaque notification,
**afin de** ne recevoir que les alertes pertinentes.

**Critères d'acceptation :**
- [ ] Les événements disponibles sont : grab (release envoyée au client), download (téléchargement terminé), import (fichier importé dans la bibliothèque), upgrade (fichier remplacé par meilleure qualité), error (erreur système)
- [ ] Chaque canal de notification peut activer/désactiver chaque événement indépendamment
- [ ] Par défaut, tous les événements sont activés pour un nouveau canal

### 3.9 Activité et historique

#### US-053 : Voir la file d'attente (queue)

**En tant qu'** utilisateur,
**je veux** voir la file d'attente des téléchargements en temps réel,
**afin de** suivre l'avancement de mes acquisitions.

**Critères d'acceptation :**
- [ ] La page affiche tous les téléchargements actifs et en attente
- [ ] Chaque entrée affiche : nom du magazine, numéro, statut, progression, vitesse, ETA
- [ ] La page se met à jour automatiquement sans rechargement (via WebSocket ou polling)
- [ ] Les actions disponibles sont : annuler, supprimer, ajouter à la blocklist

#### US-054 : Voir l'historique des événements

**En tant qu'** utilisateur,
**je veux** consulter l'historique de tous les événements passés,
**afin de** comprendre ce qui s'est passé et diagnostiquer des problèmes.

**Critères d'acceptation :**
- [ ] L'historique affiche : date, type d'événement, magazine, issue, détails
- [ ] Les types d'événements sont : grab, download, import, upgrade, rename, delete, error
- [ ] L'historique est filtrable par magazine, par type d'événement, et par période
- [ ] L'historique est paginé pour les grandes collections

#### US-055 : Gérer la blocklist

**En tant qu'** utilisateur,
**je veux** voir et gérer les releases en blocklist,
**afin de** débloquer des releases bloquées par erreur.

**Critères d'acceptation :**
- [ ] La page blocklist affiche toutes les releases bloquées avec leur motif
- [ ] L'utilisateur peut supprimer une entrée de la blocklist (déblocage)
- [ ] Une release en blocklist n'est jamais re-téléchargée automatiquement
- [ ] La blocklist est consultable depuis la page de résultats de recherche (indicateur visuel)

#### US-056 : Actions en masse sur la queue

**En tant qu'** utilisateur,
**je veux** effectuer des actions en masse sur la file d'attente,
**afin de** gérer efficacement plusieurs téléchargements.

**Critères d'acceptation :**
- [ ] L'utilisateur peut sélectionner plusieurs entrées de la queue
- [ ] Les actions de masse disponibles sont : annuler tout, supprimer tout
- [ ] Les actions prennent effet immédiatement sur le client de téléchargement

#### US-057 : L'historique est purgé automatiquement

**En tant que** système,
**je veux** purger automatiquement les entrées d'historique anciennes,
**afin de** ne pas faire croître la base de données indéfiniment.

**Critères d'acceptation :**
- [ ] Les entrées de plus de 365 jours sont supprimées automatiquement
- [ ] La rétention est configurable dans les paramètres
- [ ] La purge s'exécute une fois par jour

### 3.10 Configuration

#### US-058 : Configurer le template de nommage

**En tant qu'** administrateur,
**je veux** définir le template de nommage des fichiers importés,
**afin de** contrôler la convention de nommage de ma bibliothèque.

**Critères d'acceptation :**
- [ ] Les variables disponibles incluent : {titre_magazine}, {numero}, {volume}, {annee}, {mois}, {qualite}, {format}, {groupe}
- [ ] Un aperçu montre un exemple concret avec le template actuel
- [ ] Le template est validé (caractères interdits, longueur max)
- [ ] Un template par défaut est fourni

#### US-059 : Gérer les dossiers racine

**En tant qu'** administrateur,
**je veux** gérer les dossiers racine de la bibliothèque,
**afin de** définir où les magazines sont stockés.

**Critères d'acceptation :**
- [ ] L'utilisateur peut ajouter un ou plusieurs dossiers racine
- [ ] L'espace libre de chaque dossier racine est affiché
- [ ] Un dossier racine ne peut pas être supprimé s'il contient des magazines
- [ ] Le dossier racine par défaut est configurable

#### US-060 : Configurer les sources de métadonnées

**En tant qu'** administrateur,
**je veux** configurer les sources de métadonnées,
**afin de** contrôler d'où proviennent les informations des magazines.

**Critères d'acceptation :**
- [ ] Les sources configurables sont : Google Books (clé API), Internet Archive (toggle on/off)
- [ ] Chaque source peut être activée/désactivée indépendamment
- [ ] Un bouton "Test" est disponible pour chaque source
- [ ] Si aucune source n'est configurée, seul l'ajout manuel est possible

#### US-061 : Configurer les paramètres généraux

**En tant qu'** administrateur,
**je veux** configurer les paramètres généraux de Pressarr,
**afin de** personnaliser le comportement global de l'application.

**Critères d'acceptation :**
- [ ] Les paramètres incluent : port d'écoute, niveau de log, activation de l'authentification
- [ ] Un changement de port nécessite un redémarrage (message affiché)
- [ ] Le niveau de log est applicable immédiatement (debug, info, warning, error)

#### US-062 : Configurer l'authentification

**En tant qu'** administrateur,
**je veux** activer l'authentification par clé API,
**afin de** protéger l'accès à mon instance Pressarr.

**Critères d'acceptation :**
- [ ] L'authentification est désactivée par défaut (accès libre)
- [ ] Quand activée, toutes les requêtes API nécessitent un header X-Api-Key valide
- [ ] L'interface web gère automatiquement l'authentification (saisie unique de la clé)
- [ ] L'endpoint de health check reste accessible sans authentification
- [ ] La clé API est auto-générée au premier démarrage et affichée dans les logs

#### US-063 : Configurer les intervalles des tâches planifiées

**En tant qu'** administrateur,
**je veux** configurer la fréquence des tâches automatiques,
**afin d'** adapter le comportement à mes besoins et aux ressources de mon serveur.

**Critères d'acceptation :**
- [ ] Les tâches configurables sont : synchronisation RSS (défaut 30 min), vérification des téléchargements (défaut 30 sec), rafraîchissement des métadonnées (défaut 24h), nettoyage de l'historique (défaut 24h)
- [ ] Les intervalles sont configurables dans les paramètres
- [ ] Les modifications prennent effet sans redémarrage

#### US-064 : Exporter/importer la configuration

**En tant qu'** administrateur,
**je veux** pouvoir sauvegarder et restaurer la configuration de Pressarr,
**afin de** faciliter la migration ou la reconstruction d'une instance.

**Critères d'acceptation :**
- [ ] La configuration complète est stockée dans un fichier lisible dans le dossier /config
- [ ] La configuration inclut : connexions, profils de qualité, templates, préférences
- [ ] Les secrets (clés API, mots de passe) sont stockés dans le fichier de configuration (pas en clair dans les logs)

#### US-065 : Page "Système" avec état de santé

**En tant qu'** administrateur,
**je veux** voir une page système affichant l'état de santé de Pressarr,
**afin de** diagnostiquer les problèmes de connexion ou de configuration.

**Critères d'acceptation :**
- [ ] La page affiche : version de Pressarr, uptime, état des connexions (Prowlarr, clients de téléchargement, sources de métadonnées)
- [ ] Chaque connexion affiche un indicateur vert (OK) ou rouge (erreur) avec le message d'erreur
- [ ] Les statistiques globales sont affichées : nombre de magazines, issues totales, issues disponibles, espace disque utilisé

### 3.11 Parsing de noms de fichiers

#### US-066 : Parser les formats courants

**En tant que** système,
**je veux** reconnaître les formats de noms de fichiers magazines les plus courants,
**afin de** pouvoir importer automatiquement les fichiers téléchargés.

**Critères d'acceptation :**
- [ ] Le parser reconnaît au minimum les patterns suivants :
  - `Science.et.Vie.N1285.Mars.2025.FRENCH.PDF`
  - `National Geographic - 2025-03 (March).pdf`
  - `Le_Monde_Diplomatique_N845_Fevrier_2025_FRENCH_TruePDF.pdf`
  - `Time Magazine Issue 12 2025.epub`
  - `Hors-Serie.Science.et.Vie.HS42.2025.pdf`
- [ ] Le parser gère les séparateurs : points, espaces, underscores, tirets
- [ ] Le parser est insensible à la casse

#### US-067 : Extraire les informations du nom de fichier

**En tant que** système,
**je veux** extraire les informations structurées d'un nom de fichier,
**afin de** les utiliser pour le matching et le renommage.

**Critères d'acceptation :**
- [ ] Les informations extraites sont : titre du magazine, numéro, volume, date (mois + année), langue, qualité (TruePDF, Retail, Scan, etc.), format (PDF, EPUB, CBR, CBZ), flag hors-série, groupe de release
- [ ] Les mois sont reconnus en français, anglais, allemand, espagnol et italien
- [ ] Les champs non trouvés sont marqués comme "unknown" (pas d'erreur)

#### US-068 : Matcher par fuzzy matching

**En tant que** système,
**je veux** faire un matching approximatif entre le titre parsé et les magazines connus,
**afin de** tolérer les variations de nommage entre indexeurs.

**Critères d'acceptation :**
- [ ] Le matching tolère : accents manquants, articles omis ("Le", "The"), abréviations courantes
- [ ] Un seuil de confiance est appliqué (minimum 80% de similarité)
- [ ] Si le seuil n'est pas atteint, le fichier est signalé pour matching manuel
- [ ] "Science et Vie" matche "Science & Vie" et "Science.et.Vie"

#### US-069 : Le parser a une suite de tests exhaustive

**En tant qu'** administrateur,
**je veux** que le parser soit fiable et bien testé,
**afin de** m'assurer que les imports automatiques fonctionnent correctement.

**Critères d'acceptation :**
- [ ] Le parser dispose d'au minimum 25 cas de test couvrant tous les patterns supportés
- [ ] Les cas de test couvrent : formats variés, langues multiples, numérotations différentes, hors-séries, cas limites (numéros doubles, numéros spéciaux)

### 3.12 Compatibilité écosystème

#### US-070 : API compatible widgets

**En tant que** dashboard externe,
**je veux** interroger l'API de Pressarr dans un format compatible Homepage/Homarr,
**afin d'** afficher un widget Pressarr sur mon tableau de bord.

**Critères d'acceptation :**
- [ ] L'endpoint de statut retourne : version, nombre de magazines, nombre d'issues manquantes, nombre de téléchargements en cours
- [ ] Le format de réponse suit les conventions Sonarr/Radarr (camelCase, mêmes champs de base)
- [ ] L'endpoint de statut est accessible sans authentification (pour les health checks)

#### US-071 : API documentée automatiquement

**En tant qu'** administrateur,
**je veux** accéder à la documentation API via le navigateur,
**afin de** comprendre les endpoints disponibles et les utiliser dans mes scripts.

**Critères d'acceptation :**
- [ ] La documentation OpenAPI/Swagger est accessible à l'URL /api/docs
- [ ] Tous les endpoints sont documentés avec leurs paramètres et exemples de réponses
- [ ] La documentation est générée automatiquement depuis le code (pas de maintenance manuelle)

#### US-072 : Image Docker standalone

**En tant qu'** administrateur,
**je veux** déployer Pressarr via une image Docker unique,
**afin de** l'installer facilement sur mon NAS.

**Critères d'acceptation :**
- [ ] L'image Docker contient le backend et le frontend (standalone)
- [ ] L'image supporte les architectures amd64 et arm64
- [ ] Les volumes Docker suivent les conventions *arr : /config, /magazines, /downloads
- [ ] Le premier démarrage fonctionne sans aucune configuration (zero-config)
- [ ] L'image est compatible Unraid Community Applications

#### US-073 : Premier démarrage sans configuration

**En tant qu'** utilisateur,
**je veux** que Pressarr démarre et soit fonctionnel dès la première exécution,
**afin de** ne pas avoir à configurer avant de pouvoir explorer l'interface.

**Critères d'acceptation :**
- [ ] La base de données est créée automatiquement au premier démarrage
- [ ] La clé API est auto-générée
- [ ] Le fichier de configuration par défaut est créé
- [ ] Les migrations de base de données s'exécutent automatiquement
- [ ] L'interface web est accessible immédiatement sur le port par défaut (8585)

## 4. Functional Requirements

### 4.1 Gestion des magazines

- **FR-001 : CRUD Magazine** — Le système DOIT permettre de créer, lire, mettre à jour et supprimer des magazines via l'API et l'interface web. L'ajout DOIT être possible via la recherche de métadonnées ou manuellement.
- **FR-002 : Recherche de métadonnées** — Le système DOIT interroger les sources de métadonnées configurées (Google Books, Internet Archive) pour trouver des magazines par titre, et agréger les résultats dédupliqués. Lors de l'ajout d'un magazine, le système DOIT récupérer la liste des issues connues depuis ces sources pour peupler la bibliothèque initiale. Cette liste est ensuite complétée progressivement par les découvertes RSS et les recherches manuelles. Le ISSN Portal est hors scope v1.0.
- **FR-003 : Unicité des magazines** — Le système DOIT empêcher l'ajout d'un magazine déjà présent dans la bibliothèque, basé sur le titre normalisé + ISSN quand disponible.
- **FR-004 : Paramètres par magazine** — Chaque magazine DOIT avoir ses propres paramètres configurables : dossier de destination, profil de qualité, fréquence de publication, état de monitoring, date de début de monitoring, termes de recherche. Seules les issues à partir de la date de début de monitoring sont marquées "wanted" ; les issues antérieures restent "missing".
- **FR-005 : Compteurs de statut** — La réponse API d'un magazine DOIT inclure les compteurs : issues totales, issues disponibles, issues manquantes.
- **FR-006 : Couvertures locales** — Le système DOIT stocker localement les couvertures des magazines et les servir via un endpoint dédié. Les couvertures manquantes DOIVENT afficher un placeholder avec le titre.

### 4.2 Gestion des issues et fichiers

- **FR-007 : CRUD Issue** — Le système DOIT permettre de créer, lire et modifier des issues pour chaque magazine. Les issues ont un numéro, une date de parution, un statut, et un flag hors-série.
- **FR-008 : Statuts d'issue** — Le système DOIT gérer les statuts : available, wanted, missing, downloading, snatched, upcoming, skipped. Les transitions de statut sont automatiques (sauf skip qui est manuel).
- **FR-009 : Association fichier-issue** — Le système DOIT associer un fichier physique à une issue. Une issue a au plus un fichier actif à un instant donné.
- **FR-010 : Scan de dossier** — Le système DOIT pouvoir scanner récursivement un dossier pour détecter les fichiers magazines existants et les matcher avec les issues connues.
- **FR-011 : Formats de fichiers supportés** — Le système DOIT supporter les formats : PDF, EPUB, CBR, CBZ.

### 4.3 Recherche et scoring

- **FR-012 : Intégration Prowlarr** — Le système DOIT communiquer avec Prowlarr pour les recherches d'indexeurs, en utilisant la catégorie 7020 (Magazines). Les connexions directes Newznab/Torznab sont hors scope v1.0 (Prowlarr uniquement).
- **FR-013 : Scoring de releases** — Le système DOIT scorer les releases selon : correspondance titre, qualité vs profil, taille, seeds/âge, langue. Le scoring DOIT être déterministe.
- **FR-014 : Synchronisation RSS** — Le système DOIT interroger les flux RSS via Prowlarr à intervalles configurables (défaut 30 min) pour détecter les nouvelles releases.
- **FR-015 : Auto-grab** — Le système DOIT grabber automatiquement la meilleure release pour les issues monitored quand une release satisfaisante est trouvée.
- **FR-016 : Blocklist** — Le système DOIT maintenir une blocklist de releases à ne jamais re-télécharger. Les releases en blocklist sont exclues du scoring.

### 4.4 Téléchargement et clients

- **FR-017 : Clients torrent** — Le système DOIT supporter les clients torrent : Deluge, qBittorrent, Transmission.
- **FR-018 : Clients usenet** — Le système DOIT supporter les clients usenet : SABnzbd, NZBGet.
- **FR-019 : Label/catégorie** — Le système DOIT utiliser le label "pressarr" dans tous les clients de téléchargement.
- **FR-020 : Monitoring des téléchargements** — Le système DOIT vérifier l'état des téléchargements à intervalles réguliers (défaut 30 sec) et détecter les téléchargements terminés.
- **FR-021 : Téléchargement direct Internet Archive** — Le système DOIT pouvoir télécharger directement depuis Internet Archive sans client externe, en respectant le rate limiting (1 req/sec).

### 4.5 Import post-téléchargement

- **FR-022 : Pipeline d'import** — Le système DOIT exécuter automatiquement la chaîne : détection → parsing → matching → renommage → déplacement → mise à jour base → notification.
- **FR-023 : Parsing de noms** — Le système DOIT parser les noms de fichiers pour extraire : titre, numéro, volume, date, langue, qualité, format, flag hors-série, groupe de release.
- **FR-024 : Matching fuzzy** — Le système DOIT matcher les titres parsés avec les magazines connus via un algorithme de similarité (seuil minimum 80%).
- **FR-025 : Template de renommage** — Le système DOIT renommer les fichiers selon un template configurable avec variables.
- **FR-026 : Extraction de couverture** — Le système DOIT extraire la première page d'un PDF comme couverture (JPEG, max 500px de large). L'échec d'extraction ne DOIT PAS bloquer l'import.

### 4.6 Calendar et prévisions

- **FR-027 : Génération de forecast** — Le système DOIT générer des prévisions de parution pour les 6 prochains mois basées sur la fréquence du magazine et la dernière issue connue.
- **FR-028 : Fréquences supportées** — Les fréquences supportées pour le forecast sont : weekly, biweekly, monthly, bimonthly, quarterly, semiannual, annual. Les magazines "irregular" ne génèrent PAS de prévisions.
- **FR-029 : Réconciliation** — Le système DOIT réconcilier automatiquement les prévisions avec les issues importées (fenêtre de +/- 7 jours sur la date estimée).
- **FR-030 : Prévisions retardées** — Les prévisions non satisfaites après 7 jours passé leur date estimée DOIVENT être marquées "delayed".

### 4.7 Internet Archive

- **FR-031 : Recherche Magazine Rack** — Le système DOIT pouvoir rechercher dans la collection "magazinerack" d'Internet Archive.
- **FR-032 : Rate limiting IA** — Le système DOIT respecter un maximum de 1 requête par seconde vers Internet Archive.
- **FR-033 : Téléchargement direct** — Les fichiers d'Internet Archive sont téléchargés directement par Pressarr et passent par le pipeline d'import standard.

### 4.8 Qualité

- **FR-034 : Hiérarchie de qualité** — Le système DOIT définir une hiérarchie ordonnée de niveaux de qualité : Unknown < Scan < PDF-LQ < PDF-HQ < Retail < TruePDF.
- **FR-035 : Cutoff** — Le système DOIT supporter un seuil (cutoff) par profil, au-delà duquel les upgrades ne sont plus recherchées.
- **FR-036 : Upgrade automatique** — Le système DOIT remplacer automatiquement un fichier par une version de meilleure qualité quand disponible et si le fichier actuel est sous le cutoff.

### 4.9 Notifications

- **FR-037 : Canaux supportés** — Le système DOIT supporter les canaux de notification : Discord (webhook), Gotify, Telegram (bot), webhook HTTP générique.
- **FR-038 : Événements de notification** — Les événements notifiables sont : grab, download, import, upgrade, error.
- **FR-039 : Payload de notification** — Chaque notification DOIT inclure au minimum : titre du magazine, numéro de l'issue, qualité du fichier. La couverture DOIT être incluse quand le canal le supporte.

### 4.10 Activité et historique

- **FR-040 : File d'attente temps réel** — Le système DOIT afficher la file d'attente de téléchargement avec mise à jour en temps réel (sans rechargement de page).
- **FR-041 : Historique persisté** — Le système DOIT persister l'historique de tous les événements (grab, download, import, upgrade, rename, delete, error) avec date, magazine, issue, et détails.
- **FR-042 : Rétention configurable** — L'historique DOIT être purgé automatiquement selon une période de rétention configurable (défaut 365 jours).

### 4.11 Configuration

- **FR-043 : Configuration hiérarchique** — La configuration DOIT être stockée dans un fichier lisible dans /config, avec possibilité de surcharger par variables d'environnement.
- **FR-044 : Authentification par API key** — Le système DOIT supporter l'authentification optionnelle par header X-Api-Key. L'endpoint de health check reste public.
- **FR-045 : Dossiers racine multiples** — Le système DOIT supporter plusieurs dossiers racine pour la bibliothèque de magazines.
- **FR-046 : Intervalles configurables** — Tous les intervalles de tâches planifiées DOIVENT être configurables.

### 4.12 Parsing

- **FR-047 : Multilingue** — Le parser DOIT reconnaître les noms de mois en français, anglais, allemand, espagnol et italien.
- **FR-048 : Hors-séries** — Le parser DOIT détecter les marqueurs de hors-série (HS, Hors-Serie, Special, etc.) dans les noms de fichiers.
- **FR-049 : Qualité dans le nom** — Le parser DOIT extraire les indicateurs de qualité (TruePDF, Retail, Scan, HQ, LQ, etc.) des noms de fichiers.
- **FR-050 : Robustesse** — Le parser DOIT retourner un résultat partiel plutôt qu'une erreur quand un nom de fichier n'est pas complètement reconnu.

### 4.13 Compatibilité écosystème

- **FR-051 : API RESTful *arr** — L'API DOIT suivre les conventions Sonarr/Radarr : /api/v1/{resource} au singulier, POST /api/v1/command pour les actions asynchrones, camelCase dans les réponses JSON.
- **FR-052 : Documentation OpenAPI** — L'API DOIT exposer une documentation OpenAPI/Swagger interactive à /api/docs.
- **FR-053 : Image Docker standalone** — L'image Docker DOIT contenir backend + frontend, supporter amd64 et arm64, et fonctionner avec les volumes standard : /config, /magazines, /downloads.
- **FR-054 : Zero-config** — Le premier démarrage DOIT fonctionner sans configuration : auto-création de la base de données, auto-génération de la clé API, migrations automatiques.

## 5. Non-Functional Requirements

- **NFR-001 : Temps de réponse API** — Les endpoints de lecture (GET) DOIVENT répondre en moins de 200ms pour les requêtes unitaires et moins de 500ms pour les listes de 200 éléments.
- **NFR-002 : Temps de démarrage** — L'application DOIT démarrer et être prête à servir des requêtes en moins de 10 secondes (incluant les migrations de base de données).
- **NFR-003 : Consommation mémoire** — L'application DOIT fonctionner avec moins de 256 Mo de RAM au repos et moins de 512 Mo sous charge (200 magazines, 10 000 issues).
- **NFR-004 : Résilience externe** — La panne d'un service externe (Prowlarr, client de téléchargement, source de métadonnées) ne DOIT JAMAIS provoquer un crash de Pressarr ni retourner une erreur 500 à l'utilisateur.
- **NFR-005 : Reprise après crash** — Après un redémarrage inattendu, le système DOIT reprendre son fonctionnement normal sans perte de données ni intervention manuelle.
- **NFR-006 : Compatibilité navigateurs** — L'interface web DOIT fonctionner sur les versions actuelles de Chrome, Firefox, Safari et Edge.
- **NFR-007 : Responsive design** — L'interface DOIT être utilisable sur desktop (>1024px), tablette (768-1024px) et mobile (<768px).
- **NFR-008 : Stockage maîtrisé** — La base de données DOIT rester sous 50 Mo pour 100 magazines et 10 000 issues. Les logs DOIVENT être rotationnés automatiquement (taille max configurable).
- **NFR-009 : Sécurité des secrets** — Les clés API, mots de passe et tokens ne DOIVENT JAMAIS apparaître dans les logs ni dans les réponses API.
- **NFR-010 : Pas de dépendance cloud** — L'application DOIT fonctionner entièrement en local/LAN sans aucun service cloud requis. Les sources de métadonnées externes sont optionnelles.
- **NFR-011 : Internationalisation de l'interface** — L'interface web DOIT supporter l'internationalisation (i18n) dès la v1.0. La langue par défaut est l'anglais. Le français DOIT être disponible comme langue alternative. L'utilisateur DOIT pouvoir changer de langue dans les paramètres.

## 6. Edge Cases & Error Handling

| # | Situation | Comportement attendu |
|---|-----------|---------------------|
| EC-001 | Prowlarr est indisponible | Log warning, les recherches retournent une erreur explicite à l'utilisateur ("Prowlarr non joignable"), les tâches RSS continuent de s'exécuter (elles seront simplement vides). Aucune erreur 500. |
| EC-002 | Client de téléchargement déconnecté | Log warning, les grabs échouent avec un message explicite ("Client X non joignable"), les téléchargements en cours ne sont plus suivis jusqu'à reconnexion. Le status de la connexion est visible dans la page Système. |
| EC-003 | Google Books API quota épuisé | Log warning, cette source est temporairement ignorée, les autres sources de métadonnées continuent de fonctionner. L'utilisateur est informé dans les résultats de recherche ("Google Books : quota épuisé"). |
| EC-004 | Internet Archive rate-limité (HTTP 429) | Backoff exponentiel (attente de 5s, 10s, 20s, maximum 3 tentatives). Si toujours en erreur, la source est marquée temporairement indisponible pour 5 minutes. |
| EC-005 | Fichier téléchargé ne matche aucune issue connue | Le fichier est déplacé vers un dossier "unmatched" dans /downloads. Un événement "unmatched import" est ajouté à l'historique. L'utilisateur peut matcher manuellement depuis l'interface. |
| EC-006 | Deux releases trouvées simultanément pour la même issue | Seule la release avec le meilleur score est grabbée. Si les scores sont identiques, la première trouvée est choisie. |
| EC-007 | Magazine avec fréquence "irregular" | Aucune prévision n'est générée. Le calendrier n'affiche que les issues confirmées. Le monitoring et la recherche manuelle restent opérationnels. |
| EC-008 | Fichier PDF corrompu (couverture non extractible) | L'import continue normalement. La couverture est marquée comme non disponible. Un placeholder avec le titre est affiché. Log warning avec le chemin du fichier. |
| EC-009 | Nom de fichier non reconnu par le parser | Un résultat partiel est retourné (les champs reconnus sont remplis, les autres marqués "unknown"). Le fichier est proposé pour matching manuel. |
| EC-010 | Espace disque insuffisant pour le déplacement | L'import échoue avec un message explicite ("Espace disque insuffisant sur {dossier}"). Le fichier reste dans le dossier de téléchargement. Une notification d'erreur est envoyée. L'import sera re-tenté au prochain cycle. |
| EC-011 | Deux magazines avec des noms très similaires | Le matching fuzzy propose les deux candidats avec leur score de confiance. L'utilisateur choisit manuellement si le seuil de confiance n'est pas atteint de manière nette (écart < 10% entre les deux meilleurs matchs). |
| EC-012 | Issue numérotée différemment selon les sources | Le système utilise la numérotation en base comme référence. Les correspondances alternatives (par date) sont utilisées en fallback quand le numéro ne matche pas. |
| EC-013 | Dossier de destination d'un magazine supprimé | Au prochain scan ou import, le dossier est recréé automatiquement. Un log warning est émis. |
| EC-014 | Migration de base de données échoue | Le démarrage est interrompu avec un message d'erreur explicite et un code de sortie non-zéro. Les données ne sont pas corrompues (la migration est transactionnelle). |
| EC-015 | Suppression de fichiers échoue (permissions) | L'entrée en base est supprimée. Les fichiers non supprimés sont loggés individuellement. L'utilisateur est informé de la liste des fichiers non supprimés. |

## 7. Out of Scope (v1.0)

- Lecteur de magazines intégré (visionneuse PDF/EPUB)
- Gestion de livres, ebooks ou audiobooks (voir Readarr/Calibre)
- Gestion de comics ou bandes dessinées (voir Mylar3)
- Archivage de journaux quotidiens
- Support multi-utilisateurs avec comptes et permissions séparés
- Synchronisation cloud ou backup distant
- Application mobile native (iOS/Android)
- Scraping direct d'indexeurs (uniquement via Prowlarr)
- Connexions directes Newznab/Torznab (Prowlarr uniquement en v1.0)
- ISSN Portal comme source de métadonnées (reporté post-v1.0)
- Corbeille / recycle bin pour les fichiers supprimés ou remplacés
- OCR ou reconnaissance du contenu des magazines
- Gestion de DRM ou déverrouillage de fichiers protégés
- Conversion entre formats (PDF vers EPUB, etc.)
- Plugin ou extension navigateur
- Interface en ligne de commande (CLI) — tout passe par l'API REST et l'interface web

## Clarifications

### Session 2026-02-26

- Q: Comment la liste des issues d'un magazine est-elle initialement remplie ? → A: Depuis les sources de métadonnées (Google Books, Internet Archive) au moment de l'ajout, puis complétée progressivement par les découvertes RSS et les recherches manuelles.
- Q: Quand on ajoute un magazine avec monitoring ON, quelles issues sont marquées "wanted" ? → A: L'utilisateur choisit une date de début de monitoring à l'ajout (pattern Sonarr). Seules les issues à partir de cette date sont marquées "wanted".
- Q: En quelle langue l'interface web doit-elle être ? → A: Anglais par défaut avec support i18n dès la v1.0 (FR/EN minimum).

## 8. Open Questions

Aucune question ouverte. Toutes les clarifications ont été résolues :

- **OQ-001** (résolu) : Prowlarr uniquement en v1.0. Les connexions directes Newznab/Torznab sont reportées post-v1.0.
- **OQ-002** (résolu) : ISSN Portal reporté post-v1.0. Les sources de métadonnées v1.0 sont Google Books + Internet Archive.
- **OQ-003** (résolu) : Suppression définitive. Pas de corbeille en v1.0.

## 9. Success Criteria

- **SC-001** : Un utilisateur peut ajouter un magazine, et dans les 30 minutes suivantes le système a détecté, téléchargé et rangé automatiquement au moins un numéro manquant dans la bibliothèque.
- **SC-002** : Le calendrier affiche des prévisions cohérentes pour les 6 prochains mois de tous les magazines à fréquence régulière (monthly, quarterly, etc.).
- **SC-003** : L'image Docker démarre et est fonctionnelle en moins de 10 secondes, sans aucune configuration préalable requise.
- **SC-004** : Un widget Homepage ou Homarr affiche correctement le nombre de magazines, les issues manquantes et la file d'attente de téléchargement en interrogeant l'API.
- **SC-005** : Le parser de noms de fichiers reconnaît correctement au moins 90% des fichiers magazines provenant des indexeurs majeurs, sans intervention manuelle.
- **SC-006** : L'interface web affiche une grille de 200 magazines sans dégradation perceptible des performances (temps de chargement < 2 secondes).
- **SC-007** : Après 30 jours d'utilisation continue, aucun crash ou redémarrage inattendu n'a été nécessaire, malgré l'indisponibilité temporaire de services externes.

---

## Résumé

| Catégorie | Nombre |
|-----------|--------|
| User Stories | 73 (US-001 à US-073) |
| Functional Requirements | 54 (FR-001 à FR-054) |
| Non-Functional Requirements | 11 (NFR-001 à NFR-011) |
| Edge Cases | 15 (EC-001 à EC-015) |
| Success Criteria | 7 (SC-001 à SC-007) |
| [NEEDS CLARIFICATION] | 0 (toutes résolues) |
