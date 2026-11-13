/**
 * ЕДИНЫЙ СЛОЙ ЗАГЛУШЕК.
 *
 * Здесь лежат типы и демо-данные, которые при интеграции заменяются ответами
 * backend. Контракт: docs/API_CONTRACT.md. Никакой UI-код не должен содержать
 * собственные копии этих данных.
 *
 * Замена:
 *   MOCK_EQUIPMENT / MOCK_REPORTS → GET /api/equipment, GET /api/reports
 *   MOCK_EMPLOYEES               → будущий справочник сотрудников
 *   createMockInspection()        → POST /api/inspect
 *   Report.assignee/status        → снимок исполнителя и статус задачи
 *   Defect.specs / EquipmentNode.specs → поля из EquipmentDetail / Defect
 */

import { MOCK_EMPLOYEES, toEmployeeRef, type EmployeeRef } from './employees';

export type Severity = 'low' | 'medium' | 'high';
export type ReportStatus = 'open' | 'in_progress' | 'closed';
export type EquipmentState = 'operational' | 'maintenance' | 'fault';
export type VisionMode = 'mock' | 'real';
export type LlmMode = 'mock' | 'real';

export interface SpecItem {
  label: string;
  value: string;
  unit: string | null;
}

export interface EquipmentNode {
  id: string;
  name: string;
  specs: SpecItem[];
}

export interface EquipmentSummary {
  id: string;
  name: string;
  inventory_number: string;
  category: string;
  location: string;
  state: EquipmentState;
}

export interface EquipmentDetail extends EquipmentSummary {
  manufacturer: string;
  model: string;
  commissioned_at: string;
  service_life_years: number;
  last_maintenance_at: string;
  next_maintenance_at: string;
  specs: SpecItem[];
  nodes: EquipmentNode[];
  created_at: string;
  updated_at: string;
}

/** bbox: [x_min, y_min, x_max, y_max], нормализовано 0..1 */
export type BoundingBox = [number, number, number, number];
/** polygon: [[x, y], ...], нормализовано 0..1 */
export type Polygon = Array<[number, number]>;

export interface Defect {
  id: string;
  label: string;
  confidence: number;
  severity: Severity;
  bbox: BoundingBox;
  polygon: Polygon | null;
  node_id: string | null;
  source_model: 'corrosion' | 'crack';
  recommendation: string;
}

export interface LlmAssessment {
  criticality: Severity;
  probable_cause: string;
  recommendation_steps: string[];
}

export interface InspectionMeta {
  vision_mode: VisionMode;
  llm_mode: LlmMode;
  models: {
    corrosion: string;
    crack: string;
  };
  processing_ms: number;
  analyzed_at: string;
}

export interface InspectionResult {
  inspection_id: string;
  equipment: EquipmentDetail;
  defects: Defect[];
  llm: LlmAssessment;
  summary: string;
  meta: InspectionMeta;
}

/**
 * Отчёт — это и акт осмотра, и задача на восстановление.
 *
 * Статусы: open (назначена) → in_progress (в работе) → closed (выполнена).
 * Исполнитель — снимок EmployeeRef без пароля/email. В real-режиме backend
 * проверяет, что переход делает назначенный сотрудник.
 */
export interface Report {
  id: string;
  equipment_id: string;
  inspection_id: string;
  status: ReportStatus;
  comment: string;
  photo_url: string | null;
  result: InspectionResult;
  assignee: EmployeeRef | null;
  started_at: string | null;
  completed_at: string | null;
  repair_comment: string | null;
  created_at: string;
  updated_at: string;
}

