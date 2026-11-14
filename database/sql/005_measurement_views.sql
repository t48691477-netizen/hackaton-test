-- Convenience views for future API queries. They work with empty measurement
-- tables and do not fabricate rows.

CREATE OR REPLACE VIEW promscan.v_measurement_batch_status AS
SELECT
    b.id,
    b.dataset_code,
    b.provenance,
    b.import_status,
    b.source_row_count,
    count(m.id) AS loaded_measurement_count,
    count(DISTINCT m.channel_id) AS loaded_channel_count,
    min(m.measured_at) AS loaded_start,
    max(m.measured_at) AS loaded_end
FROM promscan.measurement_import_batches AS b
LEFT JOIN promscan.measurements AS m ON m.batch_id = b.id
GROUP BY
    b.id,
    b.dataset_code,
    b.provenance,
    b.import_status,
    b.source_row_count;

COMMENT ON VIEW promscan.v_measurement_batch_status IS
    'Import manifest with actual row counts; rejected demo batches show zero loaded rows';

CREATE OR REPLACE VIEW promscan.v_equipment_measurements AS
SELECT
    e.id AS equipment_id,
    e.name AS equipment_name,
    m.id AS measurement_id,
    m.batch_id,
    m.channel_id,
    c.name AS channel_name,
    c.modality,
    c.unit,
    sd.id AS sensor_id,
    sd.external_identifier,
    m.measured_at,
    m.numeric_value,
    m.quality_status
FROM promscan.measurements AS m
JOIN promscan.measurement_channels AS c ON c.id = m.channel_id
JOIN promscan.sensor_devices AS sd ON sd.id = m.sensor_id
JOIN promscan.equipment AS e ON e.id = sd.equipment_id;

COMMENT ON VIEW promscan.v_equipment_measurements IS
    'Measurements joined to a confirmed equipment and physical sensor';

CREATE OR REPLACE VIEW promscan.v_latest_equipment_measurement AS
SELECT DISTINCT ON (e.id, m.channel_id)
    e.id AS equipment_id,
    e.name AS equipment_name,
    m.channel_id,
    c.name AS channel_name,
    c.unit,
    sd.id AS sensor_id,
    m.measured_at,
    m.numeric_value,
    m.quality_status
FROM promscan.measurements AS m
JOIN promscan.measurement_channels AS c ON c.id = m.channel_id
JOIN promscan.sensor_devices AS sd ON sd.id = m.sensor_id
JOIN promscan.equipment AS e ON e.id = sd.equipment_id
WHERE m.quality_status <> 'invalid'
ORDER BY e.id, m.channel_id, m.measured_at DESC, m.id DESC;

COMMENT ON VIEW promscan.v_latest_equipment_measurement IS
    'Latest non-invalid reading per equipment and channel';
