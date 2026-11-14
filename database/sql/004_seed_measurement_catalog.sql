-- Catalog measurement quantities, source batches, and threshold descriptions found on Yandex Disk.
-- The two demo spreadsheets are registered as rejected sources: their synthetic rows
-- are intentionally not inserted into promscan.measurements or measurement_diagnoses.

INSERT INTO promscan.measurement_channels (
    id, name, modality, unit, measurement_location, description, sort_order
)
VALUES
    ('shaft_speed_rpm', 'Обороты', 'speed', 'об/мин', 'Вал агрегата; точка установки датчика не указана', 'Частота вращения из таблиц термометрии и вибрации.', 10),
    ('vibration_overall_rms', 'СКЗ общее', 'vibration', 'мм/с', 'Точка измерения на насосном агрегате не указана', 'Общий уровень виброскорости; описание ссылается на ГОСТ/ISO 10816.', 20),
    ('vibration_amplitude_1x', 'Амплитуда 1x', 'vibration', 'мм/с', 'Точка измерения на насосном агрегате не указана', 'Амплитуда вибрации на частоте вращения.', 30),
    ('vibration_amplitude_2x', 'Амплитуда 2x', 'vibration', 'мм/с', 'Точка измерения на насосном агрегате не указана', 'Амплитуда вибрации на удвоенной частоте вращения.', 40),
    ('vibration_hf_noise', 'ВЧ шум', 'vibration', 'g', 'Подшипниковый узел или гидравлическая часть; точка датчика не указана', 'Высокочастотное ускорение; в описании названо возможным маркером износа подшипника или кавитационного шума.', 50),
    ('pump_bearing_temperature', 'Температура подшипника насоса', 'temperature', '°C', 'Корпус подшипникового узла гидравлической части', 'В описании источника указан термодатчик в корпусе подшипникового узла.', 60),
    ('motor_winding_temperature', 'Температура обмоток электродвигателя', 'temperature', '°C', 'Статор электродвигателя', 'В описании источника указаны термодатчики PT100/PT1000.', 70)
ON CONFLICT (id) DO UPDATE SET
    name = EXCLUDED.name,
    modality = EXCLUDED.modality,
    unit = EXCLUDED.unit,
    measurement_location = EXCLUDED.measurement_location,
    description = EXCLUDED.description,
    sort_order = EXCLUDED.sort_order;

INSERT INTO promscan.measurement_import_batches (
    id, dataset_code, source_provider, source_path, source_file, source_format,
    provenance, import_status, source_row_count, recorded_timezone,
    observed_start, observed_end, equipment_id, source_description
)
VALUES
    (
        'demo-vibration-2026-11', 'vibration', 'yandex_disk',
        '/Вибрация/БД значений (вибрация).xlsx', 'БД значений (вибрация).xlsx',
        'xlsx', 'synthetic_demo', 'rejected', 500, NULL,
        timestamp '2026-11-10 08:00:00', timestamp '2026-12-01 03:00:00', NULL,
        'Синтетический демонстрационный набор, 500 часовых строк. Отклонён: даты в будущем и отсутствуют ID оборудования/датчиков. Строки не загружены.'
    ),
    (
        'demo-temperature-2026-11', 'temperature', 'yandex_disk',
        '/Температура/БД значений (температура).xlsx', 'БД значений (температура).xlsx',
        'xlsx', 'synthetic_demo', 'rejected', 500, NULL,
        timestamp '2026-11-10 08:00:00', timestamp '2026-12-01 03:00:00', NULL,
        'Синтетический демонстрационный набор, 500 часовых строк. Отклонён: даты в будущем и отсутствуют ID оборудования/датчиков. Строки не загружены.'
    )
ON CONFLICT (id) DO UPDATE SET
    dataset_code = EXCLUDED.dataset_code,
    source_file = EXCLUDED.source_file,
    provenance = EXCLUDED.provenance,
    import_status = EXCLUDED.import_status,
    source_row_count = EXCLUDED.source_row_count,
    observed_start = EXCLUDED.observed_start,
    observed_end = EXCLUDED.observed_end,
    equipment_id = EXCLUDED.equipment_id,
    source_description = EXCLUDED.source_description;

INSERT INTO promscan.measurement_thresholds (
    channel_id, level, comparison, threshold_value, source_document, notes
)
VALUES
    ('vibration_amplitude_1x', 'warning', 'gt', 2.8, '/Вибрация/Описание БД (вибрация).docx', 'Предупреждение при превышении 2.8 мм/с.'),
    ('vibration_amplitude_1x', 'critical', 'gt', 4.5, '/Вибрация/Описание БД (вибрация).docx', 'Тревога при превышении 4.5 мм/с.'),
    ('vibration_amplitude_2x', 'warning', 'gt', 1.8, '/Вибрация/Описание БД (вибрация).docx', 'Предупреждение при превышении 1.8 мм/с.'),
    ('vibration_amplitude_2x', 'critical', 'gt', 3.0, '/Вибрация/Описание БД (вибрация).docx', 'Тревога при превышении 3.0 мм/с.'),
    ('vibration_hf_noise', 'warning', 'gt', 2.5, '/Вибрация/Описание БД (вибрация).docx', 'Описание упоминает фиксацию износа подшипника или кавитационного шума выше 2.5 g; отдельный критический порог не задан.'),
    ('pump_bearing_temperature', 'warning', 'gt', 75, '/Температура/Описание БД (температура).docx', 'Предупреждение при температуре выше 75 °C.'),
    ('pump_bearing_temperature', 'critical', 'gt', 90, '/Температура/Описание БД (температура).docx', 'Тревога при температуре выше 90 °C.'),
    ('motor_winding_temperature', 'warning', 'gt', 90, '/Температура/Описание БД (температура).docx', 'Предупреждение при температуре выше 90 °C.'),
    ('motor_winding_temperature', 'critical', 'gt', 110, '/Температура/Описание БД (температура).docx', 'Тревога при температуре выше 110 °C.')
ON CONFLICT (channel_id, level, source_document) DO UPDATE SET
    comparison = EXCLUDED.comparison,
    threshold_value = EXCLUDED.threshold_value,
    notes = EXCLUDED.notes;
