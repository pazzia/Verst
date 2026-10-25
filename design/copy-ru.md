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
| `windshield_meta_round_trip` | туда и обратно | caption meta suffix of a there-and-back ready route: «2 дня · по М-8 · туда и обратно»; not added when the subtitle already says «по кругу» (S3-QA, was pending) |
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
| `navigator_type_address` | У | badge of an address row (5.12 §2; «У» = улица, as the address rows always name a street). S3-QA: renamed from the unused `navigator_type_street` |
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
| `instruments_mood_label` | КАК ЕДЕМ | Sprint 4: was «НАСТРОЕНИЕ» (5.3 §9) |
| `instruments_mood_calm` | Спокойно | engine `calm`; Sprint 4: no longer pre-selected by children |
| `instruments_mood_more` | Весело и познавательно | engine `fun` (v2 `more_stops` maps to it, ADR-0015 §5); key kept, text replaced |
| `instruments_mood_drive` | Только доехать | engine `just_drive`; = `hint.just_drive` wording (Architect: «Попробуйте режим «Только доехать»») |
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
| `waybill_over_hint` | Дешевле: другая ночёвка, меньше музеев или «Только доехать» | engine `hint.*` are the long forms (§10) |
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
| `plural_place` | место | места | мест | места |
| `plural_point` | точка | точки | точек | точки |
| `plural_person` | человек | человека | человек | человека |
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
| `road_night_prefix` | — | Ночь {n}: {text} | Road-ahead plate when more than one night has a warning: «Ночь 2: не нашли ночёвку с вашими условиями — показали ближайшую подходящую» (first letter of `{text}` lowercased after the colon); a single plate stays without the prefix (S3-QA2) |
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
| `warning.UNVERIFIED_PLACES` | Места — из открытых данных: часы и цены уточняйте | — | **Info line, not a warning plate** (5.5 §9): under the chips with the `info` icon + «О данных», like `route_approx`; never on the Drive warning step | Часть мест по открытым данным — не проверены | 48 | **CHANGE (S3-FINAL P1-02)** — Architect: update `reasons.ru.json` |
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
| `debug_mock_location` | Имитация местоположения | debug panel: mock location picker (S3-QA, was pending) |
| `debug_real_photos` | Настоящие фото Commons | debug panel toggle (S3-QA2, was pending) |

## 15. Sprint 3 — budget fit, cards, «По городу», location and addresses, hand-off

Specs: `design/screens/5.8`–`5.13`, components §17.5–§23; aligned with ADR-0011…0014 and `docs/backlog-sprint3.md` (DES-300…305). **Brand rule:** real brand names appear **only** in keys starting with `handoff_` (ADR-0014 allow-list `backend/planner/tests/brand_allowlist.txt`); every other key, including TalkBack keys, stays brand-free. The existing `stopmenu_yandex_navi`, `stopmenu_yandex_maps`, `stopmenu_2gis`, `stopmenu_install`, `exit_book_partner` and `cd_exit_book` stay in the deck for history but are **not used** (deny-listed); their Sprint 3 replacements are below.

### 15.1 Budget fit (5.8, DES-300)

| Key | Text | Notes |
| --- | --- | --- |
| `budget_nofit_title` | Не помещается в бюджет | 5.8 h1 |
| `budget_nofit_sign` | {amount} ₽ | number in the round «ограничение» sign, e.g. «30 000 ₽» |
| `budget_nofit_min` | Даже самый экономный вариант — ≈ {amount} ₽ | under the engine `textRu` |
| `budget_nofit_options` | ЧТО МОЖНО СДЕЛАТЬ | section label |
| `budget_option_shorten` | Сократить до {d} {days} | [plural: `plural_day`]; sub = option `titleRu` |
| `budget_option_shorten_sub` | {title} · ≈ {amount} ₽ | «Золотое кольцо · коротко · ≈ 29 700 ₽» |
| `budget_option_cheaper` | Ближе и дешевле: {title} | option `titleRu` |
| `budget_option_cheaper_sub` | ≈ {amount} ₽ · помещается в бюджет | |
| `budget_option_cheaper_sub_over` | ≈ {amount} ₽ · дешевле, но больше бюджета | cheaper-route option with `fits: false`; never «помещается» (S3-QA, was pending) |
| `budget_option_raise` | Поднять бюджет до {amount} ₽ | |
| `budget_option_raise_sub` | тот же маршрут, без изменений | |
| `budget_nofit_cta` | Смотреть варианты | Drive CTA when the outcome is `no_fit` (auto-advance 1 s) |
| `budget_nofit_min_label` | САМЫЙ ЭКОНОМНЫЙ ВАРИАНТ | minimum plate label (uppercase copy) |
| `waybill_tight_label` | Сверх бюджета | Waybill «Остаток» label for a small overrun (value in ink) |
| `budget_show_minimum` | Показать самый экономный вариант | text button; the trip then shows as over budget everywhere |
| `budget_fit_badge` | В БЮДЖЕТЕ | Road ahead footer badge (uppercase copy) |
| `budget_tight_badge` | ЧУТЬ БОЛЬШЕ: +{amount} ₽ | small overrun badge |
| `budget_fitted_title` | Подогнали под бюджет | Waybill heading of the lever lines |
| `budget_lever_line` | {lever}: −{amount} ₽ | one line per lever under the Waybill total |
| `budget_lever_lodging_cheap` | дешевле ночёвки | lever names (engine codes) |
| `budget_lever_family_rooms` | семейные номера | |
| `budget_lever_food_economy` | кафе попроще | |
| `budget_lever_sights_free` | бесплатные места | |
| `budget_lever_fewer_nights` | на день меньше | |
| `budget_lever_variant` | короткий вариант маршрута | |
| `budget_refit` | Подогнать под бюджет | Waybill over-budget action (re-plan → Drive) |
| `budget_alt_breaks` | не в бюджете | replace-sheet row mark (`breaksBudget`) |
| `budget_instruments_fits` | ≈ {amount} ₽ — в бюджете | Instruments caption meta suffix (`estimate.outcome`) |
| `budget_instruments_fitted` | ≈ {amount} ₽ — подгоним под бюджет | estimate needed levers |
| `budget_instruments_nofit` | не помещается в бюджет | `color.accent.redText` |
| `drive_step_budget` | Подбираем под бюджет: {lever} | engine stage text template (key `budget`), for reference |
| `cd_budget_nofit` | Не помещается в бюджет {budget} рублей. Самый экономный вариант примерно {amount} рублей. Есть варианты | |
| `cd_budget_option` | {title}. {sub}. Применить | |

