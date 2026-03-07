# Changelog

All notable changes to this project will be documented in this file. See [standard-version](https://github.com/conventional-changelog/standard-version) for commit guidelines.

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
