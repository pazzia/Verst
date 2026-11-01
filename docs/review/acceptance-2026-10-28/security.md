# Приёмка «Версты» 28.10.2026 — аудит безопасности

Роль: специалист по информационной безопасности (AppSec + инфраструктура). Проверено по коду и конфигам ветки
`ccr-013d3489-181fz2` (HEAD `311da51`); тестовый сервер `https://212-108-82-26.sslip.io` из песочницы недоступен —
живые проверки вынесены в раздел 7 как команды для CEO. Что удалось запустить здесь: тесты API на настоящем
PostgreSQL 16 (`112 passed in 15.78s`), собственные пробы API через Starlette `TestClient` (без сети), скилл
`security-review` по диффу ветки, grep секретов по репозиторию, проверка видимости репозитория через GitHub API.

## 1. Вердикт

**Принимаю для тестов с друзьями и семьёй — при трёх условиях, одно из которых блокирующее.** Серверная часть
сделана заметно аккуратнее, чем обычно бывает у MVP: случайные bearer-токены с хранением только sha256,
параметризованный SQL, строгие схемы (`extra="forbid"`), приватизация поездок перед хранением (проверил пробой:
набранный адрес и точные координаты в публичный JSON не попадают), единая ошибка без утечки стека, контейнер без
root и с read-only ФС, зависимости с хешами. Приложение не ходит по cleartext, не делает бэкап, просит ровно четыре
разрешения, аналитика без геолокации и рекламных ID. Но: (1) **ключ подписи демо-сборки с паролем лежит в публичном
репозитории** — любой может собрать APK, который встанет *поверх* сборки тестеров и унаследует их токен и
данные; это надо закрыть до следующей рассылки APK; (2) в приложении нет политики конфиденциальности и согласия,
а точная GPS-точка старта (часто — дом), набранный адрес и состав экипажа при включённом «На сервере» уходят на
VPS в Нидерландах — для тестов с друзьями нужно хотя бы короткое согласие тестеров; (3) живой сервер по коду
выглядит правильно, но реальная конфигурация (`VERST_ENV`, HSTS, что открыто наружу) не проверена — чек-лист
раздела 7 нужно прогнать один раз. Для беты с реальными пользователями (не друзьями) вердикт — «нет» до переезда
бэкенда в РФ и появления политики/оператора ПДн, что команда и так планирует (ADR-0020 §11, R-07, R-13).

## 2. Оценка: 7 / 10

Серверный код и инфраструктура — уровень «можно показывать аудитору», но релизный контур (ключ подписи в
публичном репо) и юридическая обвязка ПДн отстают от кода.

## 3. Что сделано хорошо

1. **Аутентификация устройств.** Токен — 32 случайных байта `secrets.token_urlsafe` (`backend/api/verst_api/store.py:24-26`),
   в БД только `sha256` (`store.py:29-30`, `migrations/0001_api_beta.sql:241` с CHECK на 32 байта), заголовок
   принимается только по строгому регэкспу на 43 символа (`deps.py:23,42`), отозванные токены отвергаются
   (`store.py:76-77`, тест `test_revoked_token_is_rejected`). Приложение хранит токен только для того `baseUrl`,
   для которого он выдан (`Server.kt:142`), и при 401 перерегистрируется ровно один раз (`Server.kt:97-100`).
2. **Валидация и SQL.** Все запросы параметризованы (`store.py`, единственная f-строка в `_trip_where` подставляет
   внутренние константы, `store.py:161-162`); входные модели `extra="forbid"` со строгими типами
   (`schemas.py:22-23, 50-92`); slug и id поездки проверяются регэкспом на роутере (`routes.py:292-293,305`) и
   CHECK-ограничениями в БД (`0001_api_beta.sql:250,253`). Проба: `/v1/shared/%27%20OR%201%3D1--` → 400 INVALID_INPUT,
   путь с `../` → 404.
