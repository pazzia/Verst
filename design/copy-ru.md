# Verst — Russian copy deck (DES-004)

Version 1.0.0 · 2026-10-23 · Owner: Designer · Reviewed sources: SPEC §5, §12, §13; `docs/architecture.md` §8; `backend/planner/verst_planner/resources/reasons.ru.json` and `strings.ru.json` (DEV-005 draft); `design/screens/*.md`; `design/open-issues.md` D-1…D-12; `design/decisions.md`.

## 0. Rules

| Rule | Detail |
| --- | --- |
| Keys | Android string resource names, `snake_case`, prefixed by screen: `common_`, `windshield_`, `navigator_`, `picker_`, `instruments_`, `settings_`, `drive_`, `road_`, `stopmenu_`, `replace_`, `report_`, `waybill_`, `pro_`, `exit_`, `trips_`, `error_`. TalkBack-only strings start with `cd_`. Engine strings keep their JSON keys (§10, §11) |
| Placeholders | Written here as `{name}`; `design/tools/gen_strings.py` numbers them by first appearance (`%1$s`, `%2$d`…; a repeated name reuses its number). Integer counts `{n}` `{k}` `{d}` `{a}` `{c}` `{h}` `{m}` `{min}` `{nights}` `{adults}` `{children}` become `%n$d`; everything else `%n$s` (amounts, km and times arrive pre-formatted with U+202F) |
| Generator typography | The generator also inserts U+00A0 between a number or placeholder and a unit (км, м, мин, ч, л, ₽), after «≈» and «№», and U+202F inside digit groups («30 500»), so the deck can be typed with plain spaces. Literal spaces at the ends of a text are kept only when the cell is wrapped in straight double quotes |
| Plurals | ICU via `<plurals>` with `one` / `few` / `many` / `other` (SPEC 16). Listed in §9; a string that needs one names it as `[plural: key]` |
| Typography | «ёлочки» quotes; «ё» always; «—» (em dash) with spaces; «→» between towns; «·» (middle dot) as a separator; «≈» + U+00A0 before estimates; U+202F thousands separator («30 500»); U+00A0 between number and unit («745 км», «6 000 ₽»); 24-hour time |
| Uppercase | Uppercase labels are stored in uppercase (not transformed in code) |
| Tone | Spoken, calm, second person plural «вы»; no exclamation marks; no jargon («ночёвка», not «отель-стоп»); short: labels ≤ 30 characters, plates ≤ 80, rendered reasons ≤ 140 |
| D-16 | The Waybill food example is «3 чел. × 5 приёмов × 600» = 9 000; the reference total is «≈ 30 500 ₽» (screens 5.5, 5.6) |

## 1. Common

| Key | Text | Notes |
| --- | --- | --- |
| `app_name` | Верста | launcher label (DES-103); the same in the demo build — the build line carries «демо» |
| `common_go` | ПОЕХАЛИ | start button label |
| `common_go_wait` | ЖДЁМ | start button while validating |
| `common_back_to_windshield` | К лобовому | back link |
| `common_back_instruments` | Приборы | back link |
| `common_back_road` | Дорога впереди | back link |
| `common_cancel` | Отменить | back link on Drive |
| `common_close` | Закрыть | sheet close button (TalkBack + keyboard) |
| `common_retry` | Повторить | inline retry |
| `common_try_again` | Попробовать ещё раз | CTA |
| `common_offline` | НЕТ СЕТИ | `OfflinePlate` |
| `common_need_internet` | Нужен интернет | disabled actions |
| `common_need_internet_navigator` | Нужен интернет, чтобы открыть навигатор | toast |
| `common_estimate_rub` | ≈ {amount} ₽ | amount pre-formatted with U+202F |
| `common_rub` | {amount} ₽ | |
| `common_km` | {km} км | |
| `common_km_approx` | ≈ {km} км | straight-line distances (OI-23) |
| `common_unverified` | не проверено | = engine `note.unverified` |
| `common_saved_toast` | Сохранено. Поездка откроется без сети | |
| `common_saved_near_limit` | Сохранено {n} из 50 — старые поездки можно удалить в «Мои поездки» | n ≥ 45 |
| `common_storage_full_title` | Место для поездок закончилось | dialog |
| `common_storage_full_body` | Удалите старую поездку, чтобы сохранить эту | |
| `common_storage_full_open` | Мои поездки | |
| `common_undo` | Вернуть | toast action |
| `common_month_gen_01` | января | genitive month for dates («31 октября»); index = month 1–12 |
| `common_month_gen_02` | февраля | |
| `common_month_gen_03` | марта | |
| `common_month_gen_04` | апреля | |
| `common_month_gen_05` | мая | |
| `common_month_gen_06` | июня | |
| `common_month_gen_07` | июля | |
| `common_month_gen_08` | августа | |
| `common_month_gen_09` | сентября | |
| `common_month_gen_10` | октября | |
| `common_month_gen_11` | ноября | |
| `common_month_gen_12` | декабря | |
| `common_month_short_01` | янв. | short genitive (Russian abbreviation norm: «марта», «мая», «июня», «июля» are not abbreviated); `mock_partner_dates` «7 нояб.» |
| `common_month_short_02` | февр. | |
| `common_month_short_03` | марта | |
| `common_month_short_04` | апр. | |
| `common_month_short_05` | мая | |
| `common_month_short_06` | июня | |
| `common_month_short_07` | июля | |
| `common_month_short_08` | авг. | |
| `common_month_short_09` | сент. | |
| `common_month_short_10` | окт. | |
| `common_month_short_11` | нояб. | |
| `common_month_short_12` | дек. | |
| `common_date_day` | {day} {month} | «31 октября»; day without a leading zero; `{month}` = `common_month_gen_*` |
| `common_date_range_month` | {day}–{day_to} {month} | same month: «7–9 ноября» (U+2013, no spaces) |
| `common_date_range` | {day} {month} – {day_to} {month_to} | across months: «30 октября – 2 ноября» (U+2013 with spaces) |
| `common_date_with_year` | {date} {year} | appended only when the year is not the current year: «7–9 ноября 2027» |
| `common_dialog_cancel` | Отмена | secondary button of `NaviDialog` (50-trip limit) |
| `common_join_dot` | " · " | separator; a text cell in straight double quotes is literal (spaces kept) |
| `common_join_comma` | ", " | separator |
| `cd_back` | Назад: {label} | |
| `cd_start_disabled_destination` | Поехали — сначала выберите, куда | |
| `cd_start_disabled_offline` | Поехали — нужен интернет | |
| `cd_start_route` | Поехали: {route} | |

## 2. 5.1 Windshield

