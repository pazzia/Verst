# Каталог мест Версты — открытые данные / Verst place catalogue — open data

[Русский](#русский) · [English](#english)

## Русский

### Что это

Каталог мест, который приложение «Верста» везёт с собой (города, достопримечательности, бары, кафе и рестораны, парковки), — это пять файлов сжатого JSON:

| Файл | Что внутри |
| --- | --- |
| [`catalogue_meta.json.gz`](../../backend/planner/verst_planner/resources/catalogue_meta.json.gz) | версия сборки, **уведомление о лицензии (`licence`)**, регионы, авторы и лицензии фото (`credits`), связи с демо-миром, платные парковки (`parking`) |
| [`catalogue_towns.json.gz`](../../backend/planner/verst_planner/resources/catalogue_towns.json.gz) | города |
| [`catalogue_pois.json.gz`](../../backend/planner/verst_planner/resources/catalogue_pois.json.gz) | места: достопримечательности Wikidata (id `Q…`) и места OpenStreetMap (id `osm_…`) |
| [`catalogue_bars.json.gz`](../../backend/planner/verst_planner/resources/catalogue_bars.json.gz) | бары, пабы, пивоварни, рюмочные (OpenStreetMap) |
| [`catalogue_food.json.gz`](../../backend/planner/verst_planner/resources/catalogue_food.json.gz) | рестораны, кафе, фастфуд, фуд-корты (OpenStreetMap): название, вид, координаты, город, часы работы, кухня; цен в OpenStreetMap нет. В сборке `wd-20261025-r7.6` таблица пустая — её заполняет `data-osm.yml` |

Файлы лежат в `backend/planner/verst_planner/resources/`. Это ровно те файлы, что входят в APK. Версия, размеры и sha256 — в [`backend/planner/tools/data/catalogue.lock`](../../backend/planner/tools/data/catalogue.lock). Копия для конкретной сборки приложения — по ссылке на коммит в описании релиза (папка `data/catalogue` этого коммита).

Формат: в каждом файле один объект JSON; таблицы хранятся по столбцам (`{"v": 1, "n": …, "cols": {"id": […], "name": […], …}}`), координаты — целые числа, градусы × 10⁵. Описание формата — ADR-0012 §3 ([`docs/adr/0012-open-data-catalogue-and-images.md`](../../docs/adr/0012-open-data-catalogue-and-images.md)) и `verst_planner/catalogue/__init__.py`.

```python
import gzip, json
meta = json.load(gzip.open("backend/planner/verst_planner/resources/catalogue_meta.json.gz"))
print(meta["version"], meta["licence"]["database"]["licence"])  # wd-…  ODbL-1.0
```

### Лицензия

**Каталог — производная база данных OpenStreetMap. Он распространяется по лицензии [Open Database License (ODbL) 1.0](https://opendatacommons.org/licenses/odbl/1-0/) как база данных целиком**, вместе с частями из Wikidata. Полный текст — [`LICENSE-ODbL.txt`](LICENSE-ODbL.txt). Права на отдельное содержимое — по лицензиям источников:

| Источник | Что дал каталогу | Лицензия содержимого |
| --- | --- | --- |
| OpenStreetMap — © участники OpenStreetMap ([авторские права](https://www.openstreetmap.org/copyright)) | бары; рестораны и кафе; места `osm_…` (в том числе детские площадки); платные парковки и тарифы; часы работы, плата за вход, сайты и часть описаний мест Wikidata; часть имён файлов фото | ODbL 1.0 |
| Wikidata | города; места `Q…`; краткие описания; регионы | [CC0 1.0](https://creativecommons.org/publicdomain/zero/1.0/) |
| Википедия, Викигид (ru) | описания мест (`extract`, `extractSrc` = `wikipedia` / `wikivoyage`): первая фраза статьи или листинга, **тексты сокращены** | [CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0/); авторы — в истории правок статьи |
| Wikimedia Commons | только имена файлов, авторы и лицензии (`credits`); самих фото в каталоге нет | у каждого файла своя; файлы только под GFDL не используются |

Если вы используете каталог, указывайте: «© участники OpenStreetMap, данные доступны по лицензии ODbL 1.0» со ссылками на https://www.openstreetmap.org/copyright и https://opendatacommons.org/licenses/odbl/1-0/, а производную базу распространяйте тоже по ODbL 1.0. Это же уведомление записано в самом каталоге: `catalogue_meta` → `licence`.

Сырые ответы источников, из которых собран каталог (ветки `bot/raw-*`, `bot/extras-*`, `bot/photos-*` этого репозитория), содержат выгрузки OpenStreetMap и тоже доступны по ODbL 1.0.

### Как собирается

Сборка повторяема. Все скрипты — в [`backend/planner/tools/data/`](../../backend/planner/tools/data/), запускает их GitHub Actions:

1. `.github/workflows/data.yml`: `fetch_wikidata.py` (классы, города, места) → `inflect.py` (падежи названий городов) → `bars_from_extract.py` и `food_from_extract.py` (бары, рестораны и кафе из выгрузки Geofabrik `russia-latest.osm.pbf`, запасной путь для баров — `fetch_overpass.py`) → `fetch_commons_meta.py` и `fetch_photo_meta.py` (авторы, лицензии, размеры фото) → `build_catalogue.py` → `write_lock.py`.
2. `.github/workflows/data-osm.yml`: только часть OpenStreetMap — бары и рестораны/кафе из свежей выгрузки Geofabrik поверх опубликованных сырых данных (`bot/raw-7`, `bot/extras-1`, `bot/photos-1`), затем `build_catalogue.py` и `write_lock.py`. Результат — ветка `bot/data-osm-N` (файлы каталога и `catalogue.lock`) и `bot/raw-osm-N` (`osm-raw.tar.gz`: `bars.json`, `food.json`, `sources.json`).
3. `.github/workflows/data-extras.yml`: `fetch_extras.py` — классы и наследие Wikidata, вступления статей Википедии, листинги Викигида, места и парковки OpenStreetMap, фото поблизости.
4. Ручные таблицы рядом со скриптами: `name_overrides.tsv`, `region_overrides.tsv`, `region_tz.tsv`.

`build_catalogue.py` — чистая функция от сырых файлов: отбор, очистка названий, оценка качества, лимиты на город, фильтр брендов, запись. Он же пишет блок `licence` и отбрасывает фото только под GFDL. Пересобрать текущую версию из опубликованных сырых данных (из корня клона репозитория, нужен только Python 3.12+):

```sh
git clone --depth 1 -b bot/raw-7 https://github.com/pazzia/Verst raw7
git clone --depth 1 -b bot/extras-1 https://github.com/pazzia/Verst extras1
git clone --depth 1 -b bot/photos-1 https://github.com/pazzia/Verst photos1
mkdir raw && tar -xzf raw7/data-raw.tar.gz -C raw && tar -xzf extras1/data-extra/extras.tar.gz -C raw
gunzip -c photos1/out/photo_meta.json.gz > raw/photo_meta.json
# raw/sources.json — заметка о происхождении; берём её из каталога (meta.sources), чтобы сборка совпала байт в байт
python3 -c 'import gzip,json; json.dump(json.load(gzip.open("backend/planner/verst_planner/resources/catalogue_meta.json.gz"))["sources"], open("raw/sources.json","w"), ensure_ascii=False)'
cd backend/planner && python3 tools/data/build_catalogue.py ../../raw --out ../../rebuilt \
  --version wd-20261025-r7.6 --built-at 2026-10-28
for f in ../../rebuilt/*.gz; do cmp "$f" "verst_planner/resources/$(basename "$f")" && echo "same: $f"; done
```

Результат совпадает с файлами в репозитории байт в байт (проверено 25.10.2026 для `wd-20261025-r7.4` и `wd-20261025-r7.5`, 28.10.2026 для `wd-20261025-r7.6`, 29.10.2026 для `wd-20261029-osm2` — с ветками `bot/raw-7`, `bot/extras-1`, `bot/photos-1`, `bot/raw-osm-2`, после того как скрипты получили ключ `--country`). Сборку, сделанную `data-osm.yml`, пересобирают так же, но бары и еду берут из её ветки: `git clone --depth 1 -b bot/raw-osm-N …` и `tar -xzf rawosmN/osm-raw.tar.gz -C raw` после распаковки трёх веток выше; версия и дата — из `catalogue.lock`.

### Парки и каталоги поездок за рубеж (CEO 29.10)

- `catalogue_parks.json.gz` — именованные парки и сады OpenStreetMap (`leisure=park|garden`, площадь от 3 000 м²) для прогулки «парки»: отдельный файл рядом с остальными, его строки ссылаются на города той сборки, чья контрольная сумма `catalogue_towns` записана в файле (`townsSha256`). Собирают `parks_from_extract.py` и `build_parks.py`; лок — `backend/planner/tools/data/catalogue_parks.lock`.
- Каталоги стран первой волны поездок за рубеж (Беларусь, Казахстан, Грузия, Абхазия, Армения, Азербайджан, Узбекистан, Киргизия, Турция) лежат в `backend/planner/abroad/<код>/catalogue_*.json.gz` (лок — `backend/planner/abroad/abroad.lock`). В APK их нет: поездки за рубеж строит только сервер. Формат тот же, лицензия та же (ODbL 1.0 для базы целиком, части Wikidata — CC0, выдержки Википедии и Викигида — CC BY-SA 4.0); собирает `.github/workflows/data-abroad.yml` теми же скриптами с ключом `--country`. Подробности — `docs/plan/abroad-wave1-data.md`.

## English

### What it is

The place catalogue the Verst app ships (towns, sights, bars, restaurants and cafés, parking) is five gzipped JSON files in `backend/planner/verst_planner/resources/`: [`catalogue_meta.json.gz`](../../backend/planner/verst_planner/resources/catalogue_meta.json.gz) (build version, **the licence notice `licence`**, regions, photo authors and licences `credits`, links to the demo world, paid parking), [`catalogue_towns.json.gz`](../../backend/planner/verst_planner/resources/catalogue_towns.json.gz), [`catalogue_pois.json.gz`](../../backend/planner/verst_planner/resources/catalogue_pois.json.gz) (Wikidata sights `Q…` and OpenStreetMap places `osm_…`), [`catalogue_bars.json.gz`](../../backend/planner/verst_planner/resources/catalogue_bars.json.gz) and [`catalogue_food.json.gz`](../../backend/planner/verst_planner/resources/catalogue_food.json.gz) (OpenStreetMap restaurants, cafés, fast food, food courts: name, kind, position, town, opening hours, cuisine; OSM has no prices; empty in `wd-20261025-r7.6` until `data-osm.yml` runs). They are exactly the files inside the APK. Version, sizes and sha256 are in [`catalogue.lock`](../../backend/planner/tools/data/catalogue.lock). The copy for a given app build is at the commit linked from its release notes. The format (columnar tables, coordinates as integers in degrees × 10⁵) is described in ADR-0012 §3 and `verst_planner/catalogue/__init__.py`.

### Licence

**This catalogue is a Derivative Database of OpenStreetMap and is licensed under the [Open Database License (ODbL) 1.0](https://opendatacommons.org/licenses/odbl/1-0/) as a database as a whole**, Wikidata parts included. Full text: [`LICENSE-ODbL.txt`](LICENSE-ODbL.txt) (Open Data Commons' plain-text version). Rights in individual contents follow the sources:

- **OpenStreetMap** — © OpenStreetMap contributors, ODbL 1.0 ([copyright](https://www.openstreetmap.org/copyright)): bars, restaurants and cafés, `osm_…` places (playgrounds included), paid parking and tariffs, opening hours, entry fees, websites and some descriptions of Wikidata places, some photo file names.
- **Wikidata** — [CC0 1.0](https://creativecommons.org/publicdomain/zero/1.0/): towns, `Q…` places, short descriptions, regions.
- **Wikipedia, Wikivoyage (ru)** — [CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0/): place descriptions (`extractSrc` = `wikipedia` / `wikivoyage`), the first sentence of the article or listing, **abridged**; the authors are in the article's history.
- **Wikimedia Commons** — per file: file names, authors and licences only (`credits`), no images. GFDL-only files are not used.

When you reuse the catalogue, credit «© OpenStreetMap contributors, available under the ODbL 1.0» with links to https://www.openstreetmap.org/copyright and https://opendatacommons.org/licenses/odbl/1-0/, and license derived databases under ODbL 1.0 too. The same notice is stored in the catalogue: `catalogue_meta` → `licence`. The raw source responses on the `bot/raw-*`, `bot/extras-*` and `bot/photos-*` branches hold OpenStreetMap extracts and are available under ODbL 1.0 as well.

### How it is built

The build is reproducible. The scripts are in [`backend/planner/tools/data/`](../../backend/planner/tools/data/) and run in GitHub Actions (`data.yml`: Wikidata, name forms, OpenStreetMap bars and food places from the Geofabrik extract, Commons credits and photo metadata, build, lock; `data-osm.yml`: only the OpenStreetMap bars and food places from a fresh extract on top of the published raw branches, build, lock; `data-extras.yml`: Wikidata classes and heritage, Wikipedia intros, Wikivoyage listings, OpenStreetMap places and parking, nearby photos), plus the hand-kept tables `name_overrides.tsv`, `region_overrides.tsv` and `region_tz.tsv`. `build_catalogue.py` is a pure function of the raw files; it also writes the `licence` block and drops GFDL-only photos. The commands in the Russian section above (run from the repository root, Python 3.12+ only) rebuild the current version from the published raw branches byte for byte. The parks of the walk «парки» are a separate file, `catalogue_parks.json.gz` (named OSM parks and gardens with their area, tied to the towns file of the same build by `townsSha256`). The server-only catalogues of the wave-1 countries abroad are in `backend/planner/abroad/<cc>/` (not in the APK), in the same format and under the same licences, built by `data-abroad.yml`.