3. **Приватизация данных (R-07) работает.** `scrub_trip` заменяет метки пользователя на город и округляет все
   координаты до 2 знаков (`privacy.py:84-131`); проба: после сохранения плана «ул. Тверская, 1 → Казань» в
   публичном JSON `input.origin = {lat: 55.76, lon: 37.62, label: "Москва"}`, строки «Тверская» и «37.6173»
   отсутствуют. Телефоны/почты в отзывах маскируются и текст стирается через 180 дней (`privacy.py:151-154`,
   `store.py:227-231`). Access-логи выключены везде (`Caddyfile:2-3`, `nginx-*.conf.example:12,20`,
   `entrypoint.sh:15`), JSON-лог округляет `lat`/`lon` даже в `extra` (`logs.py:203`).
4. **Ошибки не текут.** Один конверт `{code, message, details}` (`errors.py:409-410`), необработанные исключения →
   `INTERNAL` без деталей (`errors.py:474-478`, тест `test_internal_errors_do_not_leak`), лимит тела 2 МБ и на прокси,
   и в ASGI-middleware с учётом chunked (`middleware.py:312-335`).
5. **Страница шаринга.** Всё через `html.escape`, CSP `default-src 'none'`, `X-Robots-Tag: noindex`,
   `Referrer-Policy: no-referrer`, никаких внешних ресурсов (`share_page.py:278-286, 311-326`). XSS не нашёл.
6. **Контейнер и поставка.** Non-root uid 10002, `read_only: true`, `cap_drop: [ALL]`, `no-new-privileges`
   (`infra/api/docker-compose.yml:39-44`, `Dockerfile:26-27`), `pip install --require-hashes` по полному локу
   (239 хешей, `Dockerfile:14-16`), наружу опубликован только прокси; `/metrics`, `/readyz`, `/docs`, `/openapi.json`
   отдают 404 на прокси (`Caddyfile:10-11`, `nginx-verst*.conf.example:16-18/26-28`); GraphHopper без аутентификации
   по умолчанию привязан к `127.0.0.1` (`infra/routing/docker-compose.yml:19`). `env=prod` отказывается стартовать
   с дефолтным секретом или http-адресом (`settings.py:152-158`, тест `test_settings_refuse_unsafe_configs`).
7. **Приложение.** Cleartext запрещён, кроме loopback для e2e (`network_security_config.xml:8-12`),
   `allowBackup="false"` (`AndroidManifest.xml:31`), ровно 4 разрешения и CI это проверяет по merged-манифесту
   (`android.yml:145-149`, `ci-logs/.../build/permissions.txt`), `AD_ID` вырезан (`AndroidManifest.xml:12`).
   AppMetrica: геолокация и рекламные ID выключены (`VerstAnalytics.kt:50-56`), каждое событие проходит
   `PrivacyGuard` (`PrivacyGuard.kt`). Интенты в навигатор ограничены пакетом (`Platform.kt:146`), координаты в
   ссылках валидируются по диапазону (`NaviLinks.kt:10-13`). План на сервере — opt-in (`AppSettings.kt:30`), и экран
   честно пишет, что именно уходит (`strings.xml:914`). Python-движок — stdlib, без `pickle`/`eval`/`subprocess`
   (grep по `backend/planner/verst_planner`).

## 4. Замечания

Серьёзность — по реальной эксплуатируемости на текущей стадии (тесты с друзьями, публичный репозиторий).

### Критичные

**К-1. Ключ подписи демо-сборки и пароли к нему — в публичном репозитории.** *(high)*
- Доказательство: `android/app/demo.keystore` в git (`git ls-files`), пароли `storePassword = "verstdemo"`,
  `keyPassword = "verstdemo"` в `android/app/build.gradle.kts:46-51`; этим же ключом подписаны типы `demo` и
  `debug` (`build.gradle.kts:60,66`). Репозиторий `pazzia/Verst` публичный (`gh api repos/pazzia/Verst` →
  `"visibility":"public"`), файл доступен на `main` (`contents/android/app/demo.keystore`, 2624 байта), APK
  публикуются в GitHub Releases (`mvp-mock-latest`, `mvp-mock-151`, …).