| Key | Text | State / notes |
| --- | --- | --- |
| `windshield_sign_header` | РЯДОМ С ВАМИ · ИЗ {CITY_GEN} | city in the genitive, uppercase («ИЗ МОСКВЫ») |
| `windshield_sign_km` | КМ | header right |
| `windshield_sign_more` | ещё {n} {routes} в радиусе 300 км ↓ | [plural: `plural_route`] |
| `windshield_selected_label` | ВЫБРАН МАРШРУТ | caption |
| `windshield_navi_label` | НАВИГАТОР | |
| `windshield_you_are` | ВЫ: {CITY} | uppercase nominative |
| `windshield_field_title` | Куда угодно | |
| `windshield_field_sub` | город, адрес или точка на карте — по всей России | |
| `windshield_hint` | или выберите готовый маршрут на указателе ↑ | |
| `windshield_my_trips` | Мои поездки · {n} | plate |
| `windshield_loading_cd` | Загружаем маршруты рядом | `cd_` semantics of the loading sign |
| `windshield_offline_field_sub` | без сети открываются только сохранённые поездки | offline |
| `windshield_offline_empty_sign` | Нет сети — готовые маршруты появятся, когда будет интернет | offline, no cache |
| `windshield_offline_title` | Мои поездки работают | caption title, offline, saved trips exist |
| `windshield_offline_title_none` | Подключитесь к интернету | caption title, offline, no saved trips |
| `windshield_offline_meta` | маршрут построим, когда появится сеть | caption meta |
| `windshield_no_routes_sign` | Рядом пока нет готовых маршрутов | empty |
| `windshield_no_routes_footer` | Наберите любой город в навигаторе ↓ | empty |
| `windshield_no_routes_hint` | маршрут построим из любой точки России | empty, navi hint line |
| `windshield_no_routes_label` | КУДА ЕДЕМ? | caption label |
| `windshield_no_routes_title` | Выберите в навигаторе | |
| `windshield_no_routes_meta` | город, адрес или точка на карте | |
| `windshield_error_sign` | Не получилось загрузить маршруты | error |
| `windshield_location_rationale` | Определим город старта, чтобы показать маршруты рядом | first launch toast |
| `windshield_location_allow` | Разрешить | toast action |
| `windshield_location_denied` | Хорошо, старт — Москва. Изменить можно в навигаторе | toast |
| `windshield_location_blocked` | Доступ к геопозиции выключен в настройках | toast |
| `windshield_location_settings` | Настройки | toast action |
| `windshield_all_routes_title` | Готовые маршруты из {city_gen} | sheet title («из Москвы») |
| `windshield_ring_weekend` | НА ВЫХОДНЫЕ · ДО 300 КМ | sheet section |
| `windshield_ring_long` | НА 3–4 ДНЯ · ДО 700 КМ | sheet section |
| `cd_windshield_mirror` | Экипаж в зеркале: {crew_spoken}. Изменить | «2 взрослых, 1 ребёнок, собака» |
| `cd_windshield_row` | {name}, {km} километров, {direction}. {meta} | |
| `cd_windshield_more` | Ещё {n} {routes} в радиусе 300 километров. Открыть список | [plural: `plural_route`] |
| `cd_windshield_navi` | Навигатор. Куда угодно: город, адрес или точка на карте, по всей России | |
| `cd_windshield_you_are` | Старт: {city}. Определить по геопозиции | |
| `cd_windshield_caption` | Выбран маршрут: {name}. {meta} | live region |
| `cd_windshield_my_trips` | Мои поездки, {n} {saved}. Открыть список | [plural: `plural_saved`] |
| `cd_direction_n` | на север |  |
| `cd_direction_ne` | на северо-восток |  |
| `cd_direction_e` | на восток |  |
| `cd_direction_se` | на юго-восток |  |
| `cd_direction_s` | на юг |  |
| `cd_direction_sw` | на юго-запад |  |
| `cd_direction_w` | на запад |  |
| `cd_direction_nw` | на северо-запад |  |
| `crew_adults_short` | {a} взр | joined with `common_join_dot` |
| `crew_children_short` | {c} реб | omitted when 0 |
| `crew_dog_short` | пёс | only with the dog |

## 3. 5.2 Navigator and map picker

| Key | Text | State / notes |
| --- | --- | --- |
| `navigator_header` | НАВИГАТОР · ВСЯ РОССИЯ | |
| `navigator_gps_on` | GPS ● | fix |
| `navigator_gps_wait` | GPS ○ | no fix |
| `navigator_from` | ОТКУДА | |
| `navigator_from_here` | {city} · вы здесь | |
| `navigator_change` | изменить | |
| `navigator_to_label` | КУДА — город, адрес, место | |
| `navigator_to_hint` | Начните вводить | placeholder |
| `navigator_via_label` | ЗАЕЗД {n} | |
| `navigator_add_via` | + заехать по пути | |
| `navigator_add_via_max` | максимум 3 заезда | disabled |
| `navigator_map_point` | точка на карте | |
| `navigator_my_location` | Моё местоположение | first row when editing ОТКУДА |
| `navigator_recent` | НЕДАВНО ИСКАЛИ | OI-04 |
| `navigator_popular` | ЧАСТО ИЩУТ | OI-04, chips from config |
| `navigator_type_city` | Г | badge |
| `navigator_type_street` | У | badge |
| `navigator_type_place` | М | badge |
| `navigator_route_label` | МАРШРУТ | caption |
| `navigator_route_title` | {from} → {to} | vias inserted with « → » |
| `navigator_route_no_to` | {from} → ? | |
| `navigator_route_no_to_meta` | выберите, куда ехать | |
| `navigator_no_results_title` | Ничего не нашли по запросу «{q}» | |
| `navigator_no_results_text` | Попробуйте иначе или поставьте точку на карте | |
| `navigator_suggest_error` | Подсказки не загрузились | |
| `navigator_offline_title` | Поиск работает только с интернетом | |
| `navigator_offline_text` | Сохранённые поездки открываются на лобовом — «Мои поездки» | |
| `navigator_outside_title` | Сюда маршрут не строим — только по России | also map picker |
| `navigator_outside_text` | Можно доехать до границы: выберите город в России, например {city} | |
| `navigator_outside_row` | не по России | disabled row label |
| `navigator_outside_meta` | выберите город или место в России | caption meta |
| `navigator_found_cd` | Найдено {n} {variants} | [plural: `plural_variant`], live |
| `cd_navigator_clear` | Очистить | |
| `cd_navigator_via_remove` | Удалить заезд {n} | |
| `cd_navigator_move_up` | Переместить выше | custom action |
| `cd_navigator_move_down` | Переместить ниже | custom action |
| `cd_navigator_map` | Точка на карте, откроется карта | |
| `picker_cancel` | Отмена | back link |
| `picker_label` | ТОЧКА НА КАРТЕ | |
| `picker_loading` | Ищем адрес… | |
| `picker_fallback` | Точка на карте | = engine `label.map_point` |
| `picker_distance` | {region} · ≈ {km} км от вас | |
| `picker_choose` | Выбрать эту точку | CTA |
| `picker_my_place` | моё место | key |
| `picker_offline` | Карта работает только с интернетом | |
| `cd_picker_map` | Карта. Двигайте карту, чтобы поставить точку | |
| `cd_picker_zoom_in` | Приблизить |  |
| `cd_picker_zoom_out` | Отдалить |  |

## 4. 5.3 Instruments and settings