### 15.2 Cards (5.9, DES-301)

| Key | Text | Notes |
| --- | --- | --- |
| `card_photo_credit` | Фото: Wikimedia Commons · {author} · {licence} | ADR-0012 §6 order; tap → file page |
| `card_photo_credit_short` | Фото: Wikimedia Commons | no author / PD |
| `card_photo_area` | Фото района: {town} · Wikimedia Commons | hotels (engine `labelRu`); **mandatory** on hotel cards |
| `card_area_plate` | ФОТО РАЙОНА | plate on the hotel photo (uppercase copy) |
| `card_hotel_fictional` | Гостиница в демо-сборке вымышленная — на фото район, а не она | under the hotel photo |
| `card_hotel_fictional_nophoto` | Гостиница в демо-сборке вымышленная | hotel card while the area photo is a placeholder (none / error / offline): the «на фото район» clause and the `card_photo_area` credit are hidden (S3-QA P1-05) |
| `card_photo_none` | Фото пока нет | placeholder (no file / no free licence) |
| `card_photo_offline` | Фото загрузится, когда будет интернет | placeholder offline |
| `card_photo_error` | Фото не загрузилось | placeholder HTTP error |
| `card_kind_museum` | музей | kind line words (engine `poiKind`) |
| `card_kind_church` | храм | |
| `card_kind_monastery` | монастырь | |
| `card_kind_kremlin` | кремль | |
| `card_kind_park` | парк | |
| `card_kind_monument` | памятник | |
| `card_kind_view` | смотровая площадка | |
| `card_kind_square` | площадь | |
| `card_kind_embankment` | набережная | |
| `card_kind_sight` | достопримечательность | |
| `card_kind_bar` | бар | |
| `card_kind_ryumochnaya` | рюмочная | |
| `card_kind_pub` | паб | |
| `card_kind_craft` | крафтовый бар | |
| `card_kind_hotel` | гостиница · {town} | |
| `card_kind_line` | {kind} · {town} | |
| `card_hours_unverified` | часы уточняйте | when `hours.verified = false` |
| `card_ticket` | билет ≈ {adult} ₽, детский ≈ {child} ₽ | `ticket.estimate = true` → add `card_price_estimate` |
| `card_ticket_free` | вход свободный | |
| `card_per_night` | за ночь | hotel fact after the price: «≈ 6 000 ₽ за ночь» (S3-QA, was pending) |
| `card_price_estimate` | цена примерная | |
| `card_heritage` | объект культурного наследия | |
| `card_unverified` | По открытым данным — может быть неточно | catalogue places (`verified = false`) |
| `card_report` | Сообщить об ошибке | text button (D-7 sheet) |
| `card_pick_hotel` | Выбрать отель | hotel card → 5.7 |
| `card_osm` | Данные о месте: © участники OpenStreetMap | bar cards (ODbL) |
| `cd_card` | Карточка: {name} | pane title |
| `cd_card_photo` | Фото: {name} | |
| `cd_card_photo_area` | Фото района: {town}. Это не фото гостиницы | |
| `cd_card_credit` | Автор фото: {author}, {licence}. Открыть страницу фото | |

### 15.3 «По городу» and the walk result (5.10, 5.11, DES-302)

