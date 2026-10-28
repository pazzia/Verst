"""`GET /s/{slug}`: the public page of a shared trip (R-07: the start is a town, never a point or an address).
It renders only the stored, privacy-reduced share text; no map, no coordinates, no third-party resources, and
it asks search engines not to index it."""

from __future__ import annotations

from html import escape

from verst_api.store import SavedTrip

HEADERS = {
    "Content-Language": "ru",
    "X-Robots-Tag": "noindex, nofollow",
    "Content-Security-Policy": (
        "default-src 'none'; style-src 'unsafe-inline'; base-uri 'none'; form-action 'none'"
    ),
    "Referrer-Policy": "no-referrer",
    "Cache-Control": "public, max-age=300",
}

_STYLE = """
:root{--bg:#f6f3ec;--fg:#1d1b16;--muted:#6b665b;--card:#fffdf8;--line:#e3ddd0}
@media (prefers-color-scheme:dark){
:root{--bg:#16150f;--fg:#f1ece0;--muted:#a59f90;--card:#211f18;--line:#36322a}}
body{margin:0;background:var(--bg);color:var(--fg);
font:16px/1.5 system-ui,-apple-system,"Segoe UI",Roboto,sans-serif}
main{max-width:640px;margin:0 auto;padding:24px 16px 48px}
h1{font-size:1.5rem;line-height:1.25;margin:0 0 4px}
.meta{color:var(--muted);margin:0 0 20px}
.card{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:16px;
white-space:pre-wrap;overflow-wrap:anywhere}
.note{color:var(--muted);font-size:.875rem;margin-top:16px}
"""


def days_word(n: int) -> str:
    if n % 10 == 1 and n % 100 != 11:
        return "день"
    if 2 <= n % 10 <= 4 and not 12 <= n % 100 <= 14:
        return "дня"
    return "дней"


def render(trip: SavedTrip) -> str:
    approx = '<p class="note">Расстояния приблизительные.</p>' if trip.synthetic else ""
    return (
        "<!doctype html>\n"
        '<html lang="ru"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width, initial-scale=1">'
        '<meta name="robots" content="noindex, nofollow">'
        f"<title>{escape(trip.title)} — Верста</title><style>{_STYLE}</style></head>"
        "<body><main>"
        f"<h1>{escape(trip.title)}</h1>"
        f'<p class="meta">Старт: {escape(trip.start_town)} · {trip.km} км · '
        f"{trip.days} {days_word(trip.days)}</p>"
        f'<div class="card">{escape(trip.share_text)}</div>{approx}'
        '<p class="note">Поездка спланирована в приложении «Верста».</p>'
        "</main></body></html>\n"
    )


def not_found() -> str:
    return (
        '<!doctype html>\n<html lang="ru"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width, initial-scale=1">'
        f"<title>Поездка не найдена — Верста</title><style>{_STYLE}</style></head>"
        "<body><main><h1>Поездка не найдена</h1>"
        '<p class="meta">Ссылка устарела или поездку удалили.</p></main></body></html>\n'
    )


_PRIVACY = (
    (
        "Что это",
        "Тестовый сервер приложения «Верста». Он строит маршрут, когда в настройках выбрано «Где "
        "строить маршрут: на сервере». По умолчанию маршрут строится на телефоне, и на сервер ничего "
        "не уходит.",
    ),
    (
        "Что уходит на сервер",
        "Точки маршрута (откуда, куда, через что — координаты и название, которое вы ввели), состав "
        "экипажа (взрослые, дети и их возраст, собака), дневной пробег, бюджет, дата и время выезда, "
        "настройки машины. Ещё — случайный номер устройства, который сервер выдаёт при первом "
        "обращении; имени, телефона, почты и рекламных идентификаторов мы не получаем.",
    ),
    (
        "Что сервер хранит",
        "Сам маршрут при построении не сохраняется. В журналах — только время и тип запроса и "
        "координаты, округлённые до ~1 км. Адрес подключения не хранится: для защиты от перегрузки "
        "используется его хеш, он удаляется через двое суток. Если вы поделились поездкой, "
        "сохраняется её копия, где точки заменены названиями городов, — до тех пор, пока вы её не "
        "удалите.",
    ),
    (
        "Где сервер",
        "Это тестовый сервер в Нидерландах. Он нужен, пока приложение проверяют друзья и знакомые "
        "команды. Перед открытым тестированием сервер переедет в Россию, а этот будет выключен вместе"
        " с данными.",
    ),
    (
        "Как отказаться",
        "В настройках выберите «Где строить маршрут: на телефоне» — запросы прекратятся. Кнопка "
        "«Отвязать от сервера» там же удаляет номер устройства, сохранённые на сервере поездки и "
        "отзывы.",
    ),
    (
        "Кто отвечает",
        "Владелец проекта «Верста». Вопросы — через «Сообщить об ошибке» в приложении.",
    ),
)


def privacy() -> str:
    body = "".join(f"<h2>{escape(h)}</h2><p>{escape(t)}</p>" for h, t in _PRIVACY)
    return (
        "<!doctype html>\n"
        '<html lang="ru"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width, initial-scale=1">'
        '<meta name="robots" content="noindex, nofollow">'
        "<title>Данные и тестовый сервер — Верста</title>"
        f"<style>{_STYLE}h2{{font-size:1.1rem;margin:20px 0 4px}}</style></head>"
        "<body><main><h1>Данные и тестовый сервер</h1>"
        '<p class="meta">Редакция от 28.10.2026</p>'
        f"{body}</main></body></html>\n"
    )