| Key | Text | Notes |
| --- | --- | --- |
| `instruments_hint` | Нажимайте на кресла в зеркале | |
| `instruments_front_adult` | Рядом с вами: взрослый | chip on |
| `instruments_front_none` | Рядом с вами: никого | chip off |
| `instruments_seat_empty` | свободно | |
| `instruments_seat_adult` | взрослый | |
| `instruments_seat_child` | ребёнок | |
| `instruments_seat_full` | нет мест | disabled |
| `instruments_seat_limit` | В машине до 8 человек вместе с вами | toast, decisions.md OI-07 |
| `instruments_third_row` | + третий ряд | |
| `instruments_dog_on` | пёс | |
| `instruments_dog_off` | + пёс | |
| `instruments_summary_adults` | {n} {adults_word} | [plural: `plural_adult`] |
| `instruments_summary_children` | {n} {children_word} | [plural: `plural_child`], omitted when 0 |
| `instruments_summary_dog` | собака | only with the dog; parts joined with `common_join_dot` |
| `instruments_km_label` | ЗА ДЕНЬ, КМ | |
| `instruments_drive_time` | ≈ {h} ч {m} мин за рулём | minutes rounded to 10 |
| `instruments_drive_time_h` | ≈ {h} ч за рулём | when minutes = 0 |
| `instruments_days_ring` | {n} {days} на кольцо | [plural: `plural_day`] |
| `instruments_days_oneway` | {n} {days} в пути | [plural: `plural_day`] |
| `instruments_budget_label` | БЮДЖЕТ | |
| `instruments_budget_value` | до {amount} ₽ | |
| `instruments_budget_any` | не важно | |
| `instruments_gauge_empty` | E | fuel gauge letter at the red end (components §6, Latin as on a real dashboard); `cd` not needed: the gauge node speaks the budget |
| `instruments_gauge_full` | F | fuel gauge letter at the full end |
| `instruments_mood_label` | НАСТРОЕНИЕ | |
| `instruments_mood_calm` | Спокойно, с детьми | |
| `instruments_mood_more` | Побольше остановок | |
| `instruments_mood_drive` | Просто доехать | = engine `hint.just_drive` wording |
| `instruments_settings` | Машина и выезд | plate |
| `instruments_settings_summary` | {fuel} · {consumption} л · {day} {time} | «АИ-95 · 8,0 л · сб 08:00» |
| `instruments_ready_label` | ВСЁ ГОТОВО К ВЫЕЗДУ | |
| `instruments_ready_meta_ring` | из {city_gen} · {km} км по кругу | |
| `instruments_ready_meta_oneway` | ≈ {km} км · {n} {vias} | [plural: `plural_via`], omitted when 0 |
| `cd_instruments_seat` | {position} кресло: {state}. Нажмите, чтобы изменить | position: Левое / Среднее / Правое; third row: «Третий ряд, левое…» |
| `cd_instruments_dog_on` | Собака едет. Нажмите, чтобы убрать | |
| `cd_instruments_dog_off` | Собаки нет. Нажмите, чтобы взять | |
| `cd_instruments_km` | {km} километров в день | |
| `cd_instruments_km_less` | Меньше на 50 км |  |
| `cd_instruments_km_more` | Больше на 50 км |  |
| `cd_instruments_budget_value` | Бюджет до {amount} рублей |  |
| `cd_instruments_budget_any` | Бюджет не важен |  |
| `cd_instruments_budget_less` | Уменьшить бюджет |  |
| `cd_instruments_budget_more` | Увеличить бюджет |  |
| `settings_title` | Машина и выезд | sheet |
| `settings_consumption` | РАСХОД, Л НА 100 КМ | |
| `settings_fuel` | ТОПЛИВО | |
| `settings_fuel_92` | АИ-92 |  |
| `settings_fuel_95` | АИ-95 |  |
| `settings_fuel_dt` | ДТ |  |
| `settings_tank` | БАК, Л | |
| `settings_start` | ВЫЕЗД | |
| `settings_today` | сегодня | day chip |
| `settings_avoid_tolls` | Избегать платных дорог | switch |
| `settings_privacy` | Политика конфиденциальности ↗ | |
| `settings_done` | Готово | |

## 5. 5.4 Drive

| Key | Text | State / notes |
| --- | --- | --- |
| `drive_header` | СТРОИМ ДОРОГУ · {km} КМ | `{km}` with «≈ » when straight-line |
| `drive_header_days` | {n} {DAYS} | uppercase [plural: `plural_day_upper`] |
| `drive_done` | Дорога готова — смотреть знаки | CTA |
| `drive_slow` | Строим дольше обычного… | 20 s |
| `drive_wait` | Подождать | |
| `drive_simplify` | Упростить маршрут | |
| `drive_failed` | НЕ ПОЛУЧИЛОСЬ | header |
| `drive_error_sub` | Параметры поездки сохранены — можно попробовать ещё раз. | |
| `drive_to_instruments` | К приборам | CTA for `INVALID_INPUT` |
| `drive_change_route` | Изменить маршрут | CTA for `UNREACHABLE`, `TOO_SHORT` |
| `drive_retry_in` | Попробовать через {m}:{ss} | `RATE_LIMITED` countdown |
| `drive_offline` | Чтобы построить дорогу, нужен интернет. | |
| `drive_offline_sub` | Сохранённые поездки открываются без сети — на лобовом, в «Мои поездки». | |
| `drive_sign_night` | ночёвка | second line of flying service signs |
| `drive_sign_fuel` | заправка |  |
| `drive_sign_food` | обед |  |
| `drive_sign_rest` | отдых |  |
| `cd_drive_cancel` | Отменить построение | |
| `cd_drive_step_done` | Готово: {text} | live |
| `cd_drive_step_now` | Сейчас: {text} | live |
| `cd_drive_progress` | Готово {n} {stages} из 5 | [plural: `plural_stage`] |
| `cd_drive_ready` | Дорога готова. Смотреть знаки, кнопка | TalkBack, no auto-advance |

## 6. 5.5 Road ahead and its sheets