export const MOCK_EQUIPMENT: EquipmentDetail = {
  id: 'pump-cns-38-220',
  name: 'Насосный агрегат ЦНС 38-220',
  inventory_number: 'INV-2048-17',
  category: 'Насосное оборудование',
  location: 'Цех №3 · линия перекачки',
  state: 'operational',
  manufacturer: 'ПромМаш',
  model: 'ЦНС 38-220',
  commissioned_at: '2019-06-01',
  service_life_years: 10,
  last_maintenance_at: '2026-04-18',
  next_maintenance_at: '2026-10-18',
  specs: [
    { label: 'Подача', value: '38', unit: 'м³/ч' },
    { label: 'Напор', value: '220', unit: 'м' },
    { label: 'Мощность', value: '38', unit: 'кВт' },
    { label: 'Частота вращения', value: '3000', unit: 'об/мин' },
    { label: 'Масса', value: '420', unit: 'кг' },
    { label: 'Материал корпуса', value: 'Чугун СЧ20', unit: null },
  ],
  nodes: [
    {
      id: 'node-housing',
      name: 'Корпус насоса',
      specs: [
        { label: 'Материал', value: 'Чугун СЧ20', unit: null },
        { label: 'Толщина стенки', value: '12', unit: 'мм' },
        { label: 'Макс. давление', value: '2.5', unit: 'МПа' },
        { label: 'Ресурс', value: '60 000', unit: 'ч' },
      ],
    },
    {
      id: 'node-bearing',
      name: 'Подшипниковый узел',
      specs: [
        { label: 'Тип', value: 'SKF 6310', unit: null },
        { label: 'Ресурс', value: '12 000', unit: 'ч' },
        { label: 'Смазка', value: 'Литол-24', unit: null },
        { label: 'Температура', value: 'до 80', unit: '°C' },
      ],
    },
    {
      id: 'node-mount',
      name: 'Крепление к раме',
      specs: [
        { label: 'Болты', value: 'М16 × 4', unit: 'шт' },
        { label: 'Момент затяжки', value: '120', unit: 'Н·м' },
        { label: 'Материал', value: 'Сталь 40Х', unit: null },
        { label: 'Антикоррозийное покрытие', value: 'Цинк', unit: null },
      ],
    },
    {
      id: 'node-seal',
      name: 'Уплотнение вала',
      specs: [
        { label: 'Тип', value: 'Торцевое', unit: null },
        { label: 'Ресурс', value: '8 000', unit: 'ч' },
        { label: 'Допустимая утечка', value: '0.05', unit: 'л/ч' },
        { label: 'Материал', value: 'Карбид кремния', unit: null },
      ],
    },
  ],
  created_at: '2026-01-01T00:00:00Z',
  updated_at: '2026-11-13T18:30:00Z',
};

/** Демо-каталог для GET /api/equipment и связанных с ним отчётов. */
export const MOCK_EQUIPMENT_LIST: EquipmentDetail[] = [
  MOCK_EQUIPMENT,
  {
    ...MOCK_EQUIPMENT,
    id: 'compressor-k-500',
    name: 'Компрессор К-500',
    inventory_number: 'INV-2048-18',
    category: 'Компрессорное оборудование',
    location: 'Цех №1',
    state: 'maintenance',
    model: 'К-500',
    specs: [{ label: 'Мощность', value: '500', unit: 'кВт' }],
    nodes: [MOCK_EQUIPMENT.nodes[2]],
  },
  {
    ...MOCK_EQUIPMENT,
    id: 'pump-n-12',
    name: 'Насосный агрегат Н-12',
    inventory_number: 'INV-2048-19',
    location: 'Цех №3',
    model: 'Н-12',
    specs: [{ label: 'Подача', value: '12', unit: 'м³/ч' }],
    nodes: [MOCK_EQUIPMENT.nodes[3]],
  },
  {
    ...MOCK_EQUIPMENT,
    id: 'fan-vc-14',
    name: 'Вентилятор ВЦ-14',
    inventory_number: 'INV-2048-20',
    category: 'Вентиляционное оборудование',
    location: 'Цех №2',
    state: 'fault',
    model: 'ВЦ-14',
    specs: [{ label: 'Частота вращения', value: '1500', unit: 'об/мин' }],
    nodes: [{ ...MOCK_EQUIPMENT.nodes[0], name: 'Корпус вентилятора' }],
  },
  {
    ...MOCK_EQUIPMENT,
    id: 'motor-air-160',
    name: 'Электродвигатель АИР-160',
    inventory_number: 'INV-2048-21',
    category: 'Электродвигатели',
    location: 'Цех №1',
    model: 'АИР-160',
    specs: [{ label: 'Мощность', value: '15', unit: 'кВт' }],
    nodes: [MOCK_EQUIPMENT.nodes[2]],
  },
];