| Key | Text | Notes |
| --- | --- | --- |
| `city_entry` | По городу | Windshield plate (beside «Мои поездки») |
| `city_entry_sub` | пешком | second word on the plate (`type.body.sm`) |
| `city_title` | По городу | 5.10 h1 |
| `city_plate_kind` | пешком | street-name plate small line |
| `city_start` | Старт: {place} | |
| `city_start_change` | изменить | |
| `city_presets_label` | ГОТОВЫЕ ПРОГУЛКИ | |
| `city_preset_overview` | Обзорный | engine `overview` |
| `city_preset_overview_sub` | главное · {h} ч | default 4 h |
| `city_preset_museums` | Музейный | `museums` |
| `city_preset_museums_sub` | до 4 музеев · {h} ч | default 6 h |
| `city_preset_ryumochnye` | По рюмочным | `ryumochnye`, 18+ |
| `city_preset_ryumochnye_sub` | 18+ · {h} ч · только пешком | |
| `city_preset_beer` | Пивной | `beer`, 18+ |
| `city_preset_beer_sub` | 18+ · {h} ч · только пешком | |
| `city_preset_custom` | Свой маршрут | `custom` |
| `city_preset_custom_sub` | время, интересы, темп | |
| `city_badge_18` | 18+ | |
| `city_kids_blocked` | не с детьми | 18+ preset sub-line when the crew has children (disabled) |
| `city_kids_toast` | Этот маршрут только для взрослых — в экипаже есть дети | |
| `city_custom_title` | Свой маршрут | custom sheet title |
| `city_duration_label` | СКОЛЬКО ГУЛЯЕМ | |
| `city_duration` | {h} ч | chips 2 / 4 / 6 / 8 |
| `city_interests_label` | ЧТО ИНТЕРЕСНО | multi-select |
| `city_interest_history` | история | engine `history` |
| `city_interest_architecture` | архитектура | |
| `city_interest_museums` | музеи | |
| `city_interest_parks` | парки | |
| `city_interest_food` | еда | |
| `city_interest_bars` | бары | 18+ dialog when chosen |
| `city_interest_views` | виды | |
| `city_pace_label` | ТЕМП | |
| `city_pace_slow` | неспешно | |
| `city_pace_normal` | обычный | |
| `city_pace_fast` | бодро | |
| `city_budget_label` | БЮДЖЕТ НА ВСЕХ | tickets + food/drinks for the whole group |
| `city_budget_value` | до {amount} ₽ | chips 2 000 / 5 000 / 10 000 + `instruments_budget_any` |
| `city_return_label` | Вернуться к старту | switch |
| `city_build` | Собрать прогулку | YellowButton in the custom sheet |
| `city_caption_label` | ПРОГУЛКА | |
| `city_caption_title` | {name} · {h} ч | |
| `city_caption_meta` | {town} · старт {time} | before the route exists |
| `city_caption_meta_tomorrow` | {town} · старт завтра в {time} | the engine's `startAt` is on the next day (S3-QA P0-01) |
| `city_go` | ПОШЛИ | start-button label |
| `city_building` | Собираем прогулку… | shimmer caption while `city_route` runs |
| `city_no_city_title` | Рядом нет города | `NO_CITY` |
| `city_no_city_body` | Прогулки строим в городах России. Выберите старт в городе — например, центр Ярославля. | |
| `city_no_city_action` | Выбрать старт | |
| `city_not_enough_title` | Мало мест для такой прогулки | `NOT_ENOUGH_POIS` |
| `city_not_enough_body` | Попробуйте дольше погулять или другой маршрут. | |
| `city_not_enough_longer` | Гулять {h} ч | action: next duration |
| `city_not_enough_other` | Другой маршрут | action: back to presets |
| `age_gate_title` | Маршрут для взрослых | `NaviDialog`, shown **every time** an 18+ preset or «бары» is chosen |
| `age_gate_body` | Бары и рюмочные — только для тех, кому исполнилось 18. Вам есть 18? | |
| `age_gate_yes` | Да, мне есть 18 | primary → `adultConfirmed = true` |
| `age_gate_no` | Нет | secondary → no request |
| `walk_title` | {town}: {name} | 5.11 title sign, e.g. «Ярославль: обзорная прогулка» = engine `titleRu` |
| `walk_heading` | Прогулка | 5.11 h1 |
| `walk_chip_duration` | {h} ч | chips |
| `walk_chip_duration_text` | {dur} ч | chip with pre-formatted hours: «5,5 ч», «4 ч» (decimal comma, no trailing «,0»); use instead of `walk_chip_duration` when the duration is not whole (S3-QA2) |
| `walk_chip_km` | ≈ {km} км пешком | |
| `walk_chip_back` | с возвратом к старту | |
| `walk_header` | Старт {start} · финиш ≈ {finish} | above the first row |
| `walk_header_tomorrow` | Завтра: старт {start} · финиш ≈ {finish} | `startAt` on the next day (S3-QA P0-01) |
| `walk_next` | через {distance} · {min} мин пешком | `{distance}` «600 м» / «1,2 км» |
| `walk_distance_m` | {m} м | `{distance}` under 1 km, rounded to 50 m: «600 м»; ≥ 1 km uses `common_km` «1,2 км» (S3-QA, was pending) |
| `walk_shorter` | Получилось {dur} ч вместо {asked} ч — больше открытых мест рядом нет | `{dur}`, `{asked}` pre-formatted hours («2», «2,5»); note above the column when the engine's duration is shorter than the preset / chosen one (S3-QA P1-02) |
| `walk_start_row` | старт | |
| `walk_finish_row` | финиш | |
| `walk_hours_unverified` | часы работы уточняйте | engine `noteRu` default |
| `walk_responsible` | Пейте умеренно, чередуйте с водой и едой. За руль — только трезвым. | **fixed copy** (backlog); alcohol presets, on the result and in the share text |
| `walk_approx` | Расстояния пешком приблизительные: ±15 % | under the chips |
| `walk_other` | Другой вариант | re-run with `exclude` |
| `walk_remove_stop` | Убрать эту точку | card / stop menu action |
| `walk_footer_label` | СКОЛЬКО СТОИТ ПРОГУЛКА | |
| `walk_footer_total` | ≈ {amount} ₽ на всех | |
| `walk_footer_per_person` | ≈ {amount} ₽ на человека | |
| `walk_footer_free` | Бесплатно | footer amount when the walk total is 0 ₽; the per-person line is hidden (S3-QA P1-03) |
| `walk_footer_free_sub` | вход везде свободный | right-hand line of the free footer |
| `walk_saved_kind` | прогулка | «Мои поездки» meta word for walks |
| `cd_city_preset` | {name}, {sub}. Выбрать | |
| `cd_city_preset_18` | {name}, только для взрослых, {sub}. Выбрать | |