| Key | Text | State / notes |
| --- | --- | --- |
| `road_title` | Дорога впереди | h1 |
| `road_chip_days` | {d} {days} · {nights} {nights_word} | [plural: `plural_day`, `plural_night`]; args: day count, day word, night count, night word («3 дня · 2 ночи») |
| `road_chip_pace` | до {km} км в день | |
| `road_intro` | Знаки по пути — как увидите их на трассе. Любой можно заменить. | |
| `road_day` | День {n} | |
| `road_day_meta` | {km} км · ≈ {h} ч за рулём |  |
| `road_day_meta_home` | {km} км · домой | last day of a round trip |
| `road_day_navigator` | в навигатор ↗ | |
| `road_day_navigator_off` | в навигатор | offline, disabled |
| `road_start` | старт | |
| `road_ahead_km` | через {km} км | |
| `road_name_lunch` | Обед · {town} | |
| `road_name_night` | Ночёвка · {town} | |
| `road_name_rest` | Место отдыха | |
| `road_free` | вход свободный | = engine `cost.tickets.none` |
| `road_swap` | заменить | |
| `road_pick_hotel` | Выбрать отель → | |
| `road_booked` | Забронировано | the check is **not** a character (Verst Sans Narrow has no U+2713; it fell back to «√»): draw §17.4 `check` 16 × 16, stroke 2, same colour as the text, gap 6, after the text |
| `road_excursion` | Экскурсия от {amount} ₽ ↗ | SPEC §14 |
| `road_waybill_label` | ПУТЕВОЙ ЛИСТ · СКОЛЬКО СТОИТ | |
| `road_waybill_over` | ПУТЕВОЙ ЛИСТ · ПЕРЕРАСХОД {amount} ₽ | over budget |
| `road_waybill_per_person` | ≈ {amount} ₽ на человека | footer, right of the amount (5.5 F3); `perPersonRub` from the engine cost, U+202F thousands; hidden when the crew is 1 person |
| `road_prices_from` | Цены от {date} | prices older than 24 h |
| `road_prices_refresh` | Обновить цены | |
| `road_prices_updated` | Цены обновлены: ≈ {amount} ₽ | toast |
| `road_offline_plate` | Без сети: бронирование и навигатор недоступны | |
| `road_replaced_toast` | Заменили. Путевой лист: ≈ {amount} ₽ | + `common_undo` |
| `road_replace_sync_later` | Замену сохраним на сервере, когда появится сеть | |
| `cd_road_save` | Сохранить офлайн | toolbar |
| `cd_road_saved` | Сохранено офлайн | toolbar, saved |
| `cd_road_share` | Поделиться поездкой | |
| `cd_road_day` | День {n}, {km} километров, примерно {h} {hours} за рулём | [plural: `plural_hour`] |
| `cd_road_day_navigator` | Открыть день {n} в навигаторе | |
| `cd_road_row` | {ahead}, {time}, {name}. {note}. {cost}. | SPEC 16: «Через 70 км, 09:15, Троице-Сергиева лавра» |
| `cd_road_kind_fuel` | Заправка: {text} | row prefix |
| `cd_road_kind_food` | Обед: {text} |  |
| `cd_road_kind_rest` | Отдых: {text} |  |
| `cd_road_kind_night` | Ночёвка: {text} |  |
| `cd_road_warning` | Внимание: {text} | |
| `cd_road_swap` | Заменить: {name} | |
| `cd_road_hotel` | Выбрать отель в {town_prep} | |
| `cd_road_action_navigator` | Открыть в навигаторе отсюда | custom action |
| `cd_road_action_report` | Сообщить об ошибке | custom action |
| `cd_road_waybill` | Путевой лист, сколько стоит: примерно {amount} рублей | |
| `stopmenu_navigator` | ОТКРЫТЬ В НАВИГАТОРЕ ОТСЮДА | D-5 |
| `stopmenu_yandex_navi` | Яндекс Навигатор | app names, no logos |
| `stopmenu_yandex_maps` | Яндекс Карты |  |
| `stopmenu_2gis` | 2ГИС |  |
| `stopmenu_none` | Навигатор не установлен | |
| `stopmenu_install` | Установить Яндекс Навигатор из RuStore | |
| `stopmenu_last` | последний раз | |
| `stopmenu_day_title` | День {n} в навигаторе | |
| `stopmenu_swap` | Заменить | |
| `stopmenu_report` | Сообщить об ошибке | |
| `replace_title` | Заменить: {name} | D-6 |
| `replace_subtitle` | Варианты в то же время, ± 45 минут | |
| `replace_current` | сейчас | |
| `replace_delta` | {min_sign}{min} мин · {rub_sign}{amount} ₽ | independent signs «+» / «−» (U+2212): «+4 мин · −150 ₽»; `{min}` and `{amount}` are absolute values (amount with U+202F) |
| `replace_delta_min` | {min_sign}{min} мин | when the price difference is 0 |
| `replace_delta_rub` | {rub_sign}{amount} ₽ | when the time difference is 0 |
| `replace_delta_none` | то же время и цена | both differences are 0 |
| `replace_confirm` | Заменить | CTA |
| `replace_keep` | Оставить как есть | |
| `report_title` | Что не так с местом? | D-7 |
| `report_closed` | Закрыто или не работает | |
| `report_tags` | Неверно: с собакой, детское меню, парковка | |
| `report_price` | Другая цена | |
| `report_other` | Другое | |
| `report_comment` | Комментарий, если хотите | placeholder |
| `report_send` | Отправить | |
| `report_thanks` | Спасибо, проверим | toast |
| `report_queued` | Отправим, когда появится сеть | toast |

## 7. 5.6 Waybill and Pro

| Key | Text | Notes |
| --- | --- | --- |
| `waybill_form` | ФОРМА ПОЕЗДКИ · ВЕРСТА | |
| `waybill_title` | ПУТЕВОЙ ЛИСТ | |
| `waybill_subtitle` | легкового автомобиля | |
| `waybill_number` | № | handwritten number follows |
| `waybill_route` | Маршрут | |
| `waybill_crew` | Экипаж |  |
| `waybill_crew_adults` | {a} взр. | value parts joined with «, » |
| `waybill_crew_children` | {c} реб. | omitted when 0 |
| `waybill_crew_dog` | собака | only with the dog |
| `waybill_mileage` | Пробег, км |  |
| `waybill_mileage_value` | {km} за {n} {days} | [plural: `plural_day_gen`] |
| `waybill_table_item` | СТАТЬЯ И РАСЧЁТ | |
| `waybill_table_rub` | ₽ | |
| `waybill_line_fuel` | Бензин {fuel_type} | «Бензин АИ-95»; diesel: «Дизель» (engine `cost.title.fuel.dt`) — see review R-1 |
| `waybill_line_tolls` | Платные дороги | = engine `cost.title.tolls` |
| `waybill_line_lodging` | Ночёвки | = engine `cost.title.lodging` |
| `waybill_line_food` | Питание | engine has «Еда» — review R-1 |
| `waybill_line_tickets` | Билеты | = engine `cost.title.tickets` |
| `waybill_reserve` | Резерв 10% | engine has «Запас» — review R-1 |
| `waybill_reserve_sub` | на пробки и «давай заедем» | |
| `waybill_total` | ИТОГО | |
| `waybill_issued` | Выдано | |
| `waybill_left` | Остаток | |
| `waybill_over` | Перерасход | |
| `waybill_over_hint` | Дешевле: другая ночёвка, меньше музеев или «Просто доехать» | engine `hint.*` are the long forms (§10) |
| `waybill_footnote_sample` | Пример расчёта: цены средние по трассе на {month} {year}, точные — при бронировании. | `{month}` = engine `months` (nominative), e.g. «октябрь 2026» |
| `waybill_footnote_real` | Расчёт: цены средние по трассе на {month} {year}, точные — при бронировании. | after real data (SPEC 5.6) |
| `waybill_save` | Сохранить офлайн | |
| `waybill_saved` | Сохранено | the check is **not** a character (Verst Sans Narrow has no U+2713; it fell back to «√»): draw §17.4 `check` 16 × 16, stroke 2, same colour as the text, gap 6, after the text |
| `waybill_share` | Отправить экипажу | |
| `waybill_sync_failed` | Не удалось синхронизировать расчёт — повторим позже | toast |
| `waybill_stamp_top` | ВЕРСТА | decorative, not read |
| `waybill_stamp_mid` | В ПУТЬ |  |
| `waybill_stamp_bottom` | ГОТОВЫ |  |
| `cd_waybill_heading` | Путевой лист легкового автомобиля, номер {n} | |
| `cd_waybill_line` | {name}, {amount} рублей. Расчёт: {formula_spoken}. {expand} |  |
| `cd_waybill_expand` | Раскрыть подробности |  |
| `cd_waybill_collapse` | Свернуть подробности |  |
| `cd_waybill_reserve` | Резерв 10 процентов, на пробки и «давай заедем», {amount} рублей | |
| `cd_waybill_total` | Итого примерно {amount} рублей | |
| `cd_waybill_ready` | Путевой лист готов: итого примерно {amount} рублей | announcement |
| `pro_plate` | Поездка Pro · безлимит, PDF, карты без сети | |
| `pro_plate_joined` | Поездка Pro · вы в списке | the check is **not** a character (Verst Sans Narrow has no U+2713; it fell back to «√»): draw §17.4 `check` 16 × 16, stroke 2, same colour as the text, gap 6, after the text |
| `pro_title` | Поездка Pro | sheet |
| `pro_intro` | Скоро. Отметьте, что пригодится, — так поймём, что делать первым. | |
| `pro_unlimited` | Сколько угодно сохранённых поездок | |
| `pro_pdf` | Путевой лист в PDF | |
| `pro_replan` | Перестроить маршрут прямо в дороге | |
| `pro_offline_maps` | Карты без интернета | |
| `pro_join` | Хочу Pro | |
| `pro_no_payment` | Без оплаты и без регистрации. | |
| `pro_joined` | Записали. Расскажем здесь, в приложении, когда Pro будет готов. | |
| `pro_ok` | Понятно | |