- Сценарий: кто угодно собирает APK с `applicationId = app.verst.demo` и этой подписью (например, с добавленным
  кодом, который читает `files/settings/server.json` и `files/trips/saved.json` и шлёт их наружу), и присылает
  тестеру «новую сборку». Android ставит её *поверх* установленной без предупреждения — подпись совпадает, — и она
  наследует bearer-токен сервера, сохранённые поездки с точными координатами и уже выданное разрешение на
  геолокацию. Для друзей и семьи CEO это целевой, но реалистичный фишинг; для будущего релиза — скомпрометирован
  сам релизный контур (`isMinifyEnabled = false`, так что и код читается).
- Рекомендация: (1) сгенерировать новый keystore вне репозитория, положить в GitHub Secrets (base64) и
  расшифровывать в CI, пароли — тоже секреты; (2) `git rm` старого ключа (история остаётся — ключ считать
  скомпрометированным навсегда); (3) тестерам один раз удалить приложение и поставить новую сборку (данные
  поездок локальные — предупредить); (4) в релиз-нотах уже есть sha256 — добавить отпечаток сертификата, чтобы
  тестер мог сверить `apksigner verify --print-certs`. Релизный `release` buildType ключом пока не подписан
  (`build.gradle.kts:70-72`) — хорошо, оставить так.

### Важные

**В-1. Персональные данные уходят за границу без политики и согласия (152-ФЗ).** *(medium — юридический, не
технический риск)*
- Доказательство: сервер зашит в CI — `VERST_SERVER_URL: https://212-108-82-26.sslip.io` (`.github/workflows/android.yml:53-54`,
  VPS в Нидерландах по `infra/api/README.md:51-57`). При включённом «На сервере» в теле `POST /v1/trips/plan`
  уходят точные `lat`/`lon` и `label` (набранный адрес) старта, финиша и промежуточных точек
  (`core-model/.../EngineJson.kt:242-256`, `schemas.py:50-56` допускает `label` до 200 символов), состав экипажа с
  возрастами детей (`schemas.py:58-62`), бюджет. Точка старта «отсюда» — это GPS-координата телефона
  (`Platform.kt:50-64`). Строка `settings_privacy` «Политика конфиденциальности ↗» объявлена (`strings.xml:219`),
  но нигде не используется (grep по `android/`): ни политики, ни экрана согласия в приложении нет. Оператор — физлицо
  без юрлица (`docs/legal/risk-register.md`, R-13). Сам реестр рисков (R-07) всё это фиксирует честно.
- Чем грозит: тестеры — реальные субъекты ПДн; связка «постоянный ID устройства + домашняя точка + состав семьи»
  — ПДн по ст. 3; передача на сервер вне РФ — трансграничная (ст. 12), первичная запись/хранение — ст. 18 ч. 5.
  Для теста с друзьями штрафной риск близок к нулю, но при инциденте (К-1) у вас нет ни уведомления, ни
  согласий, ни документа «что храним и сколько».
- Смягчает: опция по умолчанию выключена (`AppSettings.kt:30`), экран предупреждает («На сервер уходят точки
  маршрута и состав экипажа. Поездки на нём не хранятся», `strings.xml:914`), сервер планы не хранит
  (`routes.py:328`), логирует координаты с 2 знаками (`routes.py:333-336`), IP — только HMAC в ключах лимитов.
- Рекомендация: (1) до рассылки сборки с сервером — короткое согласие тестера в приложении перед включением «На
  сервере» (что уходит, куда, что сервер за рубежом, срок хранения, как удалить) и письменное/в мессенджере
  согласие друзей; (2) документ-страница политики (на русском) по пунктам SPEC §16/R-07 и ссылка на неё с уже
  существующей строки `settings_privacy`; (3) зафиксировать срок жизни `api.device` без активности (сейчас
  бессрочно: `last_seen_at` есть, чистки нет — `store.py:215-234` чистит только счётчики и текст отзывов) и
  сохранённых поездок (ADR-0020 §11: «до удаления устройством»); (4) бета с чужими людьми — только после
  переезда на хостинг в РФ (уже запланировано).