### 15.4 Location and address search (5.12, DES-303, DES-304)

| Key | Text | Notes |
| --- | --- | --- |
| `loc_rationale_title` | Откуда поедем? | sheet |
| `loc_rationale_body` | Разрешите геопозицию — начнём маршрут оттуда, где вы сейчас. Координаты нужны только для старта и не сохраняются. | |
| `loc_allow` | Разрешить | coarse permission |
| `loc_manual` | Выберу сам | text button → ОТКУДА input |
| `loc_searching` | Ищем вас… | ОТКУДА value while the fix runs (≤ 10 s) |
| `loc_here_address` | {address} · вы здесь | online (reverse geocoding), e.g. «ул. Советская, 1 · вы здесь» |
| `loc_here_town` | {town} (по GPS) | offline label |
| `loc_precise` | Точнее | action → fine permission (shown while only coarse is granted) |
| `loc_approx_note` | примерно, по сети | sub-line while the fix is coarse |
| `loc_denied_plate` | Без геопозиции старт — {town}. Изменить можно в навигаторе | plate (last start or Москва) |
| `loc_choose` | Выбрать | action on the denied plate → ОТКУДА input |
| `loc_blocked` | Геопозиция для «Версты» выключена в настройках | |
| `loc_settings` | Настройки | |
| `loc_off` | Геолокация на телефоне выключена | |
| `loc_turn_on` | Включить | |
| `loc_timeout` | Не получилось определить, где вы. Старт — {town} | after 10 s |
| `loc_outside_title` | Вы не в России | outside-Russia state (`insideRussia = false`) |
| `loc_outside_body` | Маршруты строим только по России. Выберите старт в российском городе. | |
| `loc_outside_action` | Выбрать старт | |
| `navigator_from_input` | ОТКУДА — город или адрес | ОТКУДА as an input |
| `addr_find` | Найти адрес | explicit submit (button / IME action); never per keystroke |
| `addr_find_query` | Найти адрес «{q}» | the action row text with the typed query |
| `addr_find_hint` | Город или место — сразу, адрес — по кнопке «Найти адрес» | helper line under the field when the query contains a digit or «ул.» |
| `addr_searching` | Ищем адрес… | |
| `addr_kind` | адрес | suggestion sub type word |
| `addr_sub` | адрес · {city} | |
| `addr_none` | Такого адреса не нашли — проверьте написание | |
| `addr_offline` | Адреса ищутся только с интернетом — города и места доступны | offline hint row |
| `addr_rate` | Подождите секунду и попробуйте ещё раз | if the 1 req/s bucket is empty |
| `addr_attribution` | © OpenStreetMap | under address results (ODbL) |
| `route_approx` | Расстояния приблизительные | Road ahead line when `approxDistances = true` |
| `route_approx_open_data` | Расстояния приблизительные · места из открытых данных | one info line when both `approxDistances` and `UNVERIFIED_PLACES` apply; followed by the «О данных» link (S3-FINAL) |
| `route_approx_more` | О данных | link → «О данных» |
| `about_data_title` | О данных | screen |
| `about_data_body` | Города и места — Wikidata (CC0). Бары и адреса — © участники OpenStreetMap (ODbL). Фото — Wikimedia Commons, у каждого своя лицензия и автор. Вне центральной России расстояния и время в пути посчитаны приблизительно. Гостиницы и кафе в демо-сборке вымышленные. | |
| `cd_loc_searching` | Ищем, где вы | |
| `cd_addr_row` | {name}, {sub}, примерно {km} километров | |