Spoken formula (`formula_spoken`): «×» → «умножить на», «/100» → «на сто», «+» → «плюс», «≈» → «примерно», «₽» → «рублей» (with the number), «л» → «литров», «км» → «километров».

## 8. 5.7 Exit and «Мои поездки»

| Key | Text | Notes |
| --- | --- | --- |
| `exit_header` | НОЧЁВКА {k} ИЗ {n} | |
| `exit_header_km` | КМ {km} · {time} | |
| `exit_sign_centre` | центр | exit sign |
| `exit_sign_distance_m` | {m} м | «800 м» |
| `exit_sign_distance_km` | {km} км | «1,2 км» |
| `exit_sign_no_distance` | ночёвка | exit-sign row 2 when the engine gives no exit → hotel distance (mock build, 5.7 §8) |
| `exit_turn` | поворотник | decorative |
| `exit_book` | Забронировать ночь | |
| `exit_book_partner` | через Яндекс Путешествия | |
| `exit_book_open` | Открыть бронирование | booked |
| `exit_booked_price` | забронировано | |
| `exit_link_error` | Не получилось открыть бронирование. Попробуйте ещё раз | toast |
| `exit_return_title` | Забронировали? | dialog |
| `exit_return_body` | Отметим ночёвку в {town_prep} как забронированную | |
| `exit_return_yes` | Да, забронировали | |
| `exit_return_no` | Ещё нет | |
| `exit_booked_badge` | забронировано | `HotelOption` price slot in the booked state (= `exit_booked_price`, kept for clarity) |
| `exit_booked_toast` | Отметили: ночёвка в {town_prep} забронирована | toast after «Да, забронировали», with `common_undo` (6 s) to remove the mark |
| `exit_book_none` | нет вариантов с вашими условиями | Book CTA sub-line when the night has no hotel options (5.7 §4) |
| `exit_book_partner_mock` | демо-партнёр, без оплаты | Book CTA sub-line in the mock build (replaces `exit_book_partner`, no real brand) |
| `cd_exit_book_mock` | Забронировать ночь, демо: откроется пример бронирования без оплаты | TalkBack of the Book CTA in the mock build |
| `cd_road_booked` | Ночёвка забронирована | appended to the hotel row on Road ahead |
| `exit_tag_dogs` | можно с собакой | decisions.md OI-30 |
| `exit_tag_family` | семейный номер |  |
| `exit_tag_parking` | парковка |  |
| `exit_tag_parking_guarded` | охраняемая парковка |  |
| `cd_exit_sign` | Указатель: съезд на {town}, центр, гостиница через {distance_spoken} | |
| `cd_exit_heading` | Ночёвка {k} из {n}, километр {km}, приезд в {time}. {town} | |
| `cd_exit_group` | Где ночуем | radio group |
| `cd_exit_option` | {name}, {tags}, примерно {amount} рублей за ночь | |
| `cd_exit_book` | Забронировать ночь через Яндекс Путешествия, откроется Яндекс Путешествия | |
| `trips_title` | Мои поездки | sheet D-1 |
| `trips_subtitle` | {n} {saved} · открываются без сети | [plural: `plural_saved`] |
| `trips_row_meta` | {dates} · {d} {days} · {crew} | |
| `trips_near_limit` | Сохранено {n} из 50 — удалите старые, чтобы освободить место | |
| `trips_delete_title` | Удалить поездку «{name}»? | |
| `trips_delete_body` | Она пропадёт с этого телефона | |
| `trips_delete_yes` | Удалить | |
| `trips_delete_no` | Оставить | |
| `trips_deleted` | Поездка удалена | + `common_undo` |
| `trips_delete_action` | Удалить | TalkBack custom action and long-press menu item on a row (D-1) |
| `trips_limit_reached_title` | Место для поездок закончилось | = `common_storage_full_title`; `NaviDialog` when saving trip 51 |
| `trips_limit_reached_body` | Сохранено 50 из 50. Удалите старую поездку, чтобы сохранить эту | |
| `trips_limit_reached_open` | Открыть «Мои поездки» | primary; secondary = `common_dialog_cancel` |
| `trips_past` | прошла | small label before the meta of a past trip (D-1 order: upcoming first) |
| `cd_trips_deleted` | Поездка «{name}» удалена. Вернуть, кнопка | live region for the undo toast |
| `cd_trips_row` | {name}, {dates}, {d} {days}, примерно {amount} рублей. Открыть | |

## 9. Plurals (`<plurals>`, ICU one / few / many / other)

| Key | one | few | many | other |
| --- | --- | --- | --- | --- |
| `plural_day` | день | дня | дней | дня |
| `plural_day_gen` | день | дня | дней | дня |
| `plural_day_upper` | ДЕНЬ | ДНЯ | ДНЕЙ | ДНЯ |
| `plural_night` | ночь | ночи | ночей | ночи |
| `plural_route` | маршрут | маршрута | маршрутов | маршрута |
| `plural_variant` | вариант | варианта | вариантов | варианта |
| `plural_saved` | сохранённая | сохранённые | сохранённых | сохранённой |
| `plural_adult` | взрослый | взрослых | взрослых | взрослого |
| `plural_child` | ребёнок | ребёнка | детей | ребёнка |
| `plural_via` | заезд | заезда | заездов | заезда |
| `plural_stage` | этап | этапа | этапов | этапа |
| `plural_hour` | час | часа | часов | часа |
| `plural_minute` | минута | минуты | минут | минуты |
| `plural_km_spoken` | километр | километра | километров | километра |
| `plural_rub_spoken` | рубль | рубля | рублей | рубля |

`plural_day_gen` is used after «за» («за 1 день», «за 3 дня», «за 5 дней»); `plural_minute` has the same forms as the engine's `plural.minute`.

Engine plurals (`strings.ru.json`): `plural.day`, `plural.minute`, `plural.meal`, `plural.seat`, `plural.region_prep` — identical forms; the client uses its own `<plurals>` for UI text and never re-plurals engine output.

## 10. API errors (SPEC §12) — client strings, same text as the server `message`

| Key | Code | Text | Notes |
| --- | --- | --- | --- |
| `error_invalid_input` | `INVALID_INPUT` | Проверьте параметры поездки |  |
| `error_unreachable` | `UNREACHABLE` | Не нашли дорогу на машине до этой точки |  |
| `error_too_short` | `TOO_SHORT` | Слишком близко для поездки на машине |  |
| `error_no_lodging` | `NO_LODGING` | Не нашли ночёвку с вашими условиями — показали ближайшую подходящую | = engine `warning.NO_LODGING` |
| `error_rate_limited` | `RATE_LIMITED` | Слишком много запросов, подождите минуту |  |
| `error_upstream` | `UPSTREAM` | Сервис маршрутов временно недоступен |  |
| `error_network` | (client) | Нет связи с сервером. Проверьте интернет и попробуйте ещё раз |  |


<!-- BEGIN engine tables (design/tools/gen_copy_engine.py) -->

## 11. Engine reason templates — `reasons.ru.json`

Every key of `backend/planner/verst_planner/resources/reasons.ru.json` (52 keys), regenerated by `design/tools/gen_copy_engine.py`. "Example" renders the template with the Golden-Ring data (first letter capitalised, as the renderer does); "max" is the worst case («Переславле-Залесском», 120 km shift, 900 km/day, dog; the `overnight.shift.*` rows include the appended `overnight.cap_ok`). Limit 140 characters; the longest rendered reason is 124 characters — **all pass**.