const BASE_DEFECTS: Defect[] = [
  {
    id: 'defect-crack',
    label: 'Трещина корпуса',
    confidence: 0.94,
    severity: 'high',
    bbox: [0.16, 0.24, 0.5, 0.54],
    polygon: [
      [0.16, 0.3],
      [0.28, 0.24],
      [0.5, 0.3],
      [0.47, 0.54],
      [0.24, 0.51],
    ],
    node_id: 'node-housing',
    source_model: 'crack',
    recommendation:
      'Остановить агрегат, провести ультразвуковой контроль и согласовать ремонт корпуса с главным инженером.',
  },
  {
    id: 'defect-mount',
    label: 'Износ крепления',
    confidence: 0.78,
    severity: 'medium',
    bbox: [0.58, 0.52, 0.82, 0.74],
    polygon: [
      [0.58, 0.55],
      [0.72, 0.52],
      [0.82, 0.7],
      [0.66, 0.74],
    ],
    node_id: 'node-mount',
    source_model: 'corrosion',
    recommendation:
      'Проверить момент затяжки и заменить крепёжные болты в ближайшее технологическое окно.',
  },
  {
    id: 'defect-oil',
    label: 'Масляный след',
    confidence: 0.61,
    severity: 'low',
    bbox: [0.36, 0.68, 0.54, 0.82],
    polygon: [
      [0.36, 0.72],
      [0.5, 0.68],
      [0.54, 0.78],
      [0.4, 0.82],
    ],
    node_id: 'node-seal',
    source_model: 'corrosion',
    recommendation:
      'Осмотреть уплотнение вала и устранить подтекание до образования лужи под оборудованием.',
  },
];

const clamp = (value: number, min = 0.02, max = 0.98) =>
  Math.min(max, Math.max(min, value));

/**
 * Демо-инференс: слегка «дышит» от кадра к кадру, чтобы live-режим выглядел
 * живым. При интеграции заменяется на POST /api/inspect.
 */
export function createMockInspection(
  tick = 0,
  equipment: EquipmentDetail = MOCK_EQUIPMENT,
): InspectionResult {
  const wave = Math.sin(tick * 1.7);
  const drift = Math.cos(tick * 1.1) * 0.008;

  const defects = BASE_DEFECTS.map((defect, index) => {
    const confidence = clamp(
      defect.confidence + wave * 0.012 + index * 0.001,
      0.5,
      0.99,
    );
    const [x1, y1, x2, y2] = defect.bbox;
    const bbox: BoundingBox = [
      clamp(x1 + drift),
      clamp(y1 - drift),
      clamp(x2 + drift),
      clamp(y2 - drift),
    ];

    return {
      ...defect,
      confidence,
      bbox,
      polygon: defect.polygon?.map(
        ([x, y]) => [clamp(x + drift), clamp(y - drift)] as [number, number],
      ) ?? null,
      node_id: equipment.nodes.some((node) => node.id === defect.node_id)
        ? defect.node_id
        : null,
    };
  });

  return {
    inspection_id: `insp-demo-${String(tick).padStart(4, '0')}`,
    equipment,
    defects,
    llm: {
      criticality: 'high',
      probable_cause:
        'Усталостная трещина из-за вибрации и превышения межремонтного ресурса корпуса.',
      recommendation_steps: [
        'Остановить агрегат и исключить работу под нагрузкой.',
        'Провести ультразвуковой контроль корпуса.',
        'Согласовать ремонт с главным инженером.',
      ],
    },
    summary:
      'Обнаружены три зоны риска: критическая трещина корпуса и износ крепёжных элементов. Рекомендуется внеплановая проверка перед следующей сменой.',
    meta: {
      vision_mode: 'mock',
      llm_mode: 'mock',
      models: {
        corrosion: 'Decizez/yolov-corrosion-detection',
        crack: 'avinashhm/welding-defect-yolov8-full-training',
      },
      processing_ms: 34 + Math.round(Math.abs(wave) * 18),
      analyzed_at: new Date().toISOString(),
    },
  };
}

export function getEquipmentNode(
  equipment: EquipmentDetail,
  nodeId: string | null,
): EquipmentNode | null {
  if (!nodeId) {
    return null;
  }

  return equipment.nodes.find((node) => node.id === nodeId) ?? null;
}

function createMockReportResult(
  tick: number,
  equipment: EquipmentDetail,
  defectIndex: number,
  analyzedAt: string,
): InspectionResult {
  const result = createMockInspection(tick, equipment);
  const defect = result.defects[defectIndex];

  return {
    ...result,
    defects: [defect],
    llm: {
      criticality: defect.severity,
      probable_cause: 'Демо-оценка: требуется осмотр оборудования специалистом.',
      recommendation_steps: [defect.recommendation],
    },
    summary: `${defect.label}. ${defect.recommendation}`,
    meta: { ...result.meta, analyzed_at: analyzedAt },
  };
}