### 15.5 Hand-off (5.13, DES-305) — the only brand-bearing keys

| Key | Text | Notes |
| --- | --- | --- |
| `handoff_navigator` | Открыть в Яндекс Навигаторе | car, app installed (ADR-0014) |
| `handoff_maps_car` | Открыть в Яндекс Картах | car, only Карты installed |
| `handoff_maps_walk` | Пешком в Яндекс Картах | walk |
| `handoff_web` | Открыть Яндекс Карты в браузере | no app |
| `handoff_day` | В навигатор: день {n} | day-header menu item |
| `handoff_from_stop` | Открыть в навигаторе отсюда | stop-menu item (replaces `stopmenu_navigator` text) |
| `handoff_truncated` | Навигатор принимает до 8 промежуточных точек — взяли главные | note under the item when `truncated` |
| `handoff_part` | Часть {k} из {n} | walk split into parts |
| `handoff_toast_web` | Яндекс Навигатор не установлен — открыли карту в браузере | after the fallback |
| `handoff_toast_web_walk` | Яндекс Карты не установлены — открыли карту в браузере | |
| `handoff_offline` | Нужен интернет, чтобы открыть карту в браузере | |
| `handoff_failed` | Не получилось открыть карту. Попробуйте ещё раз | |
| `handoff_cd_navigator` | Открыть маршрут в Яндекс Навигаторе | TalkBack (key kept in the `handoff_` space) |
| `handoff_cd_maps_walk` | Открыть маршрут пешком в Яндекс Картах | |
| `handoff_cd_web` | Открыть маршрут на карте в браузере | |

## 16. Sprint 4 — CEO feedback on build 83 (design for approval)

Specs: §9/§10 «Sprint 4» sections of 5.1, 5.3, 5.5, 5.6, 5.9, 5.10, 5.11, 5.13; components §24–§30; mockups `docs/design-canvas/S4-*.dc.html`. Aligned with ADR-0015 (arch/sprint-4). Brand rule unchanged: «Яндекс» only in `handoff_*` keys.

### 16.1 Windshield (5.1 §9)

| Key | Text | Notes |
| --- | --- | --- |
| `windshield_navi_label_car` | НАВИГАТОР · НА МАШИНЕ | navigator panel label, so the two modes read as a pair |
| `windshield_city_title` | По городу пешком | blue `CityEntryPlate` under the navigator |
| `windshield_city_sub` | {town} · 2–8 ч или без ограничения | `{town}` = the origin town (nominative) |
| `cd_windshield_city` | По городу пешком. {town}, от двух до восьми часов или без ограничения. Открыть | |

### 16.2 Instruments presets (5.3 §9)

| Key | Text | Notes |
| --- | --- | --- |
| `instruments_mood_calm_sub` | меньше остановок, но длинные перерывы; короче перегоны | |
| `instruments_mood_fun_sub` | каждые полтора часа — остановка у интересного места рядом с трассой: размяться и посмотреть | |
| `instruments_mood_drive_sub` | только заправки, еда и ночёвки — без достопримечательностей | |
| `instruments_mood_fun_crew` | Под ваш экипаж: {list} | under the selected fun preset; `{list}` joins the next keys with «, » |
| `instruments_mood_fun_child` | с ребёнком — площадки, зоопарки и интерактивные музеи | |
| `instruments_mood_fun_dog` | с собакой — парки и природа | |
| `instruments_mood_fun_adults` | музеи, виды, кремли и природа | adults only: the whole `{list}` |

### 16.3 Road ahead (5.5 §10)