| Key | Template | Params | Where it shows | Example | max | Review |
| --- | --- | --- | --- | --- | --- | --- |
| `overnight.shift.hotels` | {shift}: здесь больше отелей{crew_suffix}. | crew_suffix, shift | Exit reason sentence (5.7 D7), Road-ahead hotel-row note | Не в Ростове Великом, а на 55 км дальше: здесь больше отелей, куда пускают с собакой. Ваши 300 км в день не превышены. | 124 | OK |
| `overnight.shift.quality` | {shift}: город интереснее для вечера и утра. | shift | Exit reason sentence (5.7 D7), Road-ahead hotel-row note | Не в Ростове Великом, а на 55 км дальше: город интереснее для вечера и утра. Ваши 300 км в день не превышены. | 115 | OK |
| `overnight.shift.evening` | {shift}: вечером можно прогуляться по центру. | shift | Exit reason sentence (5.7 D7), Road-ahead hotel-row note | Не в Ростове Великом, а на 55 км дальше: вечером можно прогуляться по центру. Ваши 300 км в день не превышены. | 116 | OK |
| `overnight.on_target` | Как раз на вашей дневной норме. | — | Exit reason sentence (5.7 D7), Road-ahead hotel-row note | Как раз на вашей дневной норме. | 31 | OK |
| `overnight.cap_ok` |  Ваши {daily_km} км в день не превышены. | daily_km | Exit reason sentence (5.7 D7), Road-ahead hotel-row note | Ваши 300 км в день не превышены. | 32 | appended; starts with a space by design |
| `overnight.shift.later` | Не в {other_prep}, а на {dkm} км дальше | dkm, other_prep | Exit reason sentence (5.7 D7), Road-ahead hotel-row note | Не в Ростове Великом, а на 55 км дальше | 45 | fragment — only used as `{shift}` |
| `overnight.shift.earlier` | Не в {other_prep}, а на {dkm} км раньше | dkm, other_prep | Exit reason sentence (5.7 D7), Road-ahead hotel-row note | Не в Ростове Великом, а на 55 км раньше | 45 | fragment — only used as `{shift}` |
| `overnight.shift.limit` | На {dkm} км раньше вашего предела | dkm | Exit reason sentence (5.7 D7), Road-ahead hotel-row note | На 55 км раньше вашего предела | 31 | fragment — only used as `{shift}` |
| `overnight.widened` | Ночёвку с вашими условиями нашли только на {dkm} км {dir} цели дня. | dir, dkm | Exit reason sentence (5.7 D7), Road-ahead hotel-row note | Ночёвку с вашими условиями нашли только на 55 км дальше цели дня. | 66 | OK |
| `overnight.no_hotel` | Не нашли отель с вашими условиями — заложили среднюю цену, уточните при бронировании. | — | Exit reason sentence (5.7 D7), Road-ahead hotel-row note | Не нашли отель с вашими условиями — заложили среднюю цену, уточните при бронировании. | 85 | OK |
| `overnight.template` | Ночёвка из готового маршрута «{route}». | route | Exit reason sentence (5.7 D7), Road-ahead hotel-row note | Ночёвка из готового маршрута «Золотое кольцо». | 56 | OK |
| `crew_suffix.dog` | , куда пускают с собакой | — | suffix inside overnight.shift.hotels | , куда пускают с собакой | 24 | OK |
| `crew_suffix.family` |  с семейными номерами | — | suffix inside overnight.shift.hotels | С семейными номерами | 20 | OK |
| `crew_suffix.none` | (empty) | — | suffix inside overnight.shift.hotels | (empty) | 0 | empty by design |
| `fuel.evening` | Заправиться вечером, чтобы утром сразу ехать. | — | Road-ahead fuel-row note | Заправиться вечером, чтобы утром сразу ехать. | 45 | OK |
| `fuel.range` | Через {km} км в баке останется меньше 20% — заправимся здесь. | km | Road-ahead fuel-row note | Через 40 км в баке останется меньше 20% — заправимся здесь. | 60 | OK |
| `fuel.coincide` | Заправка рядом с остановкой — без лишнего съезда. | — | Road-ahead fuel-row note | Заправка рядом с остановкой — без лишнего съезда. | 49 | OK |
| `fuel.last` | Последняя заправка до дома. | — | Road-ahead fuel-row note | Последняя заправка до дома. | 27 | OK |
| `rest.generic` | Разминка {min} {min_word} после {drive} за рулём. | drive, min, min_word | Road-ahead rest-row note | Разминка 20 минут после двух часов за рулём. | 48 | OK — R-2 resolved (`{min_word}`) |
| `rest.who` | Разминка {min} {min_word}: {who}. | min, min_word, who | Road-ahead rest-row note | Разминка 20 минут: ребёнку побегать, собаке погулять. | 53 | OK — R-2 resolved |
| `rest.roadside` | Сделайте остановку на 15 минут — подходящей площадки рядом нет. | — | Road-ahead rest-row note | Сделайте остановку на 15 минут — подходящей площадки рядом нет. | 63 | OK |
| `lunch.kids` | Обед, есть детское меню. | — | Road-ahead lunch-row note | Обед, есть детское меню. | 24 | OK |
| `lunch.parking` | Обед, парковка у входа. | — | Road-ahead lunch-row note | Обед, парковка у входа. | 23 | OK |
| `lunch.default` | Обед в {town_prep}. | town_prep | Road-ahead lunch-row note | Обед в Иванове. | 28 | OK |
| `sight.default` | {dwell} на осмотр. | dwell | Road-ahead sight-row note | Полтора часа на осмотр. | 23 | OK — R-3 resolved (renderer capitalises the first letter) |
| `sight.dog_waits` | {dwell} на осмотр. Собака ждёт с одним из взрослых. | dwell | Road-ahead sight-row note | Полтора часа на осмотр. Собака ждёт с одним из взрослых. | 56 | OK — R-3 resolved |
| `sight.osm` | По открытым данным. | — | Road-ahead sight-row note | По открытым данным. | 19 | OK |
| `start.default` | Выезд в {time}. | time | Road-ahead start-row note | Выезд в 08:00. | 14 | OK |
| `finish.home` | Дома к {part_of_day}. | part_of_day | Road-ahead finish-row note | Дома к вечеру. | 14 | OK; `part_of_day` gives «обеду / ужину / вечеру» |
| `finish.default` | Финиш. | — | Road-ahead finish-row note | Финиш. | 6 | OK |
| `via.user` | Заезд по вашей просьбе. | — | Road-ahead via-row note | Заезд по вашей просьбе. | 23 | OK |
| `alternatives.none` | Других вариантов в это время поблизости нет. | — | Replace sheet D-6 body / note | Других вариантов в это время поблизости нет. | 44 | OK — the replace sheet shows this engine text (state `replace-none-note`); no UI duplicate |
| `alternatives.one` | Нашли только один вариант в это время. | — | Replace sheet D-6 body / note | Нашли только один вариант в это время. | 38 | OK |
| `stage.route` | Прокладываем дорогу | — | Drive step line (5.4 D5) | Прокладываем дорогу | 19 | OK |
| `stage.split` | Делим путь на {n} {days_word} по ≈ {km} км | days_word, km, n | Drive step line (5.4 D5) | Делим путь на 3 дня по ≈ 40 км | 31 | OK |
| `stage.split_ring` | Делим кольцо на {n} {days_word} по ≈ {km} км | days_word, km, n | Drive step line (5.4 D5) | Делим кольцо на 3 дня по ≈ 40 км | 33 | OK |
| `stage.lodging.dog` | Ищем отели, куда пустят с собакой | — | Drive step line (5.4 D5) | Ищем отели, куда пустят с собакой | 33 | OK |
| `stage.lodging.family` | Ищем отели с семейными номерами | — | Drive step line (5.4 D5) | Ищем отели с семейными номерами | 31 | OK |
| `stage.lodging.default` | Ищем, где удобно переночевать | — | Drive step line (5.4 D5) | Ищем, где удобно переночевать | 29 | OK |
| `stage.lodging.none` | Ищем остановки по пути | — | Drive step line (5.4 D5) | Ищем остановки по пути | 22 | OK |
| `stage.hours` | Сверяем часы работы | — | Drive step line (5.4 D5) | Сверяем часы работы | 19 | OK |
| `stage.fuel` | Считаем бензин: {consumption} л на 100 км | consumption | Drive step line (5.4 D5) | Считаем бензин: 8,0 л на 100 км | 32 | OK — R-4 resolved (`fmt_consumption`, «8,0») |
| `stage.cost` | Считаем, сколько стоит поездка | — | Drive step line (5.4 D5) | Считаем, сколько стоит поездка | 30 | OK |
| `hint.cheaper_overnight` | Выберите ночёвку дешевле | — | Waybill over-budget hints (long form) | Выберите ночёвку дешевле | 24 | OK |
| `hint.fewer_sights` | Уберите пару платных мест | — | Waybill over-budget hints (long form) | Уберите пару платных мест | 25 | OK |
| `hint.just_drive` | Попробуйте режим «Просто доехать» | — | Waybill over-budget hints (long form) | Попробуйте режим «Просто доехать» | 33 | OK |
| `warning.NO_LODGING` | Не нашли ночёвку с вашими условиями — показали ближайшую подходящую | — | Road-ahead plates / day lines, Drive warning step | Не нашли ночёвку с вашими условиями — показали ближайшую подходящую | 67 | OK |
| `warning.FUEL_GAP` | На участке {km} км мало заправок — заправьтесь заранее | km | Road-ahead plates / day lines, Drive warning step | На участке 40 км мало заправок — заправьтесь заранее | 53 | OK |
| `warning.DAY_OVER_BUDGET` | День {day} получился длинным — можно убрать остановку | day | Road-ahead plates / day lines, Drive warning step | День 2 получился длинным — можно убрать остановку | 49 | R-5: key says "budget", text is about time; rename to `DAY_TOO_LONG` at the next contract version |
| `warning.TOLLS_UNAVOIDABLE` | Без платных дорог не проехать — платный участок учтён в расчёте | — | Road-ahead plates / day lines, Drive warning step | Без платных дорог не проехать — платный участок учтён в расчёте | 63 | OK |
| `warning.UNVERIFIED_PLACES` | Часть мест по открытым данным — не проверены | — | Road-ahead plates / day lines, Drive warning step | Часть мест по открытым данным — не проверены | 44 | OK |
| `warning.STOP_CLOSED` | «{name}» в этот день закрыт — убрали из маршрута | name | Road-ahead plates / day lines, Drive warning step | «Ипатьевский монастырь» в этот день закрыт — убрали из маршрута | 78 | OK — shown as a day line on 5.5 (day-level warning) |

