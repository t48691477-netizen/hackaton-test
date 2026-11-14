-- Canonical Android QR catalog used by the demo and local production smoke test.
-- These records are the explicitly approved API catalog; they are not a silent
-- mapping of the four passport rows from the separate database branch.

INSERT INTO promscan.equipment (
    id, qr_id, name, manufacturer, model, category, location, state
)
VALUES
    ('eq-pump-402', 'PUMP-402', 'Насосный агрегат ЦНС 38-220', NULL,
     'ЦНС 38-220', 'pump', 'Цех №4 · Насосная станция, поз. 12', 'operational'),
    ('eq-pump-118', 'PUMP-118', 'Насос центробежный К-80', NULL,
     'К-80', 'pump', 'Цех №2 · Линия подачи реагента', 'operational'),
    ('eq-valve-77', 'VALVE-77', 'Задвижка клиновая DN200', NULL,
     'DN200', 'valve', 'Цех №4 · Узел №7', 'operational')
ON CONFLICT (id) DO UPDATE SET
    qr_id = EXCLUDED.qr_id,
    name = EXCLUDED.name,
    model = EXCLUDED.model,
    category = EXCLUDED.category,
    location = EXCLUDED.location,
    state = EXCLUDED.state,
    updated_at = now();

INSERT INTO promscan.equipment_aliases (alias, equipment_id, source)
VALUES
    ('PUMP-402', 'eq-pump-402', 'android_qr_catalog'),
    ('PUMP-118', 'eq-pump-118', 'android_qr_catalog'),
    ('VALVE-77', 'eq-valve-77', 'android_qr_catalog')
ON CONFLICT (alias) DO UPDATE SET
    equipment_id = EXCLUDED.equipment_id,
    source = EXCLUDED.source;

INSERT INTO promscan.equipment_nodes (
    id, equipment_id, public_id, name, description,
    offset_x, offset_y, offset_z, radius, sort_order
)
VALUES
    ('eq-pump-402:C1', 'eq-pump-402', 'C1', 'Корпус насоса', 'Основной корпус, чугун СЧ20', 0.00, 0.10, 0.00, 0.30, 10),
    ('eq-pump-402:C2', 'eq-pump-402', 'C2', 'Патрубок нагнетания', 'DN100, рабочее давление 1.6 МПа', 0.32, 0.36, 0.06, 0.22, 20),
    ('eq-pump-402:C3', 'eq-pump-402', 'C3', 'Фланец №3', 'Фланцевое соединение, 8 болтов М20', -0.28, 0.44, -0.04, 0.20, 30),
    ('eq-pump-402:C4', 'eq-pump-402', 'C4', 'Подшипниковый узел', 'Подшипник 3620, смазка Литол-24', 0.14, -0.02, 0.26, 0.24, 40),
    ('eq-pump-402:C5', 'eq-pump-402', 'C5', 'Электродвигатель', 'АИР160S4, 15 кВт', -0.40, 0.18, 0.44, 0.32, 50),
    ('eq-pump-402:C6', 'eq-pump-402', 'C6', 'Муфта', 'Упругая втулочно-пальцевая муфта', 0.06, 0.24, 0.40, 0.20, 60),
    ('eq-pump-118:C1', 'eq-pump-118', 'C1', 'Корпус', NULL, 0.00, 0.10, 0.00, 0.28, 10),
    ('eq-pump-118:C2', 'eq-pump-118', 'C2', 'Патрубок', NULL, 0.30, 0.30, 0.00, 0.20, 20),
    ('eq-pump-118:C3', 'eq-pump-118', 'C3', 'Опорная рама', NULL, -0.25, -0.05, 0.20, 0.24, 30),
    ('eq-valve-77:C1', 'eq-valve-77', 'C1', 'Корпус задвижки', NULL, 0.00, 0.05, 0.00, 0.26, 10),
    ('eq-valve-77:C2', 'eq-valve-77', 'C2', 'Шпиндель', NULL, 0.00, 0.35, 0.00, 0.18, 20),
    ('eq-valve-77:C3', 'eq-valve-77', 'C3', 'Фланцы', NULL, 0.28, 0.10, 0.00, 0.20, 30)
ON CONFLICT (id) DO UPDATE SET
    equipment_id = EXCLUDED.equipment_id,
    public_id = EXCLUDED.public_id,
    name = EXCLUDED.name,
    description = EXCLUDED.description,
    offset_x = EXCLUDED.offset_x,
    offset_y = EXCLUDED.offset_y,
    offset_z = EXCLUDED.offset_z,
    radius = EXCLUDED.radius,
    sort_order = EXCLUDED.sort_order,
    updated_at = now();