**В-2. Лимиты обходятся регистрацией устройств; движок — один поток на процесс.** *(medium — доступность)*
- Доказательство: регистрация 20/ч на IP (`deps.py:83-90`, `settings.py:137`), лимит планов 30/ч *на устройство*
  (`deps.py:72-80`); проверил локально: 20 регистраций с одного адреса проходят, 21-я → 429 с `Retry-After`, а план
  со второго устройства не упирается в лимит первого. Итого 600 планов/ч с одного IP, сохранений — 400/ч ×
  2 МБ × 50 поездок на устройство (`settings.py:141-142`). Движок — `ThreadPoolExecutor(max_workers=1)` на процесс
  (`engine.py:61-69`), воркеров два (`entrypoint.sh:13`, `.env.example:16`); план держит поток до 25 с
  (`settings.py:128`), отмена — только на чекпойнтах движка (`sse.py:339-342`, `engine.py:178`). В режиме
  `road_model` план у меня занял 0,21 с, с GraphHopper будет заметно дольше. Через CGNAT мобильных операторов
  IP-лимит ещё и задевает честных пользователей.
- Сценарий: пул прокси/ботнет на несколько десятков адресов забивает очередь движка; планы честных тестеров
  получают `UPSTREAM/timeout`. Смягчает: клиент при 5xx/таймауте автоматически строит план на телефоне
  (`ServerPlannerGateway.kt:45-46`), поэтому для пользователя это деградация, а не отказ. Хранилище: 2 ГБ/ч с одного
  IP при желании — тоже возможно.
- Рекомендация: (1) семафор одновременных планов на процесс и немедленный 503 `UPSTREAM` при переполнении очереди
  (сейчас запрос ждёт в очереди и сгорает по таймауту); (2) суточный лимит регистраций на IP (например, 40/сут)
  плюс глобальный лимит регистраций в час; (3) лимит общего объёма сохранённых поездок на устройство в байтах;
  (4) при переезде в РФ — Cloudflare/антиDDoS-прокси провайдера перед Caddy.

**В-3. Публичная ссылка «поделиться» отдаёт больше, чем «город старта».** *(medium — приватность)*
- Доказательство: `GET /v1/shared/{slug}` возвращает весь `trip` (`routes.py:447-461`, `schemas.py:222-229`);
  проба: 209 КБ, внутри `input.crew = {adults: 2, children: 1, childAges: [6], dog: true}`, `input.budget = 45000`,
  `input.startAt = "2026-10-24T08:00"`, `input.vehicle`, `engineState` (внутренние данные движка). HTML-страница
  `/s/{slug}` показывает только текст — хорошо (`share_page.py:311-326`), но JSON читается любым `curl`.
- Чем грозит: ссылка пересылается дальше, чем задумывал автор; по ней видно город, дату выезда и состав семьи —
  «когда дома никого нет», плюс бюджет. Slug 8 символов Crockford (40 бит) при 300 запросах/ч на IP не
  перебирается — проблема только в содержимом.
- Рекомендация: в `SharedTripOut.trip` оставить то, что нужно экрану получателя (дни и остановки, итоговая
  смета без `budgetRub`), убрать `input.budget`, `childAges`, точное `startAt` (оставить месяц), `vehicle`,
  `engineState`; завести тест по аналогии с `test_share_page_and_shared_json_show_the_town_only`.

### Мелкие

