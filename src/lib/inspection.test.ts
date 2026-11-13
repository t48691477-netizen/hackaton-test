import { describe, expect, it } from 'vitest';
import {
  MOCK_DEFECT_ROWS,
  MOCK_EQUIPMENT,
  MOCK_EQUIPMENT_LIST,
  MOCK_REPORTS,
  createMockInspection,
  getEquipmentNode,
} from './inspection';

describe('mock-слой inspection', () => {
  it('держит bbox и polygon в нормализованных координатах', () => {
    const result = createMockInspection(1);

    expect(result.defects).toHaveLength(3);

    for (const defect of result.defects) {
      const [x1, y1, x2, y2] = defect.bbox;

      expect(x1).toBeGreaterThanOrEqual(0);
      expect(y1).toBeGreaterThanOrEqual(0);
      expect(x2).toBeLessThanOrEqual(1);
      expect(y2).toBeLessThanOrEqual(1);
      expect(x1).toBeLessThan(x2);
      expect(y1).toBeLessThan(y2);

      for (const [x, y] of defect.polygon ?? []) {
        expect(x).toBeGreaterThanOrEqual(0);
        expect(x).toBeLessThanOrEqual(1);
        expect(y).toBeGreaterThanOrEqual(0);
        expect(y).toBeLessThanOrEqual(1);
      }
    }
  });

  it('связывает каждый дефект с существующим узлом и specs', () => {
    const result = createMockInspection(2);

    for (const defect of result.defects) {
      const node = getEquipmentNode(result.equipment, defect.node_id);

      expect(node).not.toBeNull();
      expect(node?.specs.length).toBeGreaterThan(0);
    }
  });

  it('возвращает характеристики оборудования и узлов', () => {
    expect(MOCK_EQUIPMENT.specs.length).toBeGreaterThan(0);
    expect(MOCK_EQUIPMENT.nodes.length).toBeGreaterThan(0);
    expect(MOCK_EQUIPMENT.nodes[0].specs.length).toBeGreaterThan(0);
  });

  it('связывает отчёты с паспортами оборудования из каталога', () => {
    for (const report of MOCK_REPORTS) {
      const equipment = MOCK_EQUIPMENT_LIST.find((item) => item.id === report.equipment_id);

      expect(equipment).toBeDefined();
      expect(report.result.equipment).toEqual(equipment);
      expect(report.result.inspection_id).toBe(report.inspection_id);
      expect(report.result.defects.every((defect) =>
        getEquipmentNode(report.result.equipment, defect.node_id) !== null,
      )).toBe(true);
    }
  });

  it('использует API-статусы в отчётах и таблице дефектов', () => {
    const statuses = new Set(['open', 'in_progress', 'closed']);
    const severities = new Set(['low', 'medium', 'high']);

    for (const report of MOCK_REPORTS) {
      expect(statuses.has(report.status)).toBe(true);
      expect(severities.has(report.result.llm.criticality)).toBe(true);
    }

    for (const row of MOCK_DEFECT_ROWS) {
      expect(statuses.has(row.status)).toBe(true);
      expect(severities.has(row.severity)).toBe(true);
    }
  });
});