| Key | Text | Notes |
| --- | --- | --- |
| `road_handoff_cta` | Вести в навигаторе | yellow button under the chips → hand-off sheet (5.13 §5) |
| `road_handoff_cta_sub` | по дням · начнём с дня {n} | `{n}` = today's day (1 before the trip) |
| `road_handoff_day` | вести | day-header outline button |
| `cd_road_handoff_day` | Вести в навигаторе: день {n} | |
| `road_odometer` | {km} км | km post number (variant B) = engine `kmDriven`; the odometer tag is retired (5.5 §10.7) |
| `road_meta_driven` | {ahead} · пройдено {km} км | variant A — **not used** (CEO chose B) |
| `road_km_post_label` | пройдено | **not used** (S4 QA: the label collided with the sign) |
| `road_km_post_legend` | — столбик у дороги: сколько км пройдено от старта | legend under the chips, after a mini post |
| `cd_road_km_post` | пройдено {km} километров | TalkBack |
| `road_parking_inline_paid` | ≈ {amount} ₽ | P part of the costs line |
| `road_parking_inline_free` | бесплатно | |
| `road_parking_inline_unknown` | ? | |
| `cd_road_parking_inline` | Парковка: {value}. Подробнее | `{value}` «примерно 300 рублей» / «бесплатно» / «нет данных» |
| `cd_road_odometer` | пройдено {km} километров от старта | TalkBack, read after «через …» |
| `kind_museum` | МУЗЕЙ | category tags (ADR-0015 §2 whitelist); rows, cards, walks |
| `kind_kremlin` | КРЕМЛЬ | |
| `kind_monastery` | МОНАСТЫРЬ | |
| `kind_temple` | ХРАМ | |
| `kind_park` | ПАРК | |
| `kind_nature` | ПРИРОДА | |
| `kind_viewpoint` | ВИД | |
| `kind_square` | ПЛОЩАДЬ | |
| `kind_embankment` | НАБЕРЕЖНАЯ | |
| `kind_theatre` | ТЕАТР | |
| `kind_zoo` | ЗООПАРК | |
| `kind_interactive` | ИНТЕРАКТИВНЫЙ | science centres, children's museums |
| `kind_playground` | ПЛОЩАДКА | fun preset / walks only |
| `kind_monument` | ПАМЯТНИК | |
| `road_stretch_tag` | РАЗМИНКА {min} МИН | yellow tag on a fun-preset stop |
| `road_stretch_name` | Разминка · {name} | row name of a fun-preset stop |
| `road_from_road` | {min} мин от трассы | appended to the engine reason (`rest.fun.*`) when the app composes it |
| `road_rest_amenities` | есть: {list} | rest row second line from OSM tags; hidden when nothing is known |
| `road_amenity_toilet` | туалет | |
| `road_amenity_tables` | столы | |
| `road_amenity_shelter` | навес | |
| `road_amenity_cafe` | кафе | |
| `road_amenity_playground` | детская площадка | |
| `road_break_title` | Перерыв {min} мин | the fallback break (ADR-0015 §5), at most one per day with a note |
| `road_break_note` | Остановитесь, где удобно: размяться и сменить водителя | only on the first break of the day; later breaks have no note |
| `road_parking_plate_paid` | ≈ {amount} ₽ | supplementary plate under the «P» sign; `{amount}` = engine `parking.rub` |
| `road_parking_plate_free` | бесплатно | |
| `road_parking_plate_unknown` | ? | `parking: null` |
| `road_parking_detail` | парковка · {detail} | text line after the note |
| `road_parking_zone` | {zone} · ≈ {rate} ₽/ч × {h} ч | `{zone}` = engine zone name, default `road_parking_zone_default` |
| `road_parking_zone_default` | платная зона | |
| `road_parking_unknown` | нет данных — уточните на месте | |
| `road_parking_day` | ≈ {amount} ₽ | day header, after a small «P» |
| `road_parking_day_unknown` | ≈ {amount} ₽ + ? | some stops of the day without data |
| `cd_road_parking_day` | Парковки за день: примерно {amount} рублей | add `cd_road_parking_day_unknown` when needed |
| `cd_road_parking_day_unknown` | и {k} без данных | |
| `road_footer_parking` | из них парковки | footer right block; the amount below it |
| `road_parking_sheet_label` | ПАРКОВКА | `ParkingSheet` |
| `road_parking_row_rate` | Тариф | |
| `road_parking_row_stay` | Стоим | |
| `road_parking_row_sunday` | Воскресенье | |
| `road_parking_row_where` | Где | |
| `road_parking_note` | ≈ — цена примерная. Сумма уже в путевом листе и в бюджете. | big cities add the engine note («тарифы в центре меняются в течение дня») |
| `road_parking_ok` | Понятно | |
| `road_parking_paid` | ≈ {rate} ₽/ч · ≈ {amount} ₽ за стоянку | card fact / TalkBack long form |
| `road_parking_free` | бесплатно рядом | `source = free` |
| `road_parking_free_entrance` | бесплатно у входа | OSM parking with `fee=no` ≤ 100 m |
| `road_parking_hotel` | у гостиницы · бесплатно | hotel fact, not a cost |
| `cd_road_parking` | Парковка примерно {rate} рублей в час, за стоянку примерно {amount} рублей | |
| `road_open_data_legend` | — из открытых данных, часы уточняйте | legend after the dotted-ring mark, once under the chips |
| `cd_open_data` | данные из открытых источников, часы уточняйте | TalkBack for the dotted ring on a row |

### 16.4 Waybill (5.6 §9)

| Key | Text | Notes |
| --- | --- | --- |
| `waybill_parking` | Парковки | line title, `P` sign before it |
| `waybill_parking_formula` | платных стоянок: {k} · ≈ {dur} · {towns} | engine `formula` wins when present; `{towns}` «5 городов» or the names when ≤ 2 |
| `waybill_parking_unknown` | + ещё {k} без данных | after the formula when `unknownCount > 0` |
| `waybill_parking_row` | {place}, {h} ч × {rate} | breakdown row (expanded) |
| `waybill_parking_note` | Ночёвки и бесплатные стоянки — 0 ₽. Тарифы средние по городу. | under the breakdown |
| `budget_lever_parking_free` | бесплатные парковки | ADR-0015 §4 lever `parking_free` |

### 16.5 Hand-off chooser (5.13 §5) — brand-bearing, `handoff_*` only

