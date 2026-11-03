# Тестовый сервер «Версты»: подключение, устройство, база данных

Состояние на 01.11.2026. В этом файле нет паролей и ключей: они хранятся только в `/srv/verst/src/infra/api/.env` на сервере.

> **152-ФЗ.** Это ВМ в Нидерландах, только для тестов (друзья и команда). До беты с реальными пользователями всё переезжает на сервер в России (D-IR-21).

## 1. Сервер

| Что | Значение |
| --- | --- |
| Машина | ВМ `nl-vmnano`, IP `212.108.82.26` |
| Ресурсы | 6 ГБ памяти без подкачки, диск 58 ГБ |
| Адрес API для приложения | `https://212-108-82-26.sslip.io` |
| Вход | SSH под `root`: `ssh root@212.108.82.26` |
| Код | `/srv/verst/src` (git-клон репозитория) |
| Настройки сервера | `/srv/verst/src/infra/api/.env` |
| Резервные копии базы | `/srv/verst/backups` |
| Граф дорог | `/srv/verst/routing/current` (предыдущий хранится в `previous`) |

### Как устроено (Docker, проект `verst`)

```
интернет ──HTTPS──▶ nginx на сервере ──▶ 127.0.0.1:8000 verst-api-1 (FastAPI + движок)
                                              │
                         ┌────────────────────┼────────────────────┐
                         ▼                    ▼                    ▼
                verst-postgres-1      verst-graphhopper-1    verst-backup-1
                (PostgreSQL 16)       (дороги России)        (копия базы в 03:00 МСК)
```

- **Порты наружу:** открыт только nginx. База (5432) и GraphHopper (8989) доступны только внутри Docker.
- **Закрытые адреса:** `/metrics`, `/readyz`, `/docs`, `/openapi.json` снаружи закрыты (`nginx-verst.conf.example`).
- **Docker-файлы:**
  - `infra/api/docker-compose.yml` — основной;
  - `infra/api/docker-compose.host-nginx.yml` — настройки для этой ВМ: nginx вместо Caddy, меньше памяти, GraphHopper с графом на диске (`-Xmx1g`, лимит 2 ГБ).

### Что включено в `.env`

| Переменная | Значение | Смысл |
| --- | --- | --- |
| `VERST_ROUTING` | `graphhopper` | Реальные дороги (с 01.11) |
| `VERST_GRAPHHOPPER_URL` | `http://graphhopper:8989` | Адрес внутри Docker |
| `VERST_SYNTHETIC_FALLBACK` | `true` | Если GraphHopper упал, сервер считает по модели дорог и помечает маршрут как приблизительный |
| `POSTGRES_PASSWORD` | секрет | Пароль базы |
| `VERST_RATE_KEY_SECRET` | секрет | Ключ для обезличивания IP в счётчиках частоты запросов |
| `VERST_TP_TOKEN` / `VERST_TP_MARKER` / `VERST_TP_TRS` | пусто | Аккаунт Travelpayouts. Пока пусто, «Забронировать» открывает обычный поиск без комиссии (`docs/partners/hotel-affiliate.md`) |

Полный список переменных: `infra/api/.env.example`.

### Что умеет API

| Запрос | Что делает |
| --- | --- |
| `POST /v1/devices` | Регистрирует устройство и выдаёт ему токен (аккаунтов нет; в базе хранится только хеш токена) |
| `DELETE /v1/devices/me` | «Отвязать от сервера»: удаляет устройство, его поездки и отзывы |
| `POST /v1/trips/plan` | Строит план поездки и присылает его частями, по мере готовности |
| `POST /v1/route` | Маршрут прогулки или дня |
| `GET /v1/ready-routes` | Готовые маршруты |
| `POST /v1/trips`, `DELETE /v1/trips/{id}` | Сохранённые поездки (не больше 50 на устройство) |
| `GET /v1/shared/{slug}`, `/s/{slug}` | Поделиться поездкой |
| `POST /v1/feedback` | Отзыв о месте |
| `GET /v1/links/hotel` | Ссылка на поиск отелей (партнёрская, если задан аккаунт) |
| `/healthz`, `/privacy` | Проверка работы, политика конфиденциальности |

## 2. База данных

| Что | Значение |
| --- | --- |
| СУБД | PostgreSQL 16.14, контейнер `verst-postgres-1`, данные в томе `verst_pgdata` |
| База / пользователь | `verst` / `verst_api` |
| Пароль | `POSTGRES_PASSWORD` в `.env` |
| Схема | `api`, миграция `0001_api_beta` (`backend/api/migrations/`) |
| Порт | 5432, только внутри Docker |

### Таблицы

| Таблица | Что хранит |
| --- | --- |
| `api.device` | Случайный id, sha256 токена, версия приложения, язык, дата создания и последнего визита (обновляется не чаще раза в час) |
| `api.trip` | Сохранённая поездка: название, город старта, км, дни, версия движка, короткая ссылка `share_slug`, сама поездка в `jsonb` без точных координат, текст для «поделиться» |
| `api.feedback` | Отзыв о месте: тип (`closed`, `wrong_tag`, `price`, `other`), текст (контакты маскируются, текст стирается через 180 дней), к какой поездке и месту относится |
| `api.rate_counter` | Счётчики ограничения частоты запросов; удаляются через 2 дня |

Чего в базе нет: IP-адресов, точных координат, введённых адресов, имён и телефонов (R-07).

### Резервные копии