**М-1. `--forwarded-allow-ips "*"` — оправдано только пока порт 8000 не виден снаружи.** *(low)*
`entrypoint.sh:14` доверяет `X-Forwarded-For` от любого соседа; в compose порт только `expose` (`docker-compose.yml:45-46`),
в варианте host-nginx — `127.0.0.1:8000` (`docker-compose.host-nginx.yml:11`), nginx заголовок *заменяет*
(`nginx-verst*.conf.example:25/35`). Обойти IP-лимиты сможет лишь процесс на самом хосте или контейнер той же
compose-сети (`graphhopper`, `backup`). Рекомендация: указать подсеть docker/адрес прокси вместо `*`, и — главное —
живая проверка, что 8000 не слушает на внешнем интерфейсе (раздел 7). Если на тестовой VM стоит
`VERST_ENV=dev`, то `/docs` и `/openapi.json` включены в приложении (`main.py:232-234`) и спасает только 404 на
nginx — тоже в чек-лист.

**М-2. Токен устройства — в открытом файле, бессрочный, без отзыва из приложения.** *(low)*
`files/settings/server.json` (`AppPrefs.kt:71-85`) — приватное хранилище приложения, бэкап выключен; на
рутованном телефоне читается. Ротации нет, эндпоинта «забыть устройство» нет (ADR-0007: «revocation by setting
`revoked_at`» — руками в БД). Рекомендация: `DELETE /v1/devices/me` и кнопка «Отвязать от сервера» (удаляет
`server.json`); для релиза — `EncryptedFile`/Keystore не обязателен, но дёшев.

