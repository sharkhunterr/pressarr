# Changelog

All notable changes to this project will be documented in this file. See [standard-version](https://github.com/conventional-changelog/standard-version) for commit guidelines.

## [0.2.0](https://github.com/sharkhunterr/pressarr/-/compare/v0.1.51...v0.2.0) (2026-11-08)


### Features

* **activity:** couverture complète search/grab/pack/IA dans le registre ([6823859](https://github.com/sharkhunterr/pressarr/-/commit/6823859de53522bd9494a10480a622a586b4c033))
* **activity:** mirror torrent progression → Activity (kind=download) ([9dc496c](https://github.com/sharkhunterr/pressarr/-/commit/9dc496c7493205c971df7906e4320c1ed99716ec))
* **add-magazine:** éditeur de groupes multi-typés aussi à la création ([16bc107](https://github.com/sharkhunterr/pressarr/-/commit/16bc1079e722c73cd0055be2795a7347dec1d44b))
* **add-magazine:** input édition weekend (tolérance jour) ([0531ac5](https://github.com/sharkhunterr/pressarr/-/commit/0531ac59203c7a143d3c15f6fcad577f4282f665))
* **add:** la recherche d'ajout propose aussi les titres trouvés sur Bookys ([#5](https://github.com/sharkhunterr/pressarr/-/issues/5)) ([175d5fb](https://github.com/sharkhunterr/pressarr/-/commit/175d5fb5912f7cc40c824cc8e1b0d42b112bc73a))
* **ai-history:** rendu par zone — image du crop + tabs Python/Vision ([9b3e21d](https://github.com/sharkhunterr/pressarr/-/commit/9b3e21d415df4caba1e1e1dc759c0633e6e18716))
* **ai-history:** toggle Settings pour sauver les crops PNG (défaut OFF) ([ce4c521](https://github.com/sharkhunterr/pressarr/-/commit/ce4c521fb94f39a1e1a8f609e7c7acd01f079f0d))
* **ai-vision:** crop haut couverture (45 %) + prompt crop-aware ([e1d7ced](https://github.com/sharkhunterr/pressarr/-/commit/e1d7ced9f37e669d4db5a0096fb07bf4cc345492))
* **ai-vision:** crop zone configurable — évite forcer top pour tous les magazines ([1ef94fd](https://github.com/sharkhunterr/pressarr/-/commit/1ef94fdb4c44164d8deece7c242318ee8b637a35))
* **ai-vision:** sélecteur visuel de zone (crop rect) par magazine ([e259753](https://github.com/sharkhunterr/pressarr/-/commit/e259753459ee1d1c06de3c0ff824d93baa5a7342))
* **ai+pipeline:** pipeline modulaire, ISSN, activity registry, robustesse ([7b7ebbb](https://github.com/sharkhunterr/pressarr/-/commit/7b7ebbba231c14650f620a173dc2c6847a7142b9))
* **ai:** AI metadata enrichment pipeline + search ranker (Ollama) ([28f7507](https://github.com/sharkhunterr/pressarr/-/commit/28f750790e0e2365c939fa9a522c05df6c884a1c))
* **ai:** arbitrage hybride 3-couches — Python propose, IA tranche, Python valide ([2f9b89c](https://github.com/sharkhunterr/pressarr/-/commit/2f9b89cee8046001af9f565fdb7e3f7d34565dc8))
* **ai:** batch refresh en background — non bloquant + visible dans Queue ([b4b8bd4](https://github.com/sharkhunterr/pressarr/-/commit/b4b8bd4f1bd19f321e695a0824d5c110faba5ff6))
* **ai:** endpoint + modal batch refresh (metadata + IA texte + IA vision) ([2631b17](https://github.com/sharkhunterr/pressarr/-/commit/2631b17456ded9907a48fead50fcfe27b2213996))
* **ai:** history events pour chaque run + prompt vision détaillé ([e2bd1b5](https://github.com/sharkhunterr/pressarr/-/commit/e2bd1b5b71bfbd9fa6aa5e2b1b10ee134cbaf332))
* **create-magazine:** backlog wanted + auto-search au create ([e134a24](https://github.com/sharkhunterr/pressarr/-/commit/e134a24b99f0b28362cb79f32787ba1bc0fc2f51))
* **dispatch:** bouton rescan importés + ✨ actif sur imported ([18474ba](https://github.com/sharkhunterr/pressarr/-/commit/18474ba60bd437e08f67006463ae1176844af191))
* **dispatch:** éditer les metadata + fix cleanup_stale trop agressif ([659c3ff](https://github.com/sharkhunterr/pressarr/-/commit/659c3ffaf8f690a2037978d7826598adb279ab97))
* **docker:** PUID / PGID / UMASK comme les autres images *arr ([#8](https://github.com/sharkhunterr/pressarr/-/issues/8), GitHub [#1](https://github.com/sharkhunterr/pressarr/-/issues/1)) ([2658aa7](https://github.com/sharkhunterr/pressarr/-/commit/2658aa79b5df113d0ea7e7d571bc03f7d88b30ca))
* **fiche-technique:** déplie le détail complet ai_enrichment dans la timeline ([80d4121](https://github.com/sharkhunterr/pressarr/-/commit/80d4121060148fb1baa803a53201c2694e543805))
* **grab+import:** multi-target routing — remplace le gate refus-doublon-hash par un routing intelligent ([f56c6e5](https://github.com/sharkhunterr/pressarr/-/commit/f56c6e5fe56082efa0d89dd237551339f03917b7))
* **history:** rendu riche pour les events ai_enrichment et ai_ranker ([d621628](https://github.com/sharkhunterr/pressarr/-/commit/d621628d07e415caafee5ef57087c7ab95c6cb3f))
* **import:** auto-routing par date sur TOUTES les issues du magazine (fallback 2ᵉ passe) ([566f30c](https://github.com/sharkhunterr/pressarr/-/commit/566f30c2835c0a33792ac39873a58b7435064389))
* **issue:** fiche technique — modal Edit avec timeline workflow ([9d94adc](https://github.com/sharkhunterr/pressarr/-/commit/9d94adcc1ae0e3150a8013f1a4e3c051162f1021))
* **issue:** metadata extensibles + coerce défense en profondeur ([551572f](https://github.com/sharkhunterr/pressarr/-/commit/551572fa61170bd39eaf21b01252728494962e0b))
* **issue:** trace pack origin sur IssueFile (source_type + pack) ([bb445c4](https://github.com/sharkhunterr/pressarr/-/commit/bb445c47f1da643dcfcde5b8a84542043c567f91))
* **jdownloader:** chaque grab scène est suivi comme un torrent puis importé avec l'analyse IA ([#6](https://github.com/sharkhunterr/pressarr/-/issues/6)) ([90c2691](https://github.com/sharkhunterr/pressarr/-/commit/90c269159c404a75dcd55c4ffbd31246913d7c03))
* **magazine:** bouton "Recherche wanted" manuel ([971431d](https://github.com/sharkhunterr/pressarr/-/commit/971431d98ba7736dd79a63ee22a8bee0b576db5a))
* **magazine:** bouton « Régulariser » — purge doublons wanted et regénère ([b7eabb0](https://github.com/sharkhunterr/pressarr/-/commit/b7eabb022240c8d9b1540d7cc5b6f7e4e366711d))
* **magazine:** groupes d'issues multi — remplace weekend_days unique ([f9d88a0](https://github.com/sharkhunterr/pressarr/-/commit/f9d88a06d6fb5c1f23a4da3d3998a7fa4954213f))
* **magazine:** override per-mag du seuil auto-grab (slider dans Edit) ([e542d25](https://github.com/sharkhunterr/pressarr/-/commit/e542d253b7aefbf007f4c5b209fd23990b858d53))
* **magazine:** tri IA date récente + override plancher titre ([676286e](https://github.com/sharkhunterr/pressarr/-/commit/676286e05e24fbc2f20f6c4db65b11d813ea247c))
* **magazine:** type structuré sur les groupes (regular/weekend/special) + rendu badge ([5d5f11c](https://github.com/sharkhunterr/pressarr/-/commit/5d5f11c5022940b6c465e49905b49408ede29bca))
* **magazine:** weekend_days — sélection weekdays regroupés ([7cc509a](https://github.com/sharkhunterr/pressarr/-/commit/7cc509a9d1b00b1c4ef81a30d7d9e9273f45e14e))
* **packs:** pipeline dispatch avec extraction + IA + magazine placeholder ([ecf9b4a](https://github.com/sharkhunterr/pressarr/-/commit/ecf9b4a7d5a916158dbf4b860d71368ee03c6820))
* **parser:** pattern DD-MM-YYYY (FR/EU dates) ([cbc1585](https://github.com/sharkhunterr/pressarr/-/commit/cbc1585cf9b4e76d8e7a088147c10f512c504524))
* **queue:** live tracking des activités import + IA dans la Queue ([d74057f](https://github.com/sharkhunterr/pressarr/-/commit/d74057fe5dadfa95c7b4d0bc5a729de308513554))
* **scene:** recherche manuelle Bookys / tm.org avec sa propre requête ([#7](https://github.com/sharkhunterr/pressarr/-/issues/7)) ([ad0b609](https://github.com/sharkhunterr/pressarr/-/commit/ad0b609f7092ba56b1851fad6e84810e7a75a961))
* **search:** auto-grab + scheduler wanted + UI détail pipeline (Phase 2) ([b0d15a1](https://github.com/sharkhunterr/pressarr/-/commit/b0d15a12ee9c872d859825d7c75d5b08fe7de527))
* **search:** cadence wanted_search configurable + reschedule à chaud ([def8492](https://github.com/sharkhunterr/pressarr/-/commit/def8492d506e1fb00578aebd225b0ab31786c80f))
* **search:** gate Python + tolérance jour par magazine ([c75d55c](https://github.com/sharkhunterr/pressarr/-/commit/c75d55cba27756ad818c0b55de65125e8fcbe2b4))
* **search:** patterns magazine dans le contexte IA ([3f4c658](https://github.com/sharkhunterr/pressarr/-/commit/3f4c6581081820c7fa4973e00927dfda300dbab4))
* **search:** pipeline wanted-issue unifié (Phase 1 backend) ([a7e12f1](https://github.com/sharkhunterr/pressarr/-/commit/a7e12f1f4a4ccac86ef210513a610d6fd932d772))
* **search:** queries multi-format + AI ranker taggé issue_id ([76bd2cb](https://github.com/sharkhunterr/pressarr/-/commit/76bd2cb5c31c433d0356a904a51d89ff1e08b65b)), closes [#123](https://github.com/sharkhunterr/pressarr/-/issues/123)
* **search:** toggles UI + bouton "Recherche maintenant" (Phase 3) ([6a54e03](https://github.com/sharkhunterr/pressarr/-/commit/6a54e034ba23446bbf7d325b71aaab5f1e1eddc3))
* **settings:** Bookys et l'IA marqués expérimentaux ([#10](https://github.com/sharkhunterr/pressarr/-/issues/10)) ([44edbfd](https://github.com/sharkhunterr/pressarr/-/commit/44edbfdaa2153bae6bdcebff54eb84d222c7737c))
* **settings:** choisir la langue de l'interface dans Settings → General (GitHub [#1](https://github.com/sharkhunterr/pressarr/-/issues/1)) ([9c6abc6](https://github.com/sharkhunterr/pressarr/-/commit/9c6abc661fbeb466e3a5cabd220ed85ef6e599c1))
* **ui:** colonnes issue subtitle/price + pack history+activity inline ([b3e9381](https://github.com/sharkhunterr/pressarr/-/commit/b3e938114a8d42c56a6b3b33c2702295305659d9))
* **vision:** 3 sets de zones OCR par type d'issue (normal/weekend/hs) ([89a5c08](https://github.com/sharkhunterr/pressarr/-/commit/89a5c08c6c22e99c4f935557cb077c19ce056825))
* **vision:** slider upscale par zone (1×–4×) sur le zoom auto ([49ffde8](https://github.com/sharkhunterr/pressarr/-/commit/49ffde815c726cf537aa40149332df6ab813b8cf))
* **vision:** tune minicpm-v params + option skip vision quand Python OCR OK ([0dcdb2e](https://github.com/sharkhunterr/pressarr/-/commit/0dcdb2eecab57795886d350752455f3f3006a800))


### Bug Fixes

* **activity:** _retry_on_lock plus tolérant + purge registry pack en garbage ([316f608](https://github.com/sharkhunterr/pressarr/-/commit/316f60882b331b79d8bb4ada4904450c7ceb6045))
* **activity:** boot cleanup respecte les dispatchs actifs + auto-resume ([ee75f3d](https://github.com/sharkhunterr/pressarr/-/commit/ee75f3d5130a9d48857fa31ca0e0ad25dc461f70))
* **activity:** create() sérialisé + retry sur database is locked ([ac1fa2a](https://github.com/sharkhunterr/pressarr/-/commit/ac1fa2a2391a77472f1863623bd8b89612fc4c13))
* **activity:** durée figée à la fin, et un redémarrage reprend le suivi du même download ([#6](https://github.com/sharkhunterr/pressarr/-/issues/6)) ([6308658](https://github.com/sharkhunterr/pressarr/-/commit/6308658341301be1aa0774f0f78b0cd610263aed))
* **activity:** endpoints DELETE opéraient sur mauvaise DB ([3848bc5](https://github.com/sharkhunterr/pressarr/-/commit/3848bc5fa1b55395de5c4adc287863879cd63717))
* **activity:** mark_error tronque le message pour éviter le bloat en cascade ([22c13d2](https://github.com/sharkhunterr/pressarr/-/commit/22c13d2690af6701b6964a2b6bb0fa2f74c62ccf))
* **activity:** scene grab absent + badge sidebar rate un grab rapide ([aefdfd2](https://github.com/sharkhunterr/pressarr/-/commit/aefdfd2df275a8bcb7aee719b36978ea6aac291a))
* **add:** chaque source porte son nom et ne masque plus le titre ([#2](https://github.com/sharkhunterr/pressarr/-/issues/2)) ([63282a8](https://github.com/sharkhunterr/pressarr/-/commit/63282a8856df783c566d1ebd7b509dae2595b56b))
* **add:** couverture Wikimedia demandée avec un User-Agent descriptif ([#9](https://github.com/sharkhunterr/pressarr/-/issues/9)) ([e46581a](https://github.com/sharkhunterr/pressarr/-/commit/e46581a6f62b0697432fdd8925fe090f5dc9f5f9))
* **add:** la couverture montrée par la recherche d'ajout est enregistrée avec le magazine ([#9](https://github.com/sharkhunterr/pressarr/-/issues/9)) ([561820e](https://github.com/sharkhunterr/pressarr/-/commit/561820eeaeb93aad5fe007154aa3e1a31df6ce5b))
* **add:** un logo devient une couverture lisible (centré sur fond blanc, format portrait) ([#9](https://github.com/sharkhunterr/pressarr/-/issues/9)) ([840788d](https://github.com/sharkhunterr/pressarr/-/commit/840788db915a5cb08f527add41828c2c140c6ea6))
* **ai-arbiter:** postvalidate restaure les valeurs Python quand le LLM les 'oublie' ([08ed2fe](https://github.com/sharkhunterr/pressarr/-/commit/08ed2fe7940beea75f1e2b784bab9cbd6cad2a5e))
* **ai-crop:** min zone 0.3% + inputs numériques + prompts sans chiffres exemples ([3fd6b9b](https://github.com/sharkhunterr/pressarr/-/commit/3fd6b9b58c03a3957ca9a2fb44bfdfbf366f2fe3))
* **ai-enrich:** coerce int() sur number/year/month/day (bug critique) ([e1bf640](https://github.com/sharkhunterr/pressarr/-/commit/e1bf640165083352cc2bad82a9198193de15873b))
* **ai-ui:** probe uses live URL + always-Select model dropdown + visual align with Metadata ([c09d219](https://github.com/sharkhunterr/pressarr/-/commit/c09d2191d139991bd3b791cb5753c2a42b94d5b3))
* **ai-vision:** compromis DPI 200 + num_ctx 8192 pour tenir dans 8 Go VRAM ([a732db2](https://github.com/sharkhunterr/pressarr/-/commit/a732db20c4f75092ada69b1cb6559a0e121423b2))
* **ai-vision:** DPI rendu PDF 150 → 250 pour lisibilité des petits nombres ([81c0350](https://github.com/sharkhunterr/pressarr/-/commit/81c0350df81010db27390f59e40e35867ad16e97))
* **ai-vision:** num_ctx=16384 sur appels vision (fix HTTP 400 context) ([ea59dec](https://github.com/sharkhunterr/pressarr/-/commit/ea59deca1e2ffc51475533ea52446473698da292))
* **ai:** arbitre LLM → merge Python déterministe (garantit torrent > vision) ([0f8819f](https://github.com/sharkhunterr/pressarr/-/commit/0f8819f30ac891e173d17fb2704135906000e59c)), closes [#3](https://github.com/sharkhunterr/pressarr/-/issues/3)
* **ai:** arbitre parse le raw_text vision avec regex smart (N°, date) ([3e68a67](https://github.com/sharkhunterr/pressarr/-/commit/3e68a67fd78f706d848e57db2a89d7379873c796))
* **ai:** boutons user-triggered bypass le cache + toast clair cache vs vraie run ([0bc3f6d](https://github.com/sharkhunterr/pressarr/-/commit/0bc3f6ddbba04820cfe46a7f3c96a86c5d1280ce))
* **ai:** step_summary droppait zone/tag/crop_file + migration prompt vision ([8db5a3f](https://github.com/sharkhunterr/pressarr/-/commit/8db5a3fc5a24adeb6382f9710d4cf8e93d5a9479)), closes [#1](https://github.com/sharkhunterr/pressarr/-/issues/1) [#2](https://github.com/sharkhunterr/pressarr/-/issues/2)
* **auto-grab:** title gate robuste — Jaccard content-tokens au lieu de fuzz.ratio strict ([5238f2d](https://github.com/sharkhunterr/pressarr/-/commit/5238f2d1d52b5f75ab02e48296bc971409ac8da6))
* **blocklist:** page vide (contract API↔UI aligné + magazineTitle exposé) ([5c6b849](https://github.com/sharkhunterr/pressarr/-/commit/5c6b849b8caf965f88c4f14a07053c9b3943e227))
* **bookys:** connexion avec le nouveau formulaire du site (www7) (GitHub [#1](https://github.com/sharkhunterr/pressarr/-/issues/1)) ([980a90e](https://github.com/sharkhunterr/pressarr/-/commit/980a90ecb0982d97135924bb81b5a0dab66cac46))
* **bookys:** connexion, recherche et liens sur le nouveau site www7 (GitHub [#1](https://github.com/sharkhunterr/pressarr/-/issues/1)) ([0b981e7](https://github.com/sharkhunterr/pressarr/-/commit/0b981e7d3456362298b26102cd465cefdd4a7dd1))
* **bookys:** le test de connexion donne la vraie raison d'un échec (GitHub [#1](https://github.com/sharkhunterr/pressarr/-/issues/1)) ([45aa076](https://github.com/sharkhunterr/pressarr/-/commit/45aa0761371a8ab5bb5f8d2106a098cfc074ab0b))
* **bookys:** les liens d'hébergeur sont décodés (« &amp; » → « & ») ([#4](https://github.com/sharkhunterr/pressarr/-/issues/4)) ([3fffdc8](https://github.com/sharkhunterr/pressarr/-/commit/3fffdc8b5a48537fbbc5cbd721dd968af490b38f))
* **bookys:** moins de requêtes en parallèle, reprise sur 429, pas de couverture inaccessible (GitHub [#1](https://github.com/sharkhunterr/pressarr/-/issues/1)) ([5ac27bb](https://github.com/sharkhunterr/pressarr/-/commit/5ac27bb4ccd2c087c038ebc10bfe5237b60c2ba8))
* **bookys:** tout le scraping passe par une session FlareSolverr, sans compte (GitHub [#1](https://github.com/sharkhunterr/pressarr/-/issues/1)) ([73c8263](https://github.com/sharkhunterr/pressarr/-/commit/73c82630e469ab17214cbcf7ff6734be636f8c3d))
* **calendar:** coalescing weekend aussi dans generate_forecasts ([0a372b6](https://github.com/sharkhunterr/pressarr/-/commit/0a372b60c08d7ffaecdb484751f712125d419865))
* **coherence:** tolérance basée sur range local, pas médiane des diffs ([0c80206](https://github.com/sharkhunterr/pressarr/-/commit/0c80206dfc6318737132a899296262f93ea24cdc)), closes [#1234](https://github.com/sharkhunterr/pressarr/-/issues/1234) [#2743](https://github.com/sharkhunterr/pressarr/-/issues/2743) [#2745](https://github.com/sharkhunterr/pressarr/-/issues/2745) [#2743](https://github.com/sharkhunterr/pressarr/-/issues/2743) [#1234](https://github.com/sharkhunterr/pressarr/-/issues/1234) [#2745](https://github.com/sharkhunterr/pressarr/-/issues/2745)
* **crop-editor:** trait de zone dessiné à l'intérieur — ce que tu vois = ce qui est cropé ([1b1d3cf](https://github.com/sharkhunterr/pressarr/-/commit/1b1d3cf457b9d2b3117a623c8f3ec5afc19b828a))
* **db:** PRAGMA busy_timeout=30000 + synchronous=NORMAL (main DB) ([577f8a7](https://github.com/sharkhunterr/pressarr/-/commit/577f8a7c7b3c8abd5853924f32196d6405931fb0))
* **dispatch:** applique les rules exclude/include du magazine candidat ([3eadd7e](https://github.com/sharkhunterr/pressarr/-/commit/3eadd7ec7801b8182fc103f084293ce87ae0369b))
* **dispatch:** errors format/unicode + confidence badge + zones magazine ([2d90750](https://github.com/sharkhunterr/pressarr/-/commit/2d907505fd2921bc5e2cbddd82347c922f8a0167))
* **dispatch:** fiabilité — isolation session par fichier + safe json partout ([e00dfa0](https://github.com/sharkhunterr/pressarr/-/commit/e00dfa0a120da1f0ae13f69394be4f9e166d1ae0))
* **dispatch:** fuzzy scorer WRatio → ratio (élimine faux positifs préfixe) ([ac68551](https://github.com/sharkhunterr/pressarr/-/commit/ac68551278003c09e3e7609759133c440fa8a568))
* **dispatch:** ImportError apply_rules → apply_magazine_rules ([c655e6d](https://github.com/sharkhunterr/pressarr/-/commit/c655e6d15485cc82c7182b7bd360da0048bf353f))
* **dispatch:** progress steps live pendant reanalyze (0% éternel → étapes) ([b798edd](https://github.com/sharkhunterr/pressarr/-/commit/b798eddc4e1493e342274df8721cf69908b70beb))
* **dispatch:** reanalyze crée maintenant une activity visible ([d8d0d63](https://github.com/sharkhunterr/pressarr/-/commit/d8d0d636c0ad658472817629862a2fa84db2b8f3))
* **dispatch:** reanalyze écrase toujours le match (jamais fusion avec ancien) ([0d77544](https://github.com/sharkhunterr/pressarr/-/commit/0d77544ec19a208189dbb63fdbabaf9171b7bc0b))
* **dispatch:** reanalyze reset l'error_message précédent ([dc95b00](https://github.com/sharkhunterr/pressarr/-/commit/dc95b00b27d99b9a2984d33fbeefd407cca12707))
* **dispatch:** resolve_dispatch_file isole les phases pour éviter FK error ([cefa363](https://github.com/sharkhunterr/pressarr/-/commit/cefa3632a038cfb16376b117161a1ac74e5af03f))
* **docker:** healthcheck en Python, sans dépendre de curl (GitHub [#1](https://github.com/sharkhunterr/pressarr/-/issues/1)) ([8da3104](https://github.com/sharkhunterr/pressarr/-/commit/8da31043f35d2cd690a11037f0d46f8f9a3321e5))
* **docker:** OpenCV headless seul — EasyOCR et RapidOCR s'importaient en échec dans l'image (libxcb manquante) ([9da1c11](https://github.com/sharkhunterr/pressarr/-/commit/9da1c112876a2d93f5459503edf6633cd43ede10))
* **download:** callsites ratés au refactor multi-target — AttributeError sur `list.pack_id` ([93d0f9c](https://github.com/sharkhunterr/pressarr/-/commit/93d0f9c9dba032fc67523b56736234b60f6a1739))
* **frontend:** le build de production passe à nouveau (tsc -b) ([64f9c1d](https://github.com/sharkhunterr/pressarr/-/commit/64f9c1d8860ae2a98fe0d8122a6b070fd1b9f252))
* **grab:** gate anti-doublon torrent hash — refuse un grab qui écraserait un registry existant ([7b6ba77](https://github.com/sharkhunterr/pressarr/-/commit/7b6ba775a6152e10a01f17d3f777082018ed3a9c))
* **grab:** les résultats magnet-only (The Pirate Bay via Prowlarr) sont grabbés (GitHub [#1](https://github.com/sharkhunterr/pressarr/-/issues/1)) ([7a80dcd](https://github.com/sharkhunterr/pressarr/-/commit/7a80dcde6c0847325f5d7742335516b4d96d288b))
* **history:** scrub surrogates non-pairés — l'onglet Historique tombait en 500 ([07ee3b9](https://github.com/sharkhunterr/pressarr/-/commit/07ee3b978cc9f4beff8f76cbc54aa971db6ebedf))
* **import:** 2ᵉ gate anti-contamination sur la DATE — refuse quand le PDF est daté ≠ issue cible ([e830cdb](https://github.com/sharkhunterr/pressarr/-/commit/e830cdb3da80a00e41f63db3f5fd2c3397e1558c))
* **import:** capture date filename AVANT merge_ai_into_parsed (sinon écrasée) ([0dbfb6e](https://github.com/sharkhunterr/pressarr/-/commit/0dbfb6eafcb098cdcc16128f36559ac29a2375af))
* **import:** gate anti-contamination — refuse l'import si l'IA détecte un titre ≠ magazine cible ([88ac70b](https://github.com/sharkhunterr/pressarr/-/commit/88ac70bdb5c73495b879783695ef7345036db226))
* **import:** gate anti-contamination utilise le Jaccard partagé — refusait « Le Monde des 30 et 31 Août » à tort ([3b3a4e2](https://github.com/sharkhunterr/pressarr/-/commit/3b3a4e2766ea47e50b175beb306473611b8583c5))
* **import:** mois FR string → int + candidates non satisfaites remises en wanted ([28eb16a](https://github.com/sharkhunterr/pressarr/-/commit/28eb16a275437a71bbfa6d09415f70724f1b83b0))
* **import:** parser filename comme source de date primaire + short-circuit retry sur tous « Rejected: » ([c613e01](https://github.com/sharkhunterr/pressarr/-/commit/c613e013832bdfa14eba4f4ecd0fe44d8efedc6b))
* **import:** pas de month-fallback sur mags day-precise ([7877f51](https://github.com/sharkhunterr/pressarr/-/commit/7877f512c3ea1bd24227a826facd37028c852a51))
* **import:** propage source_release_title au IssueFile — Fiche technique montre le nom du torrent/pack ([0fdacb4](https://github.com/sharkhunterr/pressarr/-/commit/0fdacb4b5f3b845eada4e04dcbc3c8f8d5fc0c3b))
* **import:** rejet contamination = marque processed + blocklist auto ([f2761d6](https://github.com/sharkhunterr/pressarr/-/commit/f2761d64b3b486c5c5fa03a265edb758c3696ccf))
* **jdownloader:** JDownloader désactivé ne fait plus échouer les releases ([#3](https://github.com/sharkhunterr/pressarr/-/issues/3)) ([72a5314](https://github.com/sharkhunterr/pressarr/-/commit/72a53140c7bbdf34bf1b7b0571b813396b634459))
* **library:** l'en-tête passe à la ligne sur mobile au lieu de déborder ([b692c13](https://github.com/sharkhunterr/pressarr/-/commit/b692c13f1b54a0aecae2ea8cc9eeedbcb2e71b59))
* **magazine:** « supprimer les fichiers » supprime vraiment les fichiers et le dossier du magazine ([#1](https://github.com/sharkhunterr/pressarr/-/issues/1)) ([a09b4a6](https://github.com/sharkhunterr/pressarr/-/commit/a09b4a63813886c223eb90c889f3660999a396dd))
* **magazine:** bouton Recherche wanted aussi sur mobile ([ec20b26](https://github.com/sharkhunterr/pressarr/-/commit/ec20b26a74d4245953b8c2cef16a205a5d01ea74))
* **metadata:** la recherche d'ajout ne perd plus de sources ni ne finit en 500 ([#2](https://github.com/sharkhunterr/pressarr/-/issues/2)) ([8b109eb](https://github.com/sharkhunterr/pressarr/-/commit/8b109ebad153af3ad37e300ef0ed6a467066f3af))
* **pack-dispatch:** commit après chaque fichier au lieu de flush ([0d32783](https://github.com/sharkhunterr/pressarr/-/commit/0d32783b9210e6c2e42e0636988d72aa7cabb8b7))
* **pack-dispatch:** monitor tick relançait la dispatch en boucle ([4b36c9f](https://github.com/sharkhunterr/pressarr/-/commit/4b36c9fb6e99a4ea5674e0b381e4dc04c36829fc))
* **packs:** FK pack_dispatch_file.ai_run_id → ai_enrichment_run (bon nom) ([a00d0ee](https://github.com/sharkhunterr/pressarr/-/commit/a00d0ee89138cf7efbda39033c393ac30829b736))
* **qbittorrent:** add_torrent gère les re-add + fallback plus robuste ([fc46711](https://github.com/sharkhunterr/pressarr/-/commit/fc46711f6e5d4d338906542da275ff803712417c))
* **scene:** l'onglet Bookys s'affiche comme les indexeurs et ne garde que le bon titre ([#4](https://github.com/sharkhunterr/pressarr/-/issues/4)) ([2bccb61](https://github.com/sharkhunterr/pressarr/-/commit/2bccb6146dd3f67a3668acf4b83f77a625bb6da4)), closes [#5](https://github.com/sharkhunterr/pressarr/-/issues/5)
* **search:** auto-grab OFF par défaut + respect ai_ranker_mode ([285877d](https://github.com/sharkhunterr/pressarr/-/commit/285877d94265a1039f80d362af46374e96a81469)), closes [#6](https://github.com/sharkhunterr/pressarr/-/issues/6)
* **search:** commit explicite du searched event (perte silencieuse) ([ab106c4](https://github.com/sharkhunterr/pressarr/-/commit/ab106c46c75490151591c74e24fc314ce717a7fc))
* **search:** filtre date-match avant IA + issue_id sur success branch ([5b7721c](https://github.com/sharkhunterr/pressarr/-/commit/5b7721cea962f9604d317b078a03af9817e2d8d6)), closes [#25392](https://github.com/sharkhunterr/pressarr/-/issues/25392) [#25392](https://github.com/sharkhunterr/pressarr/-/issues/25392)
* **search:** filtre strict zero-info + contexte IA enrichi ([02780c9](https://github.com/sharkhunterr/pressarr/-/commit/02780c9433ac8691ed87a4fc1346b3470d191a47))
* **search:** history event best-effort — ne bloque plus les résultats ([7c72092](https://github.com/sharkhunterr/pressarr/-/commit/7c720922fa97d95c271e4ffb2f998a72d39823cf))
* **search:** Investir bloqué à 50% (release group « kop1 ») + queries avec accents rejetées ([eda5660](https://github.com/sharkhunterr/pressarr/-/commit/eda56608c6809fdd2fc798a03839350719427eb7)), closes [#7](https://github.com/sharkhunterr/pressarr/-/issues/7)
* **search:** Manual Research sans query fallback sur le titre magazine ([ac57cfe](https://github.com/sharkhunterr/pressarr/-/commit/ac57cfe42f2a0b9533bfc8325c06ed450499de4e))
* **search:** NameError all_raw sur le refactor multi-query dedup ([c82d4f0](https://github.com/sharkhunterr/pressarr/-/commit/c82d4f052d8ea783b6039c386379530f6138af5c))
* **search:** parser ordinaux (1er/2ème/27th) + filtre date strict ([0648678](https://github.com/sharkhunterr/pressarr/-/commit/06486782b50d1eac33693588685e7228cfb6f01a))
* **search:** plus de fallback surviving + gate ratio strict parsed ([1ff70ba](https://github.com/sharkhunterr/pressarr/-/commit/1ff70ba6fe7314322c90b24c1c63059608ccb3d8))
* **settings:** l'avertissement Cloudflare de Bookys est traduit ([#10](https://github.com/sharkhunterr/pressarr/-/issues/10)) ([2324da4](https://github.com/sharkhunterr/pressarr/-/commit/2324da41fc56a92b59f77c572e1c75771e2c6816))
* **ui:** boutons IA aussi dans la nav mobile de MagazineDetail ([e80dce6](https://github.com/sharkhunterr/pressarr/-/commit/e80dce66a3d70a8a13535ba369160eb4d4f5cd3c))
* **vision+history:** num_ctx=16384 par défaut + fallback grouping vieux runs ([eb52d75](https://github.com/sharkhunterr/pressarr/-/commit/eb52d75fb21db5ed58f4dc705fcd79c3fe695e34))
* **vision+ocr:** Tesseract preprocessing + garbage sur python_ocr + steps rejetées dimmed ([aa2579e](https://github.com/sharkhunterr/pressarr/-/commit/aa2579e18a077634cc927b3f18735ef40b616660))
* **vision:** leak check gated aux zones title-scoped ([194449f](https://github.com/sharkhunterr/pressarr/-/commit/194449f8252cfbc3c29683db100115c4bcea58cd))
* **vision:** num_ctx=16384 pour qwen2.5vl + retry auto sur unexpected EOF ([787e0a0](https://github.com/sharkhunterr/pressarr/-/commit/787e0a081fb3138c81790811ca15e0e820e09954))
* **vision:** OCR — prompt sans exemple + garbage detector durci + zoom adaptatif par zone ([6e31f76](https://github.com/sharkhunterr/pressarr/-/commit/6e31f763aea7cc6ff82bcc7ecb2b132cb5575e5c))

### [0.1.51](https://github.com/sharkhunterr/pressarr/-/compare/v0.1.50...v0.1.51) (2026-08-09)


### Features

* **files:** File Manager global (/files) — list + filters + assign + delete ([467ad17](https://github.com/sharkhunterr/pressarr/-/commit/467ad177e7d24342dced3dd501e86ea206a53dbc))
* **packs:** reimport post-hoc + fichiers en attente + dialog magazine ([aa89912](https://github.com/sharkhunterr/pressarr/-/commit/aa899124c9888881e155f0257facd4031b72dea0))

### [0.1.50](https://github.com/sharkhunterr/pressarr/-/compare/v0.1.49...v0.1.50) (2026-08-09)


### Features

* **packs:** review avant import + onglet Fichiers post-hoc ([6d7dd0b](https://github.com/sharkhunterr/pressarr/-/commit/6d7dd0bda0d191c17eed400325a34d83dc7760c9))


### Bug Fixes

* **download:** _select_client priorise is_default (tie-break sur priority) ([31564d4](https://github.com/sharkhunterr/pressarr/-/commit/31564d437ef4a432a77927d5bc3bb0dde6e7a701))

### [0.1.49](https://github.com/sharkhunterr/pressarr/-/compare/v0.1.48...v0.1.49) (2026-08-09)


### Bug Fixes

* **rootfolders:** drop unused Input import (CI TS6133) ([6dbdbda](https://github.com/sharkhunterr/pressarr/-/commit/6dbdbda69dba04f11586fc62c67b67d69967ae75))

### [0.1.48](https://github.com/sharkhunterr/pressarr/-/compare/v0.1.47...v0.1.48) (2026-08-09)


### Features

* **system:** version-check GitHub + folder browser sur Root Folders ([9ea3441](https://github.com/sharkhunterr/pressarr/-/commit/9ea3441152d0538783b598457726c3137192f65d))


### Bug Fixes

* **migrations:** heal-at-boot pour magazine.request_type + enrichment fields ([806c456](https://github.com/sharkhunterr/pressarr/-/commit/806c45603d1bf18bbd77ed3b8d6909daa5798f43))

### [0.1.47](https://github.com/sharkhunterr/pressarr/-/compare/v0.1.46...v0.1.47) (2026-07-13)


### Bug Fixes

* **tests:** align dedup test with the ISSN-first cascade refactor ([b2bb052](https://github.com/sharkhunterr/pressarr/-/commit/b2bb0522a27e4b30ba8eab45f90c0bece2277ab1))

### [0.1.46](https://github.com/sharkhunterr/pressarr/-/compare/v0.1.45...v0.1.46) (2026-07-13)


### Features

* **dispatch:** JDownloader 2 folder-watch grab path ([f11e790](https://github.com/sharkhunterr/pressarr/-/commit/f11e790105610024752ad6f0af63268c2e0fb9bb))
* **jdownloader:** inspect + manage JD2 queue directly from pressarr UI ([b1587c4](https://github.com/sharkhunterr/pressarr/-/commit/b1587c427a2ebd1f88d2e61563b91f9d069c703a))
* **magazine:** back-fill cascade enrichment on createMagazine ([fad3bf9](https://github.com/sharkhunterr/pressarr/-/commit/fad3bf95383ff31dfc8c4737d8c24cd477bf49c0))
* **magazine:** BnF MARC 326 frequency + verified-only filter ([c8a0dee](https://github.com/sharkhunterr/pressarr/-/commit/c8a0dee245ef2a0b50cb6691886e79be113998c0))
* **magazine:** Bookys + telecharger-magazines.org tabs in manual search modal ([251763d](https://github.com/sharkhunterr/pressarr/-/commit/251763d8db5fc2e3f493fbb403e23644327c5360))
* **magazine:** expose coverIsLogo + multi-ISSN filter on search ([fff3a25](https://github.com/sharkhunterr/pressarr/-/commit/fff3a2536159d0e59a256b545a3d89eaf93a14e0))
* **magazine:** expose full ISSN-L sibling list (print + online + CD-ROM) on identity ([bf52482](https://github.com/sharkhunterr/pressarr/-/commit/bf524823e799d9d7390c23b4d0770f3b98031469))
* **magazine:** ISSN Portal provider + Wikidata related publications + aggressive root-slug dedup ([f87a88f](https://github.com/sharkhunterr/pressarr/-/commit/f87a88fc6c1feac86d0e27dde4f80a741b512840))
* **magazine:** ongoing-first ranking + status filter + frequency from Wikidata P2241/P31 ([5e2c581](https://github.com/sharkhunterr/pressarr/-/commit/5e2c581394eb84d29345281897d15f9b680f6a22))
* **magazine:** persist ISSN-first cascade enrichment on Magazine rows ([c548a0e](https://github.com/sharkhunterr/pressarr/-/commit/c548a0e441d12be703f4cc56592db1fc2cc89e88))
* **magazine:** rank-first, canonical boost, drop IA noise ([e185b98](https://github.com/sharkhunterr/pressarr/-/commit/e185b986015d60ceb8344af32a348013509886e8))
* **magazine:** scene auto-grab scheduler honouring subscription / one-shot ([8b6f11c](https://github.com/sharkhunterr/pressarr/-/commit/8b6f11c70cdddc3f4bbf982a13fe2fc95e9fe5bf)), closes [#594](https://github.com/sharkhunterr/pressarr/-/issues/594)
* **magazine:** scene importer — JD2 output → library, release status flip ([b937c18](https://github.com/sharkhunterr/pressarr/-/commit/b937c18fda1a2fd7bca04923308de3452a8cf12f)), closes [#594](https://github.com/sharkhunterr/pressarr/-/issues/594) [#3986](https://github.com/sharkhunterr/pressarr/-/issues/3986)
* **magazine:** subscription vs one-shot request type on Magazine ([518471e](https://github.com/sharkhunterr/pressarr/-/commit/518471ef9e0cb602088f1e85131c236d4dd6a511))
* **magazine:** wire ISSN cascade into search + add ISSN-lookup endpoint ([04ccec1](https://github.com/sharkhunterr/pressarr/-/commit/04ccec130895eba18ffdb2b140754cbd7a2a85f2))
* **metadata:** add BnF (French press authority) to the cascade ([6c11445](https://github.com/sharkhunterr/pressarr/-/commit/6c1144596fd48dea5afe800fdfe8af8e35b9f37d))
* **metadata:** scene-indexer cover fallback in the cascade ([cea4640](https://github.com/sharkhunterr/pressarr/-/commit/cea4640a9a7670b0157cc8ed39c93ae257089d1a)), closes [#0](https://github.com/sharkhunterr/pressarr/-/issues/0)
* **metadata:** ZDB + Wikidata providers + ISSN-first cascade orchestrator ([6ffaf78](https://github.com/sharkhunterr/pressarr/-/commit/6ffaf782bd4b6929bc84c7cf54ef7e734ced4303))
* **scene-indexers:** Bookys + telecharger-magazines.org scrapers + release table ([c3f1a75](https://github.com/sharkhunterr/pressarr/-/commit/c3f1a75551dd8b12ecabebe8c50c0f51898823f2))
* **scene-indexers:** FlareSolverr-backed Bookys scraper (Cloudflare bypass) ([0e5547c](https://github.com/sharkhunterr/pressarr/-/commit/0e5547c4453ceef4d83bcd9ce92dd4938a3578cb))
* **settings:** magazine-indexer settings page in pressarr UI ([dbf1c4c](https://github.com/sharkhunterr/pressarr/-/commit/dbf1c4cc9a42e836299246db775a86f33b412fe7))


### Bug Fixes

* **dispatcher:** lowercase booleans + demote frdl.io in hoster preference ([95f3f52](https://github.com/sharkhunterr/pressarr/-/commit/95f3f52d7ded9171e50d31dca998d8949bac4aa4))
* **dispatcher:** write one hoster URL per .crawljob, not all mirrors ([8a31490](https://github.com/sharkhunterr/pressarr/-/commit/8a314900bc9ab98438ac70301029b38bf248be99))
* **jd2:** write the JD2-side path in .crawljob's downloadFolder ([414fe27](https://github.com/sharkhunterr/pressarr/-/commit/414fe27b4dd96103c3079b04d4b26e4b9d8ab1d6))
* **magazine-detail:** show Re-grab button when scene release is already grabbed ([b56d6bd](https://github.com/sharkhunterr/pressarr/-/commit/b56d6bda8268938bf5ac1e4c1481829c3bd962c4))
* **magazine:** cross-reference cascade hits via Wikidata identity + soft timeouts ([d6665a6](https://github.com/sharkhunterr/pressarr/-/commit/d6665a673c1e7c60c692b9e3278b0ab6dd902d38))
* **magazine:** emit history events on scene grab / auto-grab / import ([b7e2088](https://github.com/sharkhunterr/pressarr/-/commit/b7e2088cf2cf1f9df276674ac017cc8379f56cb5))
* **magazine:** parallelize Wikidata related-publications + bump cascade timeout ([4da6d80](https://github.com/sharkhunterr/pressarr/-/commit/4da6d80966f1047bd5a79b283d641dbfdcdd727c)), closes [#0](https://github.com/sharkhunterr/pressarr/-/issues/0)
* **magazine:** prefer Wikidata P154 logo over P18 image as cover ([9557f88](https://github.com/sharkhunterr/pressarr/-/commit/9557f88e6374c008084cb9b3cdd863cbd06ff3b5))
* **magazine:** rank ISSN-less catalogue noise below real magazines ([7c9a85b](https://github.com/sharkhunterr/pressarr/-/commit/7c9a85b64e5a6284bfa7a34013ef3dfa9bb94301))
* **magazine:** scene query normalisation + immediate back-catalogue grab on add ([030cdfe](https://github.com/sharkhunterr/pressarr/-/commit/030cdfe19a66abfc52f55b3d7a01a0bc09615ded))
* **scene-indexers:** rewrite tm.org scraper for the WordPress + liens-direct flow ([4e67e96](https://github.com/sharkhunterr/pressarr/-/commit/4e67e96d4264f86a6b531481ab57240a0e210ec1))
* **tm.org:** friendlier message when Cloudflare reports an origin outage ([2df2ba1](https://github.com/sharkhunterr/pressarr/-/commit/2df2ba19a1e88804c7b8ba74558008e4beec0ed4))

### [0.1.45](https://github.com/sharkhunterr/pressarr/-/compare/v0.1.44...v0.1.45) (2026-05-29)


### Bug Fixes

* **history:** structured error events for RSS / import failures ([8f5dfcd](https://github.com/sharkhunterr/pressarr/-/commit/8f5dfcd6b8ddc8c87cb832c6c42b542a632219dc))
* **magazine:** pattern + rule edit + convert pattern to exclude rule ([fadd682](https://github.com/sharkhunterr/pressarr/-/commit/fadd6822b659bf53680461b6bcee0dbcf23f9683))
* **parser:** trust torznab language attr over filename heuristic ([3441d97](https://github.com/sharkhunterr/pressarr/-/commit/3441d97301bafc5dccd7b9f97b04be9fd8b74f70))
* **qbittorrent:** handle 204 auth + extract hash on add_torrent ([de378de](https://github.com/sharkhunterr/pressarr/-/commit/de378deebf69a99db7b8c3961cd7b63c5725460f))

### [0.1.44](https://github.com/sharkhunterr/pressarr/-/compare/v0.1.43...v0.1.44) (2026-03-14)


### Bug Fixes

* add issue_file.magazine_id to startup migration for Docker deployments ([bf8acdc](https://github.com/sharkhunterr/pressarr/-/commit/bf8acdc4bdd8a248bf067803a75cd2032113e1a1))

### [0.1.43](https://github.com/sharkhunterr/pressarr/-/compare/v0.1.42...v0.1.43) (2026-03-14)


### Features

* add file manager modal and fix forecast auto-increment ([04623cd](https://github.com/sharkhunterr/pressarr/-/commit/04623cdb4adddde76547fb4a1b284873db857974))
* enhance file manager with unassign, mismatch indicator, and remove rename button ([fd9d58a](https://github.com/sharkhunterr/pressarr/-/commit/fd9d58a82e93dd858edc69c7fb85c43d652829b7))

### [0.1.42](https://github.com/sharkhunterr/pressarr/-/compare/v0.1.41...v0.1.42) (2026-03-13)


### Features

* add mass rename files feature and {special}/{hs} template variable ([86d5ca9](https://github.com/sharkhunterr/pressarr/-/commit/86d5ca9d1036b5ba201652898d2deccde3eb8f04))
* scan creates issues for unmatched files found on disk ([479edc2](https://github.com/sharkhunterr/pressarr/-/commit/479edc2240519de69c582df2d4fb5b429240addd))


### Bug Fixes

* use issue DB values for import naming and fix mismatch detection ([54eb5a6](https://github.com/sharkhunterr/pressarr/-/commit/54eb5a6b6337fdbc023ac1c6e4985de8027fc03d))

### [0.1.41](https://github.com/sharkhunterr/pressarr/-/compare/v0.1.40...v0.1.41) (2026-03-11)

### [0.1.40](https://github.com/sharkhunterr/pressarr/-/compare/v0.1.39...v0.1.40) (2026-03-11)


### Bug Fixes

* add indexer_overrides migration and prevent duplicate file paths in scan ([8f5f34d](https://github.com/sharkhunterr/pressarr/-/commit/8f5f34d7ff313412a022a0f10bafb6b9ddbf0124))
* issue viewer modal not fitting viewport on desktop ([6e5391a](https://github.com/sharkhunterr/pressarr/-/commit/6e5391ab38fbe05fa00d25015e5205148dd64428))

### [0.1.39](https://github.com/sharkhunterr/pressarr/-/compare/v0.1.38...v0.1.39) (2026-03-11)


### Bug Fixes

* detect file/issue mismatches and match by date in magazine refresh ([490130c](https://github.com/sharkhunterr/pressarr/-/commit/490130c20c3c9aa26313d4c53df1ec2aa14bcaf7))

### [0.1.38](https://github.com/sharkhunterr/pressarr/-/compare/v0.1.37...v0.1.38) (2026-03-11)


### Features

* issue file rename on disk and enhanced magazine refresh ([7f590f7](https://github.com/sharkhunterr/pressarr/-/commit/7f590f7f1cb2c7b988b9cb798bfc83c25fa3908d))

### [0.1.37](https://github.com/sharkhunterr/pressarr/-/compare/v0.1.36...v0.1.37) (2026-03-11)


### Features

* improve indexer categories with Prowlarr detection and picker ([21643ff](https://github.com/sharkhunterr/pressarr/-/commit/21643ff5dc8e26137aad5bb02b67f30523a5e19b))
* per-indexer category editing in Prowlarr settings ([5926a21](https://github.com/sharkhunterr/pressarr/-/commit/5926a21eec013bd29692411bb9cd6fba396a3f1b))
* per-indexer enable/disable and test with stored API key ([bc0f249](https://github.com/sharkhunterr/pressarr/-/commit/bc0f2492cf7db60bd1610af35cfe866f21064a2f))


### Bug Fixes

* show API key in indexer edit form with eye toggle ([088e585](https://github.com/sharkhunterr/pressarr/-/commit/088e585a9a50e36b716f98275d5a37774a1684cc))

### [0.1.36](https://github.com/sharkhunterr/pressarr/-/compare/v0.1.35...v0.1.36) (2026-03-10)


### Bug Fixes

* handle issue number conflict and improve manual search layout ([7491f74](https://github.com/sharkhunterr/pressarr/-/commit/7491f7443caf8964e1665c9cb445f4dc7e5be6c8))

### [0.1.35](https://github.com/sharkhunterr/pressarr/-/compare/v0.1.34...v0.1.35) (2026-03-10)


### Bug Fixes

* update reconcile_forecast test to match frequency-aware window ([9e4f46d](https://github.com/sharkhunterr/pressarr/-/commit/9e4f46d1da335bd839dc8c92fe6a9598c172d442))

### [0.1.34](https://github.com/sharkhunterr/pressarr/-/compare/v0.1.33...v0.1.34) (2026-03-10)


### Bug Fixes

* re-fetch magazine after creation to avoid lazy-load errors ([890ce18](https://github.com/sharkhunterr/pressarr/-/commit/890ce185131e3b56eaa4d5a881c429c1edbff69c))

### [0.1.33](https://github.com/sharkhunterr/pressarr/-/compare/v0.1.32...v0.1.33) (2026-03-10)


### Features

* add patterns & rules per magazine for smarter RSS matching ([77535f8](https://github.com/sharkhunterr/pressarr/-/commit/77535f89ea38cb5e27c7c335ab5c9f6a08325a9c))


### Bug Fixes

* frequency-aware issue matching to prevent monthly magazine duplicates ([b5c595f](https://github.com/sharkhunterr/pressarr/-/commit/b5c595fff93625adc6547dfbf37d719812912eb5))

### [0.1.32](https://github.com/sharkhunterr/pressarr/-/compare/v0.1.31...v0.1.32) (2026-03-08)


### Bug Fixes

* unify monitored/unmonitored badge styles across all pages ([024399a](https://github.com/sharkhunterr/pressarr/-/commit/024399a4cc4d37783c4e6584d2ad4a82b2703967))

### [0.1.31](https://github.com/sharkhunterr/pressarr/-/compare/v0.1.30...v0.1.31) (2026-03-07)


### Features

* add pack management for multi-magazine torrent bundles ([e5f3b4f](https://github.com/sharkhunterr/pressarr/-/commit/e5f3b4f62c13d9eb8727c35709595ea3788556dd))

### [0.1.30](https://github.com/sharkhunterr/pressarr/-/compare/v0.1.29...v0.1.30) (2026-03-07)


### Bug Fixes

* resolve TypeScript build errors in HistoryDetailModal ([943ba6c](https://github.com/sharkhunterr/pressarr/-/commit/943ba6cd6780570e0325b7f2ff02a43450183133))

### [0.1.29](https://github.com/sharkhunterr/pressarr/-/compare/v0.1.28...v0.1.29) (2026-03-07)


### Features

* add clickable history detail modal with structured event data ([ccd6b06](https://github.com/sharkhunterr/pressarr/-/commit/ccd6b06ad19ea69dfd4e166cbf2295979e28ccb7))

### [0.1.28](https://github.com/sharkhunterr/pressarr/-/compare/v0.1.27...v0.1.28) (2026-03-07)


### Features

* add library scan to discover and register existing files ([7d6de0a](https://github.com/sharkhunterr/pressarr/-/commit/7d6de0a91e2e6ec1d32fe43aead82fb222428843))

### [0.1.27](https://github.com/sharkhunterr/pressarr/-/compare/v0.1.26...v0.1.27) (2026-03-07)


### Bug Fixes

* add retry logic to CI verify stage for API propagation delays ([d64d204](https://github.com/sharkhunterr/pressarr/-/commit/d64d204cffea30ccedb37ead3ffb626ff567e2b5))
* clear processed state when re-grabbing the same torrent ([c16c73f](https://github.com/sharkhunterr/pressarr/-/commit/c16c73f3f9eee314ebfc878a0ad53368d37f6703))

### [0.1.26](https://github.com/sharkhunterr/pressarr/-/compare/v0.1.25...v0.1.26) (2026-03-07)


### Bug Fixes

* auto-grab/import bugs, add issue status editing and history modals ([b99de9f](https://github.com/sharkhunterr/pressarr/-/commit/b99de9fc8d1dd7708c87fd0a6370a785957c844f))

### [0.1.25](https://github.com/sharkhunterr/pressarr/-/compare/v0.1.24...v0.1.25) (2026-03-06)


### Bug Fixes

* issue viewer mobile responsiveness and error handling ([25f1633](https://github.com/sharkhunterr/pressarr/-/commit/25f16337e88ee4210806020cd31199bb96ab95e3))

### [0.1.24](https://github.com/sharkhunterr/pressarr/-/compare/v0.1.23...v0.1.24) (2026-03-06)


### Features

* add issue viewer for PDF, CBZ, and CBR files ([304e2a6](https://github.com/sharkhunterr/pressarr/-/commit/304e2a68584794cb37cef96680d09ac0b671f203))


### Bug Fixes

* issue viewer auth and double close button ([10a4e27](https://github.com/sharkhunterr/pressarr/-/commit/10a4e274b0a74271450d03a47264a1bcd73d9a97))

### [0.1.23](https://github.com/sharkhunterr/pressarr/-/compare/v0.1.22...v0.1.23) (2026-03-06)


### Features

* show grab/download source info in issue edit modal ([39168f3](https://github.com/sharkhunterr/pressarr/-/commit/39168f31865de8f0523a50f565dc9e93f0b78b56))


### Bug Fixes

* create issue as 'wanted' until grab succeeds ([4c608db](https://github.com/sharkhunterr/pressarr/-/commit/4c608dbd6c636dd594bf7a24c736f5fe96c72eb3))

### [0.1.22](https://github.com/sharkhunterr/pressarr/-/compare/v0.1.21...v0.1.22) (2026-03-06)


### Features

* add manual import button for snatched issues ([0843adf](https://github.com/sharkhunterr/pressarr/-/commit/0843adf100a0d4fa848074e45fec6ea9fab4cb09))


### Bug Fixes

* support dot-separated dates and detect quality tags in parentheses ([45eb171](https://github.com/sharkhunterr/pressarr/-/commit/45eb171ed6a4837aadc581ce6ac3e5d73a419145))

### [0.1.21](https://github.com/sharkhunterr/pressarr/-/compare/v0.1.20...v0.1.21) (2026-03-06)


### Bug Fixes

* prioritize query over magazineId in search endpoint ([f198108](https://github.com/sharkhunterr/pressarr/-/commit/f19810816cd5a1fc2318edf58cd19b63d010503f))

### [0.1.20](https://github.com/sharkhunterr/pressarr/-/compare/v0.1.19...v0.1.20) (2026-03-06)


### Bug Fixes

* add grab-registry fallback for download monitoring when Label plugin is unavailable ([17d3a07](https://github.com/sharkhunterr/pressarr/-/commit/17d3a07d1c6d4365f440f37bd2fc4fb997aa10e6))

### [0.1.19](https://github.com/sharkhunterr/pressarr/-/compare/v0.1.18...v0.1.19) (2026-03-06)


### Bug Fixes

* replace remaining Badge usage in IssueRow with StatusBadge ([e48928a](https://github.com/sharkhunterr/pressarr/-/commit/e48928ab27efca5d06bc3080ca3494f20450c1bc))

### [0.1.18](https://github.com/sharkhunterr/pressarr/-/compare/v0.1.17...v0.1.18) (2026-03-06)


### Bug Fixes

* unify status badges, fix forecast/wanted logic, exclude forecasts from stats ([a7f167b](https://github.com/sharkhunterr/pressarr/-/commit/a7f167b9e75ae9b7d92c8d93c3bcad0738a80e38))

### [0.1.17](https://github.com/sharkhunterr/pressarr/-/compare/v0.1.16...v0.1.17) (2026-03-06)


### Features

* add inline search bar, library grid/list toggle, and advanced sorting ([9125452](https://github.com/sharkhunterr/pressarr/-/commit/9125452dd07adf41cf21777ddc8ab440d8565845))
* add logs page with mobile-responsive design ([e1783ac](https://github.com/sharkhunterr/pressarr/-/commit/e1783ac74e24ac7d58075e42769669615c477f73))
* library badges, history improvements, calendar mobile fix, naming {day} ([b5c0393](https://github.com/sharkhunterr/pressarr/-/commit/b5c03933f7c145a19667d3510abae640140884d5))


### Bug Fixes

* handle "torrent already in session" in Deluge client ([b1818e4](https://github.com/sharkhunterr/pressarr/-/commit/b1818e4ec7cb7d1e481a624f1a333b2887818cc2))
* queue persistence across backend reloads and reduce warning spam ([5973f23](https://github.com/sharkhunterr/pressarr/-/commit/5973f23f61b0251716ac1203bee896ba67ab8870))

### [0.1.16](https://github.com/sharkhunterr/pressarr/-/compare/v0.1.15...v0.1.16) (2026-03-04)


### Bug Fixes

* should_upgrade() argument mismatch and queue persistence ([7751623](https://github.com/sharkhunterr/pressarr/-/commit/7751623c099a2a294263a2fdb415f26b36fcb823))

### [0.1.15](https://github.com/sharkhunterr/pressarr/-/compare/v0.1.14...v0.1.15) (2026-03-04)


### Bug Fixes

* prevent false positive matching, forecast deletion, and add remote logs ([a05fd5c](https://github.com/sharkhunterr/pressarr/-/commit/a05fd5c48a033d37ce7a74405d210579e4cc4427))

### [0.1.14](https://github.com/sharkhunterr/pressarr/-/compare/v0.1.13...v0.1.14) (2026-03-03)


### Features

* smart RSS matching, forecast promotion, and search history events ([57c3eaa](https://github.com/sharkhunterr/pressarr/-/commit/57c3eaa72a4b496221f8dfb09e1a9be91aae0918))

### [0.1.13](https://github.com/sharkhunterr/pressarr/-/compare/v0.1.12...v0.1.13) (2026-03-03)


### Features

* safe queue removal with confirmation dialog ([df3310f](https://github.com/sharkhunterr/pressarr/-/commit/df3310fb85c8770493dea64d7bc178dca2245f80))


### Bug Fixes

* prevent MissingGreenlet by eagerly loading client attributes ([327e82e](https://github.com/sharkhunterr/pressarr/-/commit/327e82ee94321ff3e8a3452ff8e692a260e131d8))

### [0.1.12](https://github.com/sharkhunterr/pressarr/-/compare/v0.1.11...v0.1.12) (2026-03-02)


### Bug Fixes

* improve monitor logging for completed downloads ([e8c4c4a](https://github.com/sharkhunterr/pressarr/-/commit/e8c4c4ac2c9f1695088d7302c33cd810d26919cc))

### [0.1.11](https://github.com/sharkhunterr/pressarr/-/compare/v0.1.10...v0.1.11) (2026-03-02)


### Bug Fixes

* pass issue/magazine association through import pipeline ([11bb518](https://github.com/sharkhunterr/pressarr/-/commit/11bb518293161c555c3d0016408925deb642dd0d))

### [0.1.10](https://github.com/sharkhunterr/pressarr/-/compare/v0.1.9...v0.1.10) (2026-03-02)


### Bug Fixes

* strict path resolution — no fallback, only exact torrent path ([3d739a7](https://github.com/sharkhunterr/pressarr/-/commit/3d739a727699b49652364f5b1cbccc5b25fe37d0))

### [0.1.9](https://github.com/sharkhunterr/pressarr/-/compare/v0.1.8...v0.1.9) (2026-03-02)


### Bug Fixes

* scope file discovery to torrent-specific path and fix DB session errors ([b63e5c6](https://github.com/sharkhunterr/pressarr/-/commit/b63e5c6900da907b6e206b78614bf5ff38cd982b))

### [0.1.8](https://github.com/sharkhunterr/pressarr/-/compare/v0.1.7...v0.1.8) (2026-03-02)


### Features

* recursive file discovery and manual import button in queue UI ([96827cb](https://github.com/sharkhunterr/pressarr/-/commit/96827cb90255cca648e27b32b56c65688069a42b))

### [0.1.7](https://github.com/sharkhunterr/pressarr/-/compare/v0.1.6...v0.1.7) (2026-03-02)


### Features

* **ui:** add remote path and local path fields to download client form ([466a61c](https://github.com/sharkhunterr/pressarr/-/commit/466a61c95dfdb22bf7f1d0de4dfcbc4a07519cde))

### [0.1.6](https://github.com/sharkhunterr/pressarr/-/compare/v0.1.5...v0.1.6) (2026-03-02)


### Features

* remote path mapping, persistent grab registry, and manual import ([2c29341](https://github.com/sharkhunterr/pressarr/-/commit/2c293413d23383dbdf1ba4f46c23f4258780dc51))

### [0.1.5](https://github.com/sharkhunterr/pressarr/-/compare/v0.1.4...v0.1.5) (2026-03-02)


### Bug Fixes

* SPA routing fallback and download monitor path resolution ([bb70575](https://github.com/sharkhunterr/pressarr/-/commit/bb705757c09aea6fb3dc1b690707fdbe673c7656))

### [0.1.4](https://github.com/sharkhunterr/pressarr/-/compare/v0.1.3...v0.1.4) (2026-03-02)


### Bug Fixes

* correct frontend static files path in CI Dockerfile ([5e04f83](https://github.com/sharkhunterr/pressarr/-/commit/5e04f83127f306bdf4cb2da275316680092e8e9a))

### [0.1.3](https://github.com/sharkhunterr/pressarr/-/compare/v0.1.2...v0.1.3) (2026-03-02)


### Bug Fixes

* correct frontend static files path in Dockerfile ([bd0c1d9](https://github.com/sharkhunterr/pressarr/-/commit/bd0c1d92ec82f5e70103dbb80a8e859e407f2784))
* resolve all ruff linting errors in backend ([dacb906](https://github.com/sharkhunterr/pressarr/-/commit/dacb9069ef7579537d01f7c10a286d02a8f2b6a7))
* resolve remaining E501 line-too-long ruff errors ([0b7e69d](https://github.com/sharkhunterr/pressarr/-/commit/0b7e69d03af79e158939a5ac4fd5cdc985f0b8a5))

### [0.1.2](https://github.com/sharkhunterr/pressarr/-/compare/v0.1.1...v0.1.2) (2026-03-02)


### Bug Fixes

* resolve CI failures in validate and test stages ([ce15d18](https://github.com/sharkhunterr/pressarr/-/commit/ce15d18803b1556d7258c60adb574e0930058e2f))

### 0.1.1 (2026-03-02)


### Features

* Anna's Archive integration, unified Manual Research modal, history lifecycle events, and file download ([6f875c8](https://github.com/sharkhunterr/pressarr/-/commit/6f875c81d7b458819c6033e16a9c51b8efcb7d37))
* branding overhaul with violet theme, logo, favicon, banner and README ([049885d](https://github.com/sharkhunterr/pressarr/-/commit/049885dcd25cc2f0ad294ec0d02ac8f913363c16)), closes [#E85D04](https://github.com/sharkhunterr/pressarr/-/issues/E85D04) [#7C3](https://github.com/sharkhunterr/pressarr/-/issues/7C3)
* complete specification and implementation planning for Pressarr (Feature 001) ([e9b1e96](https://github.com/sharkhunterr/pressarr/-/commit/e9b1e969c51043409cd6e736c6d43b4e8b902a02))
* cover picker in magazine edit modal with auto-update toggle ([809f0c7](https://github.com/sharkhunterr/pressarr/-/commit/809f0c7b3e95b83b205e7a0b51ebc02fb69a7648))
* cover upload from file or URL in magazine edit modal ([418af5b](https://github.com/sharkhunterr/pressarr/-/commit/418af5bcaa619b25a58c909d076e4c6a2d11a88b))
* excluded days for magazine forecast generation, day column, import mode, and misc fixes ([2b2991b](https://github.com/sharkhunterr/pressarr/-/commit/2b2991b84385ebbf487ea165b107ff28c4678cf1))
* grab registry, issue edit/delete dialog, and hide unknown quality ([3dfa192](https://github.com/sharkhunterr/pressarr/-/commit/3dfa19257428e1df2f9f29db9f8dfe1a73498c2a))
* group magazine search results by title with per-provider count badges ([be6f45e](https://github.com/sharkhunterr/pressarr/-/commit/be6f45e4b04058af6afd51b2b17a7d8fcb3c837d))
* implement full Pressarr application (Feature 001) ([bccb6d2](https://github.com/sharkhunterr/pressarr/-/commit/bccb6d28ae3a8fb4fb926e95b183615e1037e706))
* implement project foundation (Feature 000) ([5b6cc34](https://github.com/sharkhunterr/pressarr/-/commit/5b6cc342c30428baa01af147340f39df04e8d5d2))
* indexer search with source name, publish date, filtering, sorting and pagination ([e91bc19](https://github.com/sharkhunterr/pressarr/-/commit/e91bc1971ad4b92c8e435e0785e1b5c605a17687))
* upcoming filter badge, monitored badge next to title, and mobile layout fixes ([80bd732](https://github.com/sharkhunterr/pressarr/-/commit/80bd7325840ef183cdf2774fb1ff3cef7c16bd9c))


### Bug Fixes

* auto-create issue on grab, bare number parsing, and unified queue display ([832102e](https://github.com/sharkhunterr/pressarr/-/commit/832102eadca9dac3f5a47c4900481019a94046de))
* dark theme, sidebar navigation, download client test and password handling ([ec754d3](https://github.com/sharkhunterr/pressarr/-/commit/ec754d34c986c44b3b91713b6c1e30b31a25f48a))
* include day field in issue rename template context ([500b599](https://github.com/sharkhunterr/pressarr/-/commit/500b599c1954f780376389abb6278babe2500d7b))
* metadata search, IA downloads, settings API, and queue filtering ([33af7b1](https://github.com/sharkhunterr/pressarr/-/commit/33af7b19589494f8a41993a4fc04b52ea22d395d))
* queue stale display, forecast numbering, edit modal, collapsible upcoming, import conflicts ([e7a7882](https://github.com/sharkhunterr/pressarr/-/commit/e7a78828a2742cb5b6fe6142a723f54b06c48d06))
* uniform full-width layout and responsive padding on all pages ([2cdbcca](https://github.com/sharkhunterr/pressarr/-/commit/2cdbccaa5a3aa02943fb5859dccc1b457ab2714e))