- Контейнер `verst-backup-1` делает копию каждый день в 03:00 по Москве в `/srv/verst/backups`.
- Хранятся: ежедневные — 14 дней, недельные — 4 недели, месячные — 3 месяца.
- Проверку восстановления (команда ниже) стоит запускать раз в месяц.

## 3. Команды

Каждую строку выполняйте отдельно. Все команды, кроме SSH, запускаются из папки сервера.

Войти на сервер:
```
ssh root@212.108.82.26
```
Перейти в папку сервера:
```
cd /srv/verst/src/infra/api
```
Задать сокращение (после каждого нового входа):
```
C="docker compose -f docker-compose.yml -f docker-compose.host-nginx.yml"
```

### Состояние

Список контейнеров:
```
$C ps
```
Память и CPU контейнеров:
```
docker stats --no-stream
```
Сервер отвечает (ответ `{"status":"ok"}`):
```
curl -s https://212-108-82-26.sslip.io/healthz; echo
```
Прокладка маршрутов отвечает (ответ `OK`):
```
$C exec api python -c "import urllib.request;print(urllib.request.urlopen('http://graphhopper:8989/health').read().decode())"
```
Последние строки журнала сервера:
```
$C logs --tail 50 api
```

### База

Консоль базы:
```
$C exec postgres psql -U verst_api -d verst
```
Сколько записей:
```
$C exec postgres psql -U verst_api -d verst -c "select (select count(*) from api.device) devices, (select count(*) from api.trip) trips, (select count(*) from api.feedback) feedback;"
```
Пароль базы:
```
grep POSTGRES_PASSWORD .env
```
Проверка восстановления из копии (поднимает временную базу, считает записи, удаляет её):
```
VERST_BACKUP_DIR=/srv/verst/backups ./restore-drill.sh
```

### Подключение из программы с окном (DBeaver, DataGrip)

1. SSH-туннель: хост `212.108.82.26`, пользователь `root`.
2. База: `verst`, пользователь `verst_api`, пароль из `.env`, порт `5432`.
3. Хост базы: внутренний адрес контейнера. Его можно получить командой ниже; после перезапуска он может смениться:
```
docker inspect -f '{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}' verst-postgres-1
```

### Обновить сервер после изменений в коде

```
cd /srv/verst/src
```
```
git pull -q
```
```
cd infra/api
```
```
C="docker compose -f docker-compose.yml -f docker-compose.host-nginx.yml"
```
```
$C build api
```
```
$C up -d api
```
```
curl -s https://212-108-82-26.sslip.io/healthz; echo
```

После правки `.env` пересоздайте контейнер, иначе новые значения не подхватятся:
```
$C up -d --force-recreate api
```

### Обновить граф дорог

Когда в CI собран новый граф (релиз `routing-graph-latest`):
```
bash /srv/verst/src/infra/routing/fetch_graph.sh
```
```
$C --profile routing up -d --force-recreate graphhopper
```

## 5. Как Claude сам выполняет команды на сервере (D-IR-29)

Облачная сессия Claude не может зайти на сервер напрямую: ей открыт только HTTPS через прокси. Поэтому команды
выполняет GitHub Actions (сценарий `test-server.yml`) с отдельным ключом. Этот ключ умеет запускать только скрипт
`infra/api/server-ops.sh` и только четыре действия:

| Действие | Что делает |
| --- | --- |
| `status` | ветка и коммит на сервере, состояние контейнеров, ответ `/healthz` |
| `update` | `git pull`, пересборка и перезапуск API, ожидание `/healthz` |
| `recreate` | перезапуск API с текущим `.env` (после того как вы его поправили) |
| `errors` | строки WARNING / ERROR из журнала API за 2 часа |

Всё остальное (правка `.env`, база, граф дорог, nginx) по-прежнему делаете вы.

### Разовая настройка (на сервере, после обновления кода до `main`)

1. Создать отдельный ключ без пароля (только для GitHub Actions):
```
ssh-keygen -t ed25519 -N "" -C verst-github-actions -f /root/.ssh/verst_github_actions
```
2. Разрешить этому ключу только скрипт:
```
echo "restrict,command=\"/srv/verst/src/infra/api/server-ops.sh\" $(cat /root/.ssh/verst_github_actions.pub)" >> /root/.ssh/authorized_keys
```
3. Показать закрытый ключ, чтобы скопировать его в GitHub (не присылайте его в чат):
```
cat /root/.ssh/verst_github_actions
```
   Скопируйте весь текст, включая строки `-----BEGIN…` и `-----END…`, в GitHub → репозиторий Verst → Settings →
   Secrets and variables → Actions → New repository secret, имя `VERST_TEST_SERVER_SSH_KEY`.
4. Показать «отпечаток» сервера, чтобы GitHub знал, что заходит именно на него:
```
echo "212.108.82.26 $(cut -d' ' -f1,2 /etc/ssh/ssh_host_ed25519_key.pub)"
```
   Строку целиком — во второй секрет `VERST_TEST_SERVER_KNOWN_HOSTS`.
5. Удалить закрытый ключ с сервера (он теперь только в GitHub):
```
rm /root/.ssh/verst_github_actions
```

### Как отключить

Удалить строку `verst-github-actions` из `/root/.ssh/authorized_keys`:
```
sed -i '/verst-github-actions/d' /root/.ssh/authorized_keys
```

## 4. Где подробнее

- Сервер и безопасность: `infra/api/README.md`, ADR-0020.
- Прокладка маршрутов: `infra/routing/README.md`, ADR-0017, D-IR-21.
- Состояние проекта целиком: `docs/PROJECT-STATE.md`.
