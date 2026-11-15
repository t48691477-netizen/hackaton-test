-- Легаси-поля веб-приложения поверх существующего каталога оборудования.
-- Каталог оборудования в database/sql/001_schema.sql нормализован
-- (equipment/equipment_specs/equipment_nodes/node_specs), но основной API
-- app/ (legacy-контракт /api/equipment) использует плоскую карточку:
-- component_age, last_maintenance_date, status, components, inspection_count.
-- Эта миграция добавляет совместимую таблицу promscan.webapp_equipment в той
-- же базе каталога (DATABASE_URL), не трогая существующие таблицы.
-- Идемпотентна: повторный запуск безопасен.

BEGIN;

CREATE TABLE IF NOT EXISTS promscan.webapp_equipment (
    id                    text PRIMARY KEY,
    name                  text NOT NULL,
    serial_number         text,
    location              text,
    commissioned_at       date,
    component_age         text,
    last_maintenance_at   date,
    state                 text CHECK (state IN ('operational', 'maintenance', 'fault')),
    components_json       jsonb NOT NULL DEFAULT '[]'::jsonb
                            CHECK (jsonb_typeof(components_json) = 'array'),
    inspection_count      integer NOT NULL DEFAULT 0 CHECK (inspection_count >= 0),
    created_at            timestamptz NOT NULL DEFAULT now(),
    updated_at            timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS webapp_equipment_name_idx
    ON promscan.webapp_equipment (name);

-- Начальные записи (сид) отсутствуют намеренно: production-каталог
-- наполняется из утверждённого реестра или миграцией каталога.

COMMIT;
