-- Transcribed from the four scanned pump passports in the shared Yandex Disk folder.
-- The four passports show the same model and technical table; serial numbers differ.
-- No commissioning date, inventory number, location, condition, or maintenance event
-- is inferred from blank fields in the passports.

INSERT INTO promscan.equipment (
    id, name, manufacturer, model, serial_number, inventory_number,
    category, location, state, commissioned_at, service_life_years
)
VALUES
    ('pump-ams-pcp60s12-3-01-1', 'Насос AMS PCP60S12/3 №1', 'ООО «Альтернативные Механические Системы»', 'AMS PCP60S12/3 01 Ex B1 HNBR DTS', '21031004-1', NULL, 'Насосное оборудование', NULL, NULL, NULL, NULL),
    ('pump-ams-pcp60s12-3-01-2', 'Насос AMS PCP60S12/3 №2', 'ООО «Альтернативные Механические Системы»', 'AMS PCP60S12/3 01 Ex B1 HNBR DTS', '21031004-2', NULL, 'Насосное оборудование', NULL, NULL, NULL, NULL),
    ('pump-ams-pcp60s12-3-01-3', 'Насос AMS PCP60S12/3 №3', 'ООО «Альтернативные Механические Системы»', 'AMS PCP60S12/3 01 Ex B1 HNBR DTS', '21031004-3', NULL, 'Насосное оборудование', NULL, NULL, NULL, NULL),
    ('pump-ams-pcp60s12-3-01-4', 'Насос AMS PCP60S12/3 №4', 'ООО «Альтернативные Механические Системы»', 'AMS PCP60S12/3 01 Ex B1 HNBR DTS', '21031004-4', NULL, 'Насосное оборудование', NULL, NULL, NULL, NULL)
ON CONFLICT (id) DO UPDATE SET
    name = EXCLUDED.name,
    manufacturer = EXCLUDED.manufacturer,
    model = EXCLUDED.model,
    serial_number = EXCLUDED.serial_number,
    category = EXCLUDED.category,
    updated_at = now();

INSERT INTO promscan.equipment_specs (equipment_id, label, value, unit, sort_order)
SELECT e.id, s.label, s.value, s.unit, s.sort_order
FROM promscan.equipment AS e
CROSS JOIN (VALUES
    ('Подача', '5–20', 'м³/ч', 10),
    ('Давление', 'до 10', 'бар', 20),
    ('Допускаемый кавитационный запас NPSHr', '2', 'м', 30),
    ('Температура продукта', '+5…+45', '°C', 40),
    ('Максимальная температура продукта при промывке и выключенном насосе', '+90', '°C', 50),
    ('Максимальная плотность', '1600', 'кг/м³', 60),
    ('Концентрация твёрдой фазы', 'до 5', '%', 70),
    ('Габариты (длина × ширина × высота)', '2742 × 360 × 605', 'мм', 80),
    ('Масса', '430', 'кг', 90),
    ('Нормативный документ', 'ТУ 3631-001-23430200-2015', NULL, 100),
    ('Реверсивная работа агрегата', 'Да', NULL, 110),
    ('Защитный кожух', 'Да', NULL, 120)
) AS s(label, value, unit, sort_order)
WHERE e.model = 'AMS PCP60S12/3 01 Ex B1 HNBR DTS'
ON CONFLICT (equipment_id, label) DO UPDATE SET
    value = EXCLUDED.value,
    unit = EXCLUDED.unit,
    sort_order = EXCLUDED.sort_order;

INSERT INTO promscan.equipment_nodes (id, equipment_id, name, sort_order)
SELECT e.id || '-' || n.suffix, e.id, n.name, n.sort_order
FROM promscan.equipment AS e
CROSS JOIN (VALUES
    ('rotor', 'Ротор', 10),
    ('stator', 'Статор', 20),
    ('seal', 'Уплотнение', 30),
    ('housing', 'Корпус', 40),
    ('motor', 'Электродвигатель', 50),
    ('reducer', 'Редуктор', 60)
) AS n(suffix, name, sort_order)
WHERE e.model = 'AMS PCP60S12/3 01 Ex B1 HNBR DTS'
ON CONFLICT (id) DO UPDATE SET
    name = EXCLUDED.name,
    sort_order = EXCLUDED.sort_order;

INSERT INTO promscan.node_specs (node_id, label, value, unit, sort_order)
SELECT n.id, s.label, s.value, s.unit, s.sort_order
FROM promscan.equipment_nodes AS n
JOIN promscan.equipment AS e ON e.id = n.equipment_id
JOIN (VALUES
    ('rotor', 'Материал', 'Коррозионностойкая сталь 40Х13, закалка 50 HRC', NULL, 10),
    ('stator', 'Материал', 'Износостойкий эластомер HNBR', NULL, 10),
    ('seal', 'Тип', 'Одинарное торцевое', NULL, 10),
    ('seal', 'Материалы пары трения', 'Карбид вольфрама / карбид кремния', NULL, 20),
    ('housing', 'Материал', 'Сталь 20 с защитным покрытием', NULL, 10),
    ('motor', 'Мощность', '11', 'кВт', 10),
    ('motor', 'Подключение', '380 В, 50 Гц', NULL, 20),
    ('motor', 'Степень защиты / взрывозащита', 'IP55 / ExdIIBT4Gb', NULL, 30),
    ('motor', 'Опция', 'РТС терморезисторы', NULL, 40),
    ('reducer', 'Частота вращения', '260', 'об/мин', 10),
    ('reducer', 'Передаточное отношение', '5,3', NULL, 20)
) AS s(suffix, label, value, unit, sort_order)
    ON n.id = e.id || '-' || s.suffix
WHERE e.model = 'AMS PCP60S12/3 01 Ex B1 HNBR DTS'
ON CONFLICT (node_id, label) DO UPDATE SET
    value = EXCLUDED.value,
    unit = EXCLUDED.unit,
    sort_order = EXCLUDED.sort_order;

INSERT INTO promscan.equipment_documents (
    equipment_id, document_type, file_name, source_provider, source_path, mime_type
)
VALUES
    ('pump-ams-pcp60s12-3-01-1', 'passport', '1) Насос №1 ПС.pdf', 'yandex_disk', '/Документация/Паспорта Насосов/1) Насос №1 ПС.pdf', 'application/pdf'),
    ('pump-ams-pcp60s12-3-01-2', 'passport', '1) Насос №2 ПС.pdf', 'yandex_disk', '/Документация/Паспорта Насосов/1) Насос №2 ПС.pdf', 'application/pdf'),
    ('pump-ams-pcp60s12-3-01-3', 'passport', '1) Насос №3 ПС.pdf', 'yandex_disk', '/Документация/Паспорта Насосов/1) Насос №3 ПС.pdf', 'application/pdf'),
    ('pump-ams-pcp60s12-3-01-4', 'passport', '1) Насос №4 ПС.pdf', 'yandex_disk', '/Документация/Паспорта Насосов/1) Насос №4 ПС.pdf', 'application/pdf')
ON CONFLICT (equipment_id, document_type, source_path) DO UPDATE SET
    file_name = EXCLUDED.file_name,
    mime_type = EXCLUDED.mime_type;