## 12. Engine UI strings — `strings.ru.json`

Shown to the user through cost formulas, labels, suggestion sub-lines, share text and notes; the app never duplicates them.

| Key | Text | Review |
| --- | --- | --- |
| `months` | январь, февраль, март, апрель, май, июнь, июль, август, сентябрь, октябрь, ноябрь, декабрь | OK |
| `plural.day` | день, дня, дней | OK |
| `plural.minute` | минута, минуты, минут | OK |
| `plural.meal` | приём, приёма, приёмов | OK |
| `plural.seat` | место, места, мест | OK |
| `plural.region_prep` | регионам, регионам, регионам | OK |
| `duration.30` | полчаса | OK |
| `duration.60` | час | OK |
| `duration.90` | полтора часа | OK |
| `duration.120` | два часа | OK |
| `duration.gen.30` | получаса | OK |
| `duration.gen.60` | часа | OK |
| `duration.gen.90` | полутора часов | OK |
| `duration.gen.120` | двух часов | OK |
| `duration.hm` | {h} ч {m} мин | OK |
| `duration.h` | {h} ч | OK |
| `duration.m` | {m} мин | OK |
| `part_of_day.morning` | обеду | OK |
| `part_of_day.afternoon` | ужину | OK |
| `part_of_day.evening` | вечеру | OK |
| `who.child` | ребёнку побегать | OK |
| `who.children` | детям побегать | OK |
| `who.dog` | собаке погулять | OK |
| `who.join` | ,  | OK |
| `label.map_point` | Точка на карте | OK |
| `label.roadside_night` | Ночёвка у трассы {road_ref}, {km} км | OK |
| `label.roadside_night_noref` | Ночёвка у трассы, {km} км | OK |
| `label.trip_title` | {origin} → {destination} | OK |
| `label.round_title` | {origin} → {destination} → {origin} | OK |
| `label.dir_earlier` | раньше | OK |
| `label.dir_later` | дальше | OK |
| `warning.nearest` | Ближайшая подходящая: {name}, {town}, {dkm} км от ночёвки | used on Exit; Road ahead uses `note.nearest` |
| `note.nearest` | Ближайшая подходящая: {name}, {town}, {dkm} км | OK |
| `note.unverified` | не проверено | OK |
| `cost.title.fuel` | Бензин {fuel_type} | OK — R-1 resolved |
| `fuel_type.ai92` | АИ-92 | OK |
| `fuel_type.ai95` | АИ-95 | OK |
| `fuel_type.dt` | ДТ | OK |
| `cost.title.fuel.dt` | Дизель | OK |
| `cost.title.tolls` | Платные дороги | OK |
| `cost.title.lodging` | Ночёвки | OK |
| `cost.title.food` | Питание | OK — R-1 resolved |
| `cost.title.tickets` | Билеты | OK |
| `cost.title.reserve` | Резерв {pct}% | OK — R-1 resolved |
| `cost.fuel.one` | {km} км × {cons} л/100 × {price} ₽ | OK |
| `cost.fuel.many` | {km} км × {cons} л/100 × ≈ {price} ₽ (средняя по {n} {regions_word}) | R-6: long, wraps to 2 lines on the Waybill (allowed) |
| `cost.fuel.row` | {km} км × {cons} л/100 × {price} ₽ = {rub} | OK |
| `cost.fuel.none` | без поездки по дорогам | OK |
| `cost.tolls.item` | {road}: {rub} | OK |
| `cost.tolls.join` |  +  | OK |
| `cost.tolls.none` | платных дорог нет | OK |
| `cost.tolls.day` | днём | OK |
| `cost.tolls.night` | ночью | OK |
| `cost.tolls.row` | {road}, {when} | OK |
| `cost.lodging.equal` | {towns}, {nights} × {price} | OK |
| `cost.lodging.item` | {town} {price} | OK |
| `cost.lodging.item_rooms` | {town} {rooms} номера × {price} | OK |
| `cost.lodging.item_rooms_many` | {town} {rooms} номеров × {price} | OK |
| `cost.lodging.join` |  +  | OK |
| `cost.lodging.default_suffix` |  (средняя цена) | OK |
| `cost.lodging.none` | без ночёвок | OK |
| `cost.lodging.row` | Ночь {day}: {town} | OK |
| `cost.lodging.row_formula` | {rooms} × {price} | OK |
| `cost.food.uniform` | {people} чел. × {meals} {meals_word} × {check} | D-16: «3 чел. × 5 приёмов × 600» |
| `cost.food.avg` | {people} чел. × {meals} {meals_word} × ≈ {check} (в среднем) | OK |
| `cost.food.none` | без остановок на еду | OK |
| `cost.food.row` | День {day} | OK |
| `cost.food.meal.breakfast` | завтрак | OK |
| `cost.food.meal.lunch` | обед | OK |
| `cost.food.meal.dinner` | ужин | OK |
| `cost.food.meal_item` | {meal} {check} | OK |
| `cost.food.meal_join` |  +  | OK |
| `cost.tickets.formula` | {n} {seats_word} × ({adults} взр. + {children} реб.) | OK |
| `cost.tickets.formula_adults` | {n} {seats_word} × {adults} взр. | OK |
| `cost.tickets.none` | вход свободный | same text as `road_free` |
| `cost.tickets.row` | {adults} × {adult} | OK |
| `cost.tickets.row_children` | {adults} × {adult} + {children} × {child} | OK |
| `cost.reserve` | на пробки и «давай заедем» | OK — R-1 resolved |
| `share.header` | {title} · {km} км · {days} {days_word} | OK |
| `share.day` | День {day} · {km} км | OK |
| `share.stop` | {time} {name} | OK |
| `share.total` | Итого ≈ {total} на {people} чел. | D-11 follows this format |
| `label.roadside_break` | Остановка у дороги | OK |
| `suggest.sub.city` | город · {region} | OK — the Navigator suggestion sub-line comes from the engine; no UI duplicate |
| `suggest.sub.place` | место · {region} | OK — as above |

