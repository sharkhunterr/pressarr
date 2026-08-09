# Changelog

All notable changes to this project will be documented in this file. See [standard-version](https://github.com/conventional-changelog/standard-version) for commit guidelines.

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
