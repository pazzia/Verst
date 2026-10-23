-- Seed: the 16 regions of the Sprint-1 fixture world (DEV-021). Geometries are NULL until INF-001 imports
-- OSM admin_level=4 boundaries ('RU' is the national price fallback and keeps a NULL geometry).
-- Written, not executed in Sprint 1 (execution against PostGIS is DEV-B02).
INSERT INTO core.region (code, name_ru, tz, geom) VALUES
  ('RU', 'Россия', 'Europe/Moscow', NULL),
  ('RU-MOW', 'Москва', 'Europe/Moscow', NULL),
  ('RU-MOS', 'Московская область', 'Europe/Moscow', NULL),
  ('RU-YAR', 'Ярославская область', 'Europe/Moscow', NULL),
  ('RU-KOS', 'Костромская область', 'Europe/Moscow', NULL),
  ('RU-IVA', 'Ивановская область', 'Europe/Moscow', NULL),
  ('RU-VLA', 'Владимирская область', 'Europe/Moscow', NULL),
  ('RU-NIZ', 'Нижегородская область', 'Europe/Moscow', NULL),
  ('RU-CU', 'Чувашская Республика', 'Europe/Moscow', NULL),
  ('RU-TA', 'Республика Татарстан', 'Europe/Moscow', NULL),
  ('RU-TUL', 'Тульская область', 'Europe/Moscow', NULL),
  ('RU-RYA', 'Рязанская область', 'Europe/Moscow', NULL),
  ('RU-LIP', 'Липецкая область', 'Europe/Moscow', NULL),
  ('RU-TAM', 'Тамбовская область', 'Europe/Moscow', NULL),
  ('RU-VOR', 'Воронежская область', 'Europe/Moscow', NULL),
  ('RU-VGG', 'Волгоградская область', 'Europe/Volgograd', NULL)
ON CONFLICT (code) DO UPDATE SET name_ru = EXCLUDED.name_ru, tz = EXCLUDED.tz;