<!-- END engine tables -->

## 13. Review findings for the Developer (DEV-005) and the Manager

| ID | File · key | Finding | Requested change |
| --- | --- | --- | --- |
| R-1 (resolved by DEV) | `strings.ru.json` `cost.title.food`, `cost.title.reserve`, `cost.title.fuel`, `cost.reserve` | Line titles differ from the approved Waybill: «Еда» vs «Питание», «Запас» vs «Резерв 10%», «Бензин» vs «Бензин АИ-95»; the reserve sub-line repeats «10%» | `cost.title.food` → «Питание»; `cost.title.reserve` → «Резерв {pct}%»; `cost.title.fuel` → «Бензин {fuel_type}» (АИ-92 / АИ-95; diesel keeps «Дизель»); `cost.reserve` → «на пробки и «давай заедем»» |
| R-2 (resolved by DEV) | `reasons.ru.json` `rest.generic`, `rest.who` | «{min} минут» is a fixed plural: 21 → «21 минут» | add `{min_word}` from `plural.minute`: «Разминка {min} {min_word} …» |
| R-3 (resolved by DEV) | `sight.default`, `sight.dog_waits` | The sentence starts with `{dwell}` («полтора часа»), lowercase | the renderer capitalises the first character of every rendered reason (one rule in `explain/`, covers future templates) |
| R-4 (resolved by DEV) | `stage.fuel` | `{consumption}` must be «8,0», not «8.0» | format decimals with a comma in `explain/ru.py` |
| R-5 | `warning.DAY_OVER_BUDGET` | Key name suggests money, text is about a long day (time budget, SPEC 7.2 step 10) | text OK; rename the key to `DAY_TOO_LONG` when the API contract is next versioned. The design shows it as a day line (5.5, canvas `5.5-road-ahead-no-lodging-over-budget`) |
| R-6 | `cost.fuel.many` | Long formula line | keep, the Waybill formula line wraps to 2 lines (allowed) |
| R-7 | — | Engine text used directly by the UI (no client duplicate): `alternatives.none` (replace sheet), `suggest.sub.*` (Navigator sub-lines). Missing engine strings the design needs: the NO_LODGING overnight note uses `note.nearest` (present); the Road-ahead day meta «≈ {h} ч за рулём» and «домой» are client strings (§6) | none |

D-16 applied: the Waybill example uses 5 meals («3 чел. × 5 приёмов × 600» = 9 000), and all reference totals are ≈ 30 500 ₽ (screens 5.5, 5.6, open-issues D-1, D-11, checklist P-15).

## 14. Mock build (Sprint 2, DES-104)

Keys for the on-device mock build (architecture-android-mvp M§9, ADR-0010). Specs are open-issues D-13…D-16 (design numbering; not the architecture decision D-16).

| Key | Text | Notes |
| --- | --- | --- |
| `engine_starting_cd` | Готовим маршруты рядом | TalkBack of the 5.1 loading sign while `EngineStatus.Starting` (state `engine-starting`) |
| `engine_failed_title` | Планировщик не запустился | 5.1 plate, state `engine-failed` (D-15) |
| `engine_failed_text` | Сохранённые поездки на месте — попробуйте запустить ещё раз | under the title |
| `common_engine_error` | Сохранили. Планировщик не ответил — суммы пересчитаны на телефоне | toast, M§6.3 |
| `mock_partner_title` | Бронирование ночи | `MockPartnerSheet` title (D-13) |
| `mock_partner_line` | «Придорожная» — вымышленный партнёр · демо | partner line; «Придорожная» is a fictional name used only in the demo (no real brand anywhere in the mock build, Manager 2026-10-24) |
| `mock_partner_badge` | ДЕМО | badge at the sheet title (D-13) |
| `mock_partner_hotel` | {hotel}, {town} | |
| `mock_partner_dates` | {checkin} — {checkout} · {nights} {nights_word} | [plural: `plural_night`]; dates «7 нояб.» |
| `mock_partner_guests` | Гости: {guests} | guests = `waybill_crew_*` parts |
| `mock_partner_price` | ≈ {amount} ₽ за {nights} {nights_word} | [plural: `plural_night`] |
| `mock_partner_note` | Это демо-сборка: настоящего бронирования и оплаты нет. В рабочей версии здесь откроется сайт партнёра по бронированию с этими датами. | |
| `mock_partner_back` | Вернуться в Версту | primary button; dismissal → «Забронировали?» |
| `cd_mock_partner` | Бронирование ночи, демо, вымышленный партнёр. {hotel}, {checkin} — {checkout}, примерно {amount} рублей | pane description |
| `mock_map_unavailable` | Карта появится в следующей версии — пока введите город или адрес | plate after tapping «точка на карте» (D-14) |
| `mock_build_line` | Сборка {n} · {sha} · демо-данные | D-4 footer, long-press 2 s → debug panel (D-16) |
| `mock_share_note` | Посчитано в демо-сборке «Версты», цены примерные | last line of the share text instead of the link (D-16) |
| `cd_windshield_you_are_mock` | Старт: {city}. Изменить | «ВЫ: …» opens Navigator with focus ОТКУДА (no location in the mock) |
| `debug_label_title` | Отладка | debug panel (not in visual QA) |
| `debug_label_world` | Мир данных | |
| `debug_label_clock` | Часы | |
| `debug_clock_system` | системные | |
| `debug_clock_golden` | как в эталонах | |
| `debug_label_offline` | Имитировать отсутствие сети | |
| `debug_label_slow` | Задержать готовность плана, с | |
| `debug_label_force_error` | Вызвать ошибку планировщика | |
| `debug_force_none` | нет | |
| `debug_label_timings` | Время работы планировщика | |
| `debug_label_parity` | Расхождения с эталонами | |
| `debug_label_build` | Сборка | |
| `debug_reset` | Сбросить данные | |
| `debug_reset_title` | Сбросить все данные? | dialog |
| `debug_reset_body` | Удалим сохранённые поездки и настройки на этом телефоне | |
| `debug_reset_yes` | Сбросить | |
| `debug_reset_no` | Отмена | |