**М-3. Клиент читает SSE-поток и JSON-ответ сервера без ограничения размера.** *(low, теоретический)*
`Server.kt:117-121` (`readUtf8Line` без лимита), `Server.kt:102,105` (`body.string()`), тогда как для Nominatim
есть `jsonBodyOrNull(1 МБ)` (`Online.kt:125-133`). Эксплуатируется только скомпрометированным сервером или MITM с
подменённым корневым сертификатом (пиннинга нет — для тест-сервера на Let's Encrypt это нормально). Рекомендация:
лимит на строку/тело (например, 4 МБ) и `ServerUnavailable` при превышении; пиннинг — не раньше релиза и на
промежуточный/корневой CA.

**М-4. CI: права и закрепление зависимостей.** *(low)*
`android.yml:21,43-44` — `pull_request` плюс `permissions: contents: write` в публичном репо (для PR из форков
GitHub выдаёт read-only токен, так что практического пути нет; но для PR из веток репо — write); `planner.yml` без
блока `permissions` (наследует дефолт репозитория) и `pip install ruff mypy` без версий (`planner.yml:16`); все
`uses:` закреплены тегами (`actions/checkout@v4`, `reactivecircus/android-emulator-runner@v2`), а не SHA;
`data.yml:52` качает `russia-latest.osm.pbf` без контрольной суммы; базовые образы Docker по тегу, не по digest
(README это признаёт). Хорошо: `head_commit.message` передаётся через `env`, а не подставляется в скрипт
(`android.yml:345-347, 431-433`); jar GraphHopper проверяется по sha256 (`routing.yml:78-83`,
`infra/routing/Dockerfile:5-6,16`). Рекомендация: `permissions: contents: read` по умолчанию на уровне репо,
`write` только job'ам `release`/`ci-logs`; SHA-пиннинг действий; версии в `pip install`.

**М-5. В публичную ветку `ci-logs` уходит полный logcat эмулятора.** *(info)*
`tools/ci/run_e2e.sh:87-89` пишет `logcat-full.txt.gz`, а workflow удаляет только `logcat.txt`
(`android.yml:307`); в прогоне 40591934106-1 это 54 542 строки. Сейчас там нет ни токенов, ни следов сервера
(e2e ходят в MockWebServer, `Sprint4Test.kt:128`), координаты — синтетический `geo fix` Тулы. Но при появлении
серверных e2e туда попадут ответы/ошибки API. Рекомендация: оставлять только `logcat-filtered.txt` или
фильтровать `Verst*` перед публикацией.

**М-6. Логи приложения.** *(info)* `Platform.kt:117,132` пишет в logcat web-ссылку с координатами маршрута при
отсутствии браузера. Локально, в ci-logs не попадает. Токен ни в одном `Log.*` не встречается (grep).

**М-7. Бэкапы.** *(low)* Дампы незашифрованные в `/srv/verst/backups` (0700 root — `infra/api/README.md:31`), содержат
хеши токенов и приватизированные поездки; off-site копия — вручную. Рекомендация: шифровать (`age`/`gpg`) перед
копированием, хранить ключ вне VM; `restore-drill.sh` — хороший инструмент, прогонять ежемесячно, как написано.

**М-8. Заголовки.** *(info)* HSTS есть у Caddy и у certbot-варианта (`Caddyfile:22`, `nginx-verst-certbot.conf.example:23`),
но без `includeSubDomains`/`preload` (для sslip-имени не нужно); в `nginx-verst.conf.example` (порт 80) HSTS нет —
его должен добавить `certbot --nginx` в 443-блок: проверить вживую. `frame-ancestors` в CSP страницы шаринга нет,
но на странице нечего кликать.

**М-9. `fetch_rates.py`.** *(info)* Парсит XML ЦБ стандартным `xml.etree` (`tools/ci/fetch_rates.py:24`): внешние
сущности expat по умолчанию не раскрывает, источник — HTTPS ЦБ; результат вшивается в APK. Приемлемо.

### Что искал и не нашёл

Секреты: по всему репозиторию (ключи AWS/GitHub/Slack/Google, `BEGIN PRIVATE KEY`, `password=`, `.env`,
`*.pem/*.jks`) — только `demo.keystore` (К-1) и CI-пароль `verst-ci-only` для сервиса Postgres в `api.yml:41`
(используется только в CI). Ключ подписи ссылок Яндекс.Навигатора в приложении не хранится: `HandoffSigner`
создаётся только в тестах (`HandoffSignerTest.kt`), в рантайме `handoffSigner == null` (`VerstFlow.kt:220`).
Open redirect: `links.py` строит только `https://travel.yandex.ru/hotels/search/?…` с `urlencode`, редиректов нет.
XXE/десериализация/pickle/eval в движке и API — нет. CORS: middleware CORS не подключён, preflight → 404 без
`Access-Control-Allow-Origin` (проба) — для мобильного API правильно. Инъекции через ответы сервера в приложение:
JSON декодируется `kotlinx.serialization` с `ignoreUnknownKeys` (`EngineJson.kt:33`), ссылки в навигатор
собираются из чисел с проверкой диапазонов, интенты ограничены пакетом — путей нет.

### Результат скилла `security-review` по диффу ветки (7 коммитов, 24 файла)

По критериям скилла (только >80 % уверенности, без DoS/лимитов/секретов на диске) — **находок HIGH/MEDIUM нет**.
Проверены: `Server.kt` (токен отдаётся только `BuildConfig.SERVER_URL`, который задаётся переменной окружения CI;
повторная регистрация один раз; ответ сервера парсится, не исполняется), `ServerPlannerGateway.kt`,
`AppPrefs.kt`, `SettingsRoute.kt`, `nginx-verst*.conf.example` (XFF заменяется, не дописывается),
`docker-compose.host-nginx.yml` (loopback), `routing.yml`/`load_test.py` (без недоверенного ввода),
`android.yml` (URL в `env`). Всё, что найдено выше (К-1, В-1…В-3), относится к коду, существовавшему до этой
ветки, либо исключено правилами скилла — потому и вынесено в общий отчёт.

## 5. Чего не удалось проверить

- **Живой сервер:** версия/конфиг nginx-certbot, фактические TLS-параметры и заголовки, что `/metrics`, `/readyz`,
  `/docs` действительно 404 снаружи, что порты 8000/5432/8989 не торчат наружу, `VERST_ENV=prod` и секреты в
  `.env`, что `uvicorn` получает корректный `X-Forwarded-For` (лимиты по IP работают), что HTTP редиректит на HTTPS.
- **Сборка APK:** подпись реальных релизов (`apksigner`), наличие тестового ключа AppMetrica в демо-сборке (в CI
  он берётся из `VERST_APPMETRICA_TEST_KEY`; пустой — аналитика выключена, `build.gradle.kts:18-27`).
- **Нагрузка:** время плана с GraphHopper и реальное поведение очереди (В-2) — на тестовой VM GraphHopper не
  поднят (`VERST_ROUTING=road_model`).
- **История git** на предмет когда-либо закоммиченных секретов — не копал по условию задания; с учётом К-1 имеет
  смысл один раз прогнать `gitleaks detect` по всей истории.

## 6. Три шага, которые я сделал бы первыми

1. **Сегодня:** новый keystore вне репозитория → GitHub Secrets → CI; удалить `demo.keystore` и пароли из
   `build.gradle.kts`; попросить тестеров переустановить следующую сборку (К-1).
2. **До следующей рассылки с сервером:** экран согласия перед переключателем «На сервере» + страница политики на
   русском, подвешенная на уже существующую строку `settings_privacy`; срок хранения устройств и поездок записать
   в политику и в `cleanup` (В-1).
3. **На этой неделе:** прогнать чек-лист раздела 7 на тестовой VM и сузить `/v1/shared/{slug}` до нужных полей
   (В-3); заодно — семафор и лимит очереди планов (В-2).

## 7. Чек-лист живых проверок для CEO (только чтение, свой хост)

Все команды — со своей машины против своего сервера; ничего не ломают. `H=212-108-82-26.sslip.io`.

**Снаружи**

```sh
H=212-108-82-26.sslip.io

# 1. Что открыто наружу. Ожидание: только 22 (и то лучше по allow-list), 80, 443; 8000/5432/8989/8990/8080 — closed/filtered.
nmap -sV -p 22,80,443,5432,8000,8080,8989,8990 $H

# 2. Сертификат и TLS. Ожидание: issuer Let's Encrypt, срок > 2 недель, TLS 1.2/1.3, без TLS 1.0/1.1.
openssl s_client -connect $H:443 -servername $H </dev/null 2>/dev/null | openssl x509 -noout -subject -issuer -dates
openssl s_client -connect $H:443 -servername $H -tls1_1 </dev/null 2>&1 | grep -E 'Protocol|handshake failure|no protocols'

# 3. HTTP → HTTPS и заголовки. Ожидание: 301/308 на https; в ответе HSTS, X-Content-Type-Options: nosniff, нет Server: nginx/x.y.
curl -sI http://$H/healthz | head -3
curl -sI https://$H/healthz | grep -i -E '^(strict-transport-security|x-content-type-options|server|x-request-id|content-type):'

# 4. Приватные эндпоинты. Ожидание: все 404.
for p in metrics readyz docs docs/ openapi.json; do printf '%-13s ' "$p"; curl -s -o /dev/null -w '%{http_code}\n' "https://$H/$p"; done

# 5. Ошибки без деталей. Ожидание: 401 {"error":{"code":"UNAUTHORIZED",...}} и 404 NOT_FOUND без стека/версий.
curl -s -X POST https://$H/v1/trips/plan -H 'Content-Type: application/json' -d '{}'; echo
curl -s https://$H/v1/nope; echo
curl -s https://$H/s/aaaaaaaa | head -c 300; echo

# 6. Лимит тела. Ожидание: 413 (от nginx или PAYLOAD_TOO_LARGE от API).
head -c 3000000 /dev/zero | tr '\0' 'a' | curl -s -o /dev/null -w '%{http_code}\n' -X POST https://$H/v1/devices -H 'Content-Type: application/json' --data-binary @-

# 7. Регистрация и лимит по IP. Ожидание: 20 × 201, затем 429 с Retry-After; X-Forwarded-For снаружи ничего не меняет.
for i in $(seq 1 21); do curl -s -o /dev/null -w '%{http_code} ' -X POST https://$H/v1/devices \
  -H 'Content-Type: application/json' -H 'X-Forwarded-For: 203.0.113.9' -d '{"appVersion":"audit-ceo","locale":"ru-RU"}'; done; echo
# после проверки на VM: docker compose exec postgres psql -U verst_api -d verst -c "UPDATE api.device SET revoked_at=now() WHERE app_version='audit-ceo'"

# 8. Тайм-аут потока. Ожидание: ответ text/event-stream, ": ping" каждые 5 с, завершение не позже ~25 с.
TOKEN=$(curl -s -X POST https://$H/v1/devices -H 'Content-Type: application/json' -d '{"appVersion":"audit-ceo"}' | sed 's/.*"token":"\([^"]*\)".*/\1/')
curl -s -N --max-time 40 -X POST https://$H/v1/trips/plan -H "Authorization: Bearer $TOKEN" -H 'Accept: text/event-stream' \
  -H 'Content-Type: application/json' -d '{"origin":{"lat":55.7558,"lon":37.6173},"destination":{"lat":55.7887,"lon":49.1221},"crew":{"adults":2},"dailyKm":500}' | head -c 600
```

**На VM**

```sh
cd /srv/verst/src/infra/api   # или где лежит compose
docker compose -f docker-compose.yml -f docker-compose.host-nginx.yml ps          # api/postgres healthy, proxy и graphhopper не подняты
ss -ltnp | grep -E ':(8000|5432|8989|8990)\b'                                       # 8000 только 127.0.0.1; 5432/8989 не слушают на хосте
grep -E '^(VERST_ENV|VERST_PUBLIC_BASE_URL|VERST_RATE_KEY_SECRET|POSTGRES_PASSWORD)=' .env | sed -E 's/=(.{4}).*/=\1…/'   # prod, https, оба секрета непустые
stat -c '%a %U %n' .env /srv/verst/backups                                         # 600 root, 700 root
docker inspect $(docker compose ps -q api) --format '{{.HostConfig.ReadonlyRootfs}} {{.HostConfig.CapDrop}} {{.HostConfig.SecurityOpt}} {{.Config.User}}'   # true [ALL] [no-new-privileges:true] verst
docker compose logs --since 24h api | grep -v '"level": "INFO"' | tail -20          # без ERROR
docker compose logs --since 24h api | grep -o '"origin": \[[^]]*\]' | sort -u | head  # только 2 знака после запятой
docker compose exec postgres psql -U verst_api -d verst -c "SELECT count(*) devices, count(*) FILTER (WHERE revoked_at IS NULL) live, min(created_at) FROM api.device" -c "SELECT count(*) FROM api.trip" -c "SELECT count(*) FROM api.feedback WHERE text IS NOT NULL"
ls -la /srv/verst/backups/daily | tail -3 && VERST_BACKUP_DIR=/srv/verst/backups ./restore-drill.sh   # «restore drill OK»
sudo ufw status verbose 2>/dev/null || sudo iptables -S INPUT | head                 # 22 ограничен, 8000/5432 закрыты
UC=$(docker inspect nginx-nginx-1 --format '{{range .Mounts}}{{if eq .Destination "/etc/nginx/user_conf.d"}}{{.Source}}{{end}}{{end}}'); grep -n -E 'add_header|return 404|X-Forwarded-For|client_max_body_size|access_log' "$UC/verst.conf"
```

**На телефоне тестера (adb, по желанию)**

```sh
adb shell dumpsys package app.verst.demo | grep -A3 'signatures'      # сверить с отпечатком НОВОГО ключа после К-1
adb logcat -d | grep -E 'VerstServer|Bearer|sslip'                      # ожидание: ни токена, ни URL с координатами
adb shell run-as app.verst.demo ls files/settings 2>&1                  # ожидание: «not debuggable» — файл с токеном недоступен
```