| Key | Text | Notes |
| --- | --- | --- |
| `handoff_sheet_title` | Вести в навигаторе | |
| `handoff_scope_day` | День {n} | tab |
| `handoff_scope_next` | До след. | tab; TalkBack `handoff_cd_scope_next` |
| `handoff_cd_scope_next` | До следующей точки | |
| `handoff_day_line` | {from} → {to} · {km} км · {points} | `{points}` = `plural_point` |
| `handoff_next_line` | Следующая точка: {name} · {km} км | |
| `handoff_app_maps` | Яндекс Карты | card title |
| `handoff_app_navi` | Яндекс Навигатор | card title |
| `handoff_badge_day` | весь день | yellow badge on the app that takes the whole day |
| `handoff_maps_day` | все {points} дня по порядку; в Картах нажмите «В путь» — поведут с голосом | unsigned and signed |
| `handoff_maps_next` | маршрут до точки, с голосом | |
| `handoff_navi_next` | только до следующей точки: {name}, {km} км | unsigned (ADR-0015 §1) |
| `handoff_navi_day` | все {points} дня, сразу ведёт с голосом | signed |
| `handoff_navi_limit` | по ссылке открывается до 5 раз в сутки, потом — в браузере | unsigned only |
| `handoff_explain_unsigned` | Навигатор пока принимает от нас только одну точку, поэтому весь день с остановками ведут Карты — в них тоже есть ведение с голосом. | |
| `handoff_explain_signed` | Навигатор получает весь день: старт, финиш и до 8 остановок между ними. Карты — запасной вариант. | |
| `handoff_maps_missing` | не установлены — откроем карту в браузере | |
| `handoff_navi_missing` | не установлен | |
| `handoff_install` | Установить из магазина приложений | opens the store page |
| `handoff_remember` | Запомнить выбор | then the Road button opens the chosen app directly; long-press it to choose again |
| `handoff_walk_cta` | Вести пешком в Яндекс Картах | 5.11 |
| `handoff_open_maps` | Открываем Яндекс Карты | toast (1 s) before leaving the app |
| `handoff_open_navi` | Открываем Яндекс Навигатор | |

### 16.6 Cards with little data (5.9 §9)

| Key | Text | Notes |
| --- | --- | --- |
| `card_why` | Почему здесь: {why} | engine `whyRu` |
| `card_desc_wikipedia` | Описание: Википедия · CC BY-SA | link to the article |
| `card_desc_wikivoyage` | Описание: Викигид · CC BY-SA | |
| `card_photo_nearby_label` | ФОТО РЯДОМ | label over a Commons geosearch photo |
| `card_photo_nearby_credit` | Фото рядом с местом · Wikimedia Commons · {author} · {licence} | |
| `card_illustration_none` | фото пока нет | small caption in the category illustration, **only** when the place has no text either |
| `hours_today_open` | сегодня {hours} · открыто | walks and cards |
| `hours_open_until` | открыто до {time} | timed walk row |
| `hours_closed` | сегодня закрыто | |
| `hours_closed_day` | сегодня закрыто · {weekday} | untimed walk |
| `hours_24` | круглосуточно | |
| `hours_unknown` | часы не указаны | |
| `card_dogs_no` | с собакой — нельзя | fact chip |
| `card_dogs_yes` | с собакой можно | |
| `card_parking_free` | P бесплатно у входа | fact chip |
| `card_parking_paid` | P ≈ {rate} ₽/ч | fact chip |
| `card_open_data` | часы и цены — из открытых данных, уточняйте | once, after the facts; only when a fact is open data |

### 16.7 «По городу» start and the walk (5.10 §10, 5.11 §10)