const ASSIGNEE_ANNA = toEmployeeRef(MOCK_EMPLOYEES[1]);
const ASSIGNEE_ALEXEY = toEmployeeRef(MOCK_EMPLOYEES[2]);

/** Заглушка для GET /api/reports. Идентификаторы и паспорта согласованы с каталогом. */
export const MOCK_REPORTS: Report[] = [
  {
    id: 'report-1042',
    equipment_id: MOCK_EQUIPMENT.id,
    inspection_id: 'insp-demo-0001',
    status: 'in_progress',
    comment: 'Требуется внеплановая проверка корпуса.',
    photo_url: null,
    result: createMockReportResult(1, MOCK_EQUIPMENT_LIST[0], 0, '2026-11-13T14:12:00Z'),
    assignee: ASSIGNEE_ALEXEY,
    started_at: '2026-11-13T14:20:00Z',
    completed_at: null,
    repair_comment: null,
    created_at: '2026-11-13T14:12:00Z',
    updated_at: '2026-11-13T14:20:00Z',
  },
  {
    id: 'report-1041',
    equipment_id: 'compressor-k-500',
    inspection_id: 'insp-demo-0002',
    status: 'open',
    comment: 'Износ крепления компрессора.',
    photo_url: null,
    result: createMockReportResult(2, MOCK_EQUIPMENT_LIST[1], 1, '2026-11-13T13:48:00Z'),
    assignee: ASSIGNEE_ANNA,
    started_at: null,
    completed_at: null,
    repair_comment: null,
    created_at: '2026-11-13T13:48:00Z',
    updated_at: '2026-11-13T13:48:00Z',
  },
  {
    id: 'report-1039',
    equipment_id: 'pump-n-12',
    inspection_id: 'insp-demo-0003',
    status: 'open',
    comment: 'Масляный след под валом.',
    photo_url: null,
    result: createMockReportResult(3, MOCK_EQUIPMENT_LIST[2], 2, '2026-11-13T12:05:00Z'),
    assignee: null,
    started_at: null,
    completed_at: null,
    repair_comment: null,
    created_at: '2026-11-13T12:05:00Z',
    updated_at: '2026-11-13T12:05:00Z',
  },
  {
    id: 'report-1038',
    equipment_id: 'fan-vc-14',
    inspection_id: 'insp-demo-0004',
    status: 'open',
    comment: 'Трещина корпуса вентилятора.',
    photo_url: null,
    result: createMockReportResult(4, MOCK_EQUIPMENT_LIST[3], 0, '2026-11-13T11:32:00Z'),
    assignee: ASSIGNEE_ALEXEY,
    started_at: null,
    completed_at: null,
    repair_comment: null,
    created_at: '2026-11-13T11:32:00Z',
    updated_at: '2026-11-13T11:32:00Z',
  },
  {
    id: 'report-1036',
    equipment_id: 'motor-air-160',
    inspection_id: 'insp-demo-0005',
    status: 'closed',
    comment: 'Крепление восстановлено.',
    photo_url: null,
    result: createMockReportResult(5, MOCK_EQUIPMENT_LIST[4], 1, '2026-11-13T10:17:00Z'),
    assignee: ASSIGNEE_ALEXEY,
    started_at: '2026-11-13T10:30:00Z',
    completed_at: '2026-11-13T12:40:00Z',
    repair_comment: 'Крепление восстановлено, момент затяжки проверен.',
    created_at: '2026-11-13T10:17:00Z',
    updated_at: '2026-11-13T12:40:00Z',
  },
];

/**
 * Совместимый производный формат старой демо-таблицы.
 * UI получает Report[] через API-клиент, а не использует эту заглушку напрямую.
 */
export interface DefectRow {
  id: string;
  title: string;
  equipment: string;
  area: string;
  severity: Severity;
  status: ReportStatus;
  assignee: string;
  time: string;
}

export const MOCK_DEFECT_ROWS: DefectRow[] = MOCK_REPORTS.map((report) => ({
  id: report.id,
  title: report.result.defects[0]?.label ?? report.result.summary,
  equipment: report.result.equipment.name,
  area: report.result.equipment.location,
  severity: report.result.llm.criticality,
  status: report.status,
  assignee: report.assignee?.full_name ?? 'Не назначен',
  time: report.created_at.slice(11, 16),
}));

export const DEMO_META = {
  vision: 'vision: mock',
  llm: 'llm: mock',
  note: 'Демо-данные. При интеграции заменяются ответами backend.',
} as const;