| Key | Text | Notes |
| --- | --- | --- |
| `city_start_label` | СТАРТ ПРОГУЛКИ | |
| `city_start_here` | {town} · вы здесь | second line of the start field |
| `cd_city_start` | Старт прогулки: {place}. Изменить | |
| `city_crew_label` | КТО ИДЁТ | |
| `city_crew_adults` | Взрослые | |
| `city_crew_kids` | Дети | |
| `city_crew_dog` | Собака | |
| `city_crew_dog_on` | с нами | |
| `city_crew_dog_off` | нет | |
| `city_type_label` | КАКАЯ ПРОГУЛКА | |
| `city_preset_dog` | Прогулка с собакой | first preset when the dog is on (ADR-0015 §6 `dog_walk`) |
| `city_preset_dog_sub` | парки, набережные, виды | |
| `city_duration_unlimited` | без ограничения | duration chip; `durationMin = null` |
| `city_duration_hint_timed` | Соберём расписание: когда куда прийти и когда финиш | |
| `city_duration_hint_untimed` | Без расписания: порядок мест по пути и часы работы каждого | |
| `city_prefs_label` | ПОЖЕЛАНИЯ И ОГРАНИЧЕНИЯ | |
| `city_pref_budget` | Бюджет на всех | |
| `city_pref_pace` | Темп | |
| `city_pref_return` | Вернуться к старту | |
| `city_caption_untimed` | {crew} · без расписания | caption meta |
| `age_gate_question` | Вам есть 18? | the whole dialog (CEO 3); `age_gate_title` / `age_gate_body` / `city_kids_*` are retired |
| `age_gate_yes_short` | Да | |
| `walk_warn_child_bars` | Ребёнку может быть некомфортно: в бары с детьми обычно не пускают. | engine `CHILD_BARS` |
| `walk_warn_dog_bars` | С собакой в бары обычно нельзя. Оставьте собаку дома или выберите прогулку с собакой. | engine `DOG_INDOOR`, drink presets |
| `walk_warn_dog_indoor` | С собакой в музеи и кафе обычно нельзя. Оставьте собаку дома или выберите прогулку с собакой. | other presets, before the walk is built (5.10) |
| `walk_warn_dog_count` | С собакой в музеи и бары обычно нельзя — таких мест на маршруте: {k} | on the result |
| `walk_action_dog_walk` | Прогулка с собакой | plate action |
| `walk_action_dog_home` | Собака останется дома | plate action: `dog = false`, rebuild |
| `walk_action_overview` | Обзорная прогулка вместо этой | plate action under `walk_warn_child_bars` |
| `walk_info_child` | С ребёнком: добавили детскую площадку и кафе с детским меню. | green info plate |
| `walk_info_child_museums` | С ребёнком: взяли интерактивные музеи и паузы каждые полтора часа. | |
| `walk_info_dog` | С собакой: парки, набережные, виды и площади — без закрытых помещений. | |
| `walk_stop_dog_no` | С собакой внутрь нельзя. | per indoor stop, end of its note |
| `walk_untimed_header` | Порядок по пути · заходите, куда открыто | replaces «Старт … · финиш …» |
| `walk_untimed_facts` | Без расписания · {places} по пути · ≈ {km} км | `{places}` = `plural_place` |
| `walk_filters_cd` | Условия прогулки | toolbar pane title |
| `walk_rebuilding` | Пересобираем прогулку… | over the dimmed previous walk |
| `walk_rebuild_failed` | Не получилось пересобрать — оставили прежний вариант | toast with `walk_rebuild_retry` |
| `walk_rebuild_retry` | Повторить | |
| `walk_other_none` | Других вариантов нет | disabled «Другой вариант» |
| `walk_other_none_note` | С этими условиями показали все варианты. Поменяйте время или прогулку выше. | |
| `walk_few_title` | Для {dur} рядом мало мест | `NOT_ENOUGH_POIS`; replaces `city_not_enough_*` |
| `walk_few_body` | Нашли {found} — это примерно {span}. Проверили, что сработает: | `{found}` = `plural_place` |
| `walk_few_duration` | Гулять {dur} | engine suggestion `durationMin` |
| `walk_few_duration_sub` | хватит на {found} | |
| `walk_few_unlimited` | Без ограничения | engine suggestion `durationMin: null` |
| `walk_few_unlimited_sub` | {found} без расписания | |
| `walk_few_preset` | {preset} вместо этой прогулки | engine suggestion `preset` |
| `walk_few_preset_sub` | {found} рядом | |
| `walk_few_clear` | Вернуть убранные места | engine suggestion `clearExclude` |
| `walk_few_clear_sub` | вы убрали {found} — вернём их в подбор | |

### 16.8 Online data states (5.5 §10.9)

| Key | Text | Notes |
| --- | --- | --- |
| `online_loading` | Загружаем данные о парковке… | sheet status while loading |
| `online_updated_now` | обновлено только что | |
| `online_updated_min` | обновлено {min} мин назад | |
| `online_updated_hours` | обновлено {h} ч назад | |
| `online_later` | уточним при интернете | deferred value (row P part, sheet cells) |
| `online_need_check` | требуется уточнить при наличии интернета | generic, for any other online-only value |
| `online_banner` | Нет сети — показываем сохранённое, остальное уточним при интернете | Road-ahead banner |
| `online_cached_note` | Показываем сохранённое. Обновим, когда появится интернет. | |
| `parking_live_status` | сейчас ≈ {k} мест · {rate} ₽/ч · обновлено только что | |
| `parking_row_free_now` | Свободно сейчас | sheet row key (live) |
| `parking_row_free_cached` | Свободно | sheet row key (cached) |
| `parking_free_now` | ≈ {k} мест | |
| `parking_free_cached` | было ≈ {k} · {min} мин назад | |
| `parking_live_note` | Свободные места меняются каждую минуту — к приезду их может не быть. Сумма уже в путевом листе и в бюджете. | |
| `parking_offline_status` | нет сети — уточним при интернете | |
| `parking_offline_note` | В путевом листе это место пока без суммы — добавим, когда появится интернет. Маршрут и остальное работают без сети. | |
| `parking_none_status` | нет данных о парковке | |
| `parking_none_note` | Открытые источники ничего не знают об этой парковке. В путевом листе — «без данных», в сумму не входит. | |
| `parking_loading_note` | Пока грузим, в путевом листе — сумма по справочнику тарифов. | |
| `cd_parking_loading` | Парковка: загружаем | |
| `cd_parking_live` | Парковка сейчас: примерно {k} свободных мест, {rate} рублей в час | |
