import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import {
  MOCK_EQUIPMENT,
  MOCK_EQUIPMENT_LIST,
  MOCK_REPORTS,
  createMockInspection,
} from './inspection';
import type { CreateReportInput, EquipmentUpsert } from './api';
import { SESSION_STORAGE_KEY } from './session';

function equipmentInput(): EquipmentUpsert {
  const { id, created_at, updated_at, ...input } = MOCK_EQUIPMENT;
  void id;
  void created_at;
  void updated_at;
  return { ...input, name: 'Тестовый насос', inventory_number: 'TEST-001' };
}

function reportInput(): CreateReportInput {
  const result = createMockInspection(42);
  return {
    equipmentId: result.equipment.id,
    inspectionId: result.inspection_id,
    status: 'open',
    comment: 'Проверка перед сменой',
    result,
    assigneeId: 'emp-002',
  };
}

beforeEach(() => {
  vi.resetModules();
  vi.stubEnv('VITE_USE_MOCK_API', 'true');
  vi.stubEnv('VITE_API_BASE_URL', undefined);
  vi.stubGlobal('fetch', vi.fn());
});

afterEach(() => {
  vi.unstubAllEnvs();
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

describe('API-клиент: mock-режим', () => {
  it('по умолчанию использует mock без заданной переменной окружения', async () => {
    vi.stubEnv('VITE_USE_MOCK_API', undefined);
    const api = await import('./api');

    expect(api.API_CONFIG.useMock).toBe(true);
    expect(await api.fetchEquipment()).toBeInstanceOf(Array);
    expect(fetch).not.toHaveBeenCalled();
  });

  it('возвращает каталог EquipmentSummary[] и паспорта с узлами/specs по ID', async () => {
    const api = await import('./api');
    const equipment = await api.fetchEquipment();

    expect(equipment).toHaveLength(MOCK_EQUIPMENT_LIST.length);
    for (const item of equipment) {
      expect(item).not.toHaveProperty('nodes');
      const detail = await api.fetchEquipmentById(item.id);
      expect(detail).toMatchObject(item);
      expect(detail.specs.length).toBeGreaterThan(0);
      expect(detail.nodes.length).toBeGreaterThan(0);
      expect(detail.nodes.every((node) => node.specs.length > 0)).toBe(true);
    }
    expect(fetch).not.toHaveBeenCalled();
  });

  it('возвращает 404 для неизвестного оборудования', async () => {
    const api = await import('./api');

    await expect(api.fetchEquipmentById('missing')).rejects.toMatchObject({
      name: 'ApiError', status: 404,
    });
    await expect(api.inspectImage(null, 'missing')).rejects.toMatchObject({ status: 404 });
  });

  it('создаёт и обновляет оборудование, сохраняя изменения для следующих GET', async () => {
    const api = await import('./api');
    const saved = await api.saveEquipment(equipmentInput());

    expect(saved.id).not.toBe(MOCK_EQUIPMENT.id);
    expect(saved).toMatchObject(equipmentInput());
    expect(saved.created_at).toBe(saved.updated_at);
    expect(Number.isNaN(Date.parse(saved.created_at))).toBe(false);
    expect(await api.fetchEquipment()).toContainEqual(expect.objectContaining({ id: saved.id }));
    expect(await api.fetchEquipmentById(saved.id)).toEqual(saved);

    const updated = await api.saveEquipment({ ...saved, location: 'Новый цех' });
    expect(updated).toMatchObject({ id: saved.id, location: 'Новый цех', created_at: saved.created_at });
    expect(await api.fetchEquipmentById(saved.id)).toEqual(updated);
    expect(await api.fetchEquipment()).toHaveLength(MOCK_EQUIPMENT_LIST.length + 1);
  });

  it.each(['open', 'in_progress', 'closed'] as const)(
    'фильтрует отчёты по status=%s',
    async (status) => {
      const api = await import('./api');
      const reports = await api.fetchReports(status);

      expect(reports).toEqual(MOCK_REPORTS.filter((report) => report.status === status));
      expect(reports.length).toBeGreaterThan(0);
    },
  );

  it('создаёт отчёт с переданными полями и добавляет его в список', async () => {
    const api = await import('./api');
    const input = reportInput();
    const saved = await api.createReport({ ...input, photo: new Blob(['image'], { type: 'image/jpeg' }) });

    expect(saved).toMatchObject({
      equipment_id: input.equipmentId,
      inspection_id: input.inspectionId,
      status: 'open',
      comment: input.comment,
      result: input.result,
      photo_url: null,
      assignee: { id: 'emp-002', full_name: 'Анна Петрова' },
      started_at: null,
      completed_at: null,
      repair_comment: null,
    });
    expect(saved.id).toBeTruthy();
    expect(saved.created_at).toBe(saved.updated_at);
    expect(await api.fetchReports(input.status)).toContainEqual(saved);
    expect(await api.fetchReports()).toHaveLength(MOCK_REPORTS.length + 1);

    const second = await api.createReport({ ...input, comment: undefined });
    expect(second.comment).toBe('');
    expect(second.id).not.toBe(saved.id);
    expect(fetch).not.toHaveBeenCalled();
  });

  it('читает задачу по ID и проводит её по статусам', async () => {
    const api = await import('./api');
    const input = reportInput();
    const saved = await api.createReport(input);

    expect(await api.fetchReportById(saved.id)).toEqual(saved);

    const started = await api.updateReportStatus(saved.id, 'in_progress');
    expect(started.status).toBe('in_progress');
    expect(started.started_at).toBeTruthy();
    expect(started.completed_at).toBeNull();
    expect(await api.fetchReportById(saved.id)).toEqual(started);

    const completed = await api.updateReportStatus(
      saved.id,
      'closed',
      'Заменено крепление.',
    );
    expect(completed.status).toBe('closed');
    expect(completed.completed_at).toBeTruthy();
    expect(completed.repair_comment).toBe('Заменено крепление.');
    expect(await api.fetchReports('closed')).toContainEqual(completed);

    await expect(api.updateReportStatus(saved.id, 'in_progress')).rejects.toMatchObject({
      status: 409,
    });
  });

  it('не даёт начать задачу без исполнителя', async () => {
    const api = await import('./api');
    const saved = await api.createReport({ ...reportInput(), assigneeId: null });

    await expect(api.updateReportStatus(saved.id, 'in_progress')).rejects.toMatchObject({
      status: 409,
      message: expect.stringContaining('назначьте'),
    });
  });

  it('сохраняет mock-задачи между перезагрузкой модуля', async () => {
    const api = await import('./api');
    const saved = await api.createReport(reportInput());

    vi.resetModules();
    const reloaded = await import('./api');
    expect(await reloaded.fetchReportById(saved.id)).toEqual(saved);
  });

  it('не позволяет UI изменить хранилище через возвращённые объекты', async () => {
    const api = await import('./api');
    const detail = await api.fetchEquipmentById(MOCK_EQUIPMENT.id);
    detail.nodes[0].specs[0].value = 'Изменено в UI';
    const reports = await api.fetchReports();
    reports[0].result.defects[0].bbox[0] = 99;

    expect(await api.fetchEquipmentById(MOCK_EQUIPMENT.id)).toEqual(MOCK_EQUIPMENT);
    expect(await api.fetchReports()).toEqual(MOCK_REPORTS);
  });

  it('включает сценарий детекций только по явному live-флагу в mock', async () => {
    const api = await import('./api');
    expect((await api.inspectImage(null, MOCK_EQUIPMENT.id, 8, { live: true })).defects).toEqual([]);
    expect((await api.inspectImage(null, MOCK_EQUIPMENT.id, 8, { live: false })).defects).toHaveLength(3);
    expect((await api.inspectImage(null, MOCK_EQUIPMENT.id, 8)).defects).toHaveLength(3);
      expect(fetch).not.toHaveBeenCalled();
  });

  it('возвращает безопасный mock-список сотрудников и сохраняет mock-удаление', async () => {
    const api = await import('./api');

    const employees = await api.fetchEmployees();
    expect(employees).toHaveLength(4);
    expect(employees[0]).toMatchObject({
      id: 'emp-001',
      fullName: 'Иван Иванов',
      role: 'dispatcher',
    });
    expect(employees[0]).not.toHaveProperty('keySalt');
    expect(employees[0]).not.toHaveProperty('keyHash');
    expect(fetch).not.toHaveBeenCalled();

    await api.deleteEmployee('emp-001');
    expect(
      (await api.fetchEmployees()).some((employee) => employee.id === 'emp-001'),
    ).toBe(false);
    expect(fetch).not.toHaveBeenCalled();
  });

  it('анализирует выбранное оборудование и возвращает нормализованные bbox/polygon', async () => {
    const api = await import('./api');
    for (const equipment of MOCK_EQUIPMENT_LIST) {
      for (const tick of [0, 1, 10, 1000]) {
        const result = await api.inspectImage(null, equipment.id, tick);
        expect(result.equipment.id).toBe(equipment.id);
        for (const defect of result.defects) {
          const [x1, y1, x2, y2] = defect.bbox;
          expect(x1).toBeLessThan(x2);
          expect(y1).toBeLessThan(y2);
          for (const value of [...defect.bbox, ...(defect.polygon ?? []).flat()]) {
            expect(Number.isFinite(value)).toBe(true);
            expect(value).toBeGreaterThanOrEqual(0);
            expect(value).toBeLessThanOrEqual(1);
          }
          if (defect.node_id !== null) {
            expect(result.equipment.nodes.some((node) => node.id === defect.node_id)).toBe(true);
          }
        }
      }
    }
  });
});

describe('API-клиент: HTTP-контракт', () => {
  const fetchMock = vi.fn<typeof fetch>();

  const remoteEmployee = {
    id: 'emp-007',
    full_name: 'Пётр Сидоров',
    email: 'p.sidorov@promscan.ru',
    role: 'dispatcher',
    key_created_at: '2026-11-15T08:30:00Z',
    invitation: {
      status: 'queued',
      provider: 'smtp',
      email: 'p.sidorov@promscan.ru',
      sent_at: null,
      error: null,
    },
    access_key: 'OPEN-KEY-SHOULD-NEVER-LEAK',
    key_salt: 'server-salt',
    key_hash: 'server-hash',
  };

  function setSessionToken(token = 'test-session-token') {
    sessionStorage.setItem(
      SESSION_STORAGE_KEY,
      JSON.stringify({
        accountId: 'director-001',
        fullName: 'Генеральный директор',
        email: 'director@promscan.ru',
        role: 'director',
        issuedAt: '2026-11-15T08:00:00Z',
        sessionToken: token,
      }),
    );
  }

  beforeEach(() => {
    vi.stubEnv('VITE_USE_MOCK_API', 'false');
    vi.stubEnv('VITE_API_BASE_URL', 'https://api.example///');
    fetchMock.mockReset();
    fetchMock.mockImplementation(async () => new Response(JSON.stringify(MOCK_EQUIPMENT), { status: 200 }));
    vi.stubGlobal('fetch', fetchMock);
  });

  it('использует GET для списка, ID и фильтра status', async () => {
    const api = await import('./api');
    await api.fetchEquipment();
    await api.fetchEquipmentById('pump/a b');
    await api.fetchReports('in_progress');
    await api.fetchReports();
    await api.fetchReportById('report/a b');

    expect(fetchMock.mock.calls.map(([url]) => url)).toEqual([
      'https://api.example/api/equipment',
      'https://api.example/api/equipment/pump%2Fa%20b',
      'https://api.example/api/reports?status=in_progress',
      'https://api.example/api/reports',
      'https://api.example/api/reports/report%2Fa%20b',
    ]);
    for (const [, init] of fetchMock.mock.calls) {
      expect(init?.method ?? 'GET').toBe('GET');
      expect(init?.credentials).toBe('include');
      expect(new Headers(init?.headers).get('Accept')).toBe('application/json');
    }
  });

  it('запрашивает сотрудников с bearer и исключает director из UI-списка', async () => {
    const api = await import('./api');
    setSessionToken();
    fetchMock.mockResolvedValueOnce(
      new Response(
        JSON.stringify([
          remoteEmployee,
          { ...remoteEmployee, id: 'director-001', role: 'director' },
        ]),
        { status: 200 },
      ),
    );

    const employees = await api.fetchEmployees();

    expect(employees).toEqual([
      {
        id: 'emp-007',
        fullName: 'Пётр Сидоров',
        email: 'p.sidorov@promscan.ru',
        role: 'dispatcher',
        keyCreatedAt: '2026-11-15T08:30:00Z',
        invitation: {
          status: 'queued',
          email: 'p.sidorov@promscan.ru',
          provider: 'smtp',
          sentAt: null,
          error: null,
        },
      },
    ]);

    const [url, init] = fetchMock.mock.calls[0];
    expect(url).toBe('https://api.example/api/users');
    expect(init?.method ?? 'GET').toBe('GET');
    expect(init?.credentials).toBe('include');
    expect(new Headers(init?.headers).get('Accept')).toBe('application/json');
    expect(new Headers(init?.headers).get('Authorization')).toBe(
      'Bearer test-session-token',
    );
  });

  it('создаёт сотрудника с нормализованным JSON-телом и возвращает статус приглашения', async () => {
    const api = await import('./api');
    setSessionToken('create-token');
    fetchMock.mockResolvedValueOnce(
      new Response(
        JSON.stringify({
          account: remoteEmployee,
          invitation: remoteEmployee.invitation,
        }),
        { status: 201 },
      ),
    );

    const result = await api.createEmployee({
      fullName: '  Пётр   Сидоров  ',
      email: ' P.Sidorov@Promscan.ru ',
      role: 'dispatcher',
    });

    expect(result.employee).toMatchObject({
      id: 'emp-007',
      fullName: 'Пётр Сидоров',
      email: 'p.sidorov@promscan.ru',
      role: 'dispatcher',
    });
    expect(result.invitation).toEqual({
      provider: 'smtp',
      status: 'queued',
      messageId: null,
      error: null,
    });

    const [url, init] = fetchMock.mock.calls[0];
    expect(url).toBe('https://api.example/api/users');
    expect(init?.method).toBe('POST');
    expect(init?.credentials).toBe('include');
    expect(new Headers(init?.headers).get('Accept')).toBe('application/json');
    expect(new Headers(init?.headers).get('Authorization')).toBe(
      'Bearer create-token',
    );
    expect(new Headers(init?.headers).get('Content-Type')).toBe('application/json');
    expect(JSON.parse(init?.body as string)).toEqual({
      full_name: 'Пётр Сидоров',
      email: 'p.sidorov@promscan.ru',
      role: 'dispatcher',
    });
  });

  it('отклоняет mutation response с ролью директора и не раскрывает секретные поля', async () => {
    const api = await import('./api');
    fetchMock.mockResolvedValueOnce(
      new Response(
        JSON.stringify({
          account: { ...remoteEmployee, role: 'director' },
          invitation: remoteEmployee.invitation,
        }),
        { status: 201 },
      ),
    );

    await expect(api.createEmployee({
      fullName: 'Сотрудник Тестов',
      email: 'test@promscan.ru',
      role: 'dispatcher',
    })).rejects.toMatchObject({ name: 'ApiError', status: 502 });
  });

  it('отклоняет некорректные runtime-поля списка сотрудников', async () => {
    const api = await import('./api');
    fetchMock.mockResolvedValueOnce(
      new Response(
        JSON.stringify([{ ...remoteEmployee, invitation: { ...remoteEmployee.invitation, status: 'unknown' } }]),
        { status: 200 },
      ),
    );

    await expect(api.fetchEmployees()).rejects.toMatchObject({
      name: 'ApiError',
      status: 502,
      message: 'Ответ API содержит неизвестный статус приглашения.',
    });
  });

  it('перевыпускает ключ через employee endpoint с bearer', async () => {
    const api = await import('./api');
    setSessionToken('reissue-token');
    fetchMock.mockResolvedValueOnce(
      new Response(
        JSON.stringify({
          account: { ...remoteEmployee, key_created_at: '2026-11-15T09:00:00Z' },
          invitation: { ...remoteEmployee.invitation, status: 'queued' },
        }),
        { status: 200 },
      ),
    );

    const result = await api.reissueEmployee('emp/a b');

    expect(result.employee.keyCreatedAt).toBe('2026-11-15T09:00:00Z');
    const [url, init] = fetchMock.mock.calls[0];
    expect(url).toBe('https://api.example/api/users/emp%2Fa%20b/access');
    expect(init?.method).toBe('POST');
    expect(init?.credentials).toBe('include');
    expect(init?.body).toBeUndefined();
    expect(new Headers(init?.headers).get('Authorization')).toBe(
      'Bearer reissue-token',
    );
  });

  it('удаляет сотрудника через DELETE и принимает ответ 204', async () => {
    const api = await import('./api');
    setSessionToken('delete-token');
    fetchMock.mockResolvedValueOnce(new Response(null, { status: 204 }));

    await expect(api.deleteEmployee('emp/a b')).resolves.toBeUndefined();

    const [url, init] = fetchMock.mock.calls[0];
    expect(url).toBe('https://api.example/api/users/emp%2Fa%20b');
    expect(init?.method).toBe('DELETE');
    expect(init?.credentials).toBe('include');
    expect(new Headers(init?.headers).get('Accept')).toBe('application/json');
    expect(new Headers(init?.headers).get('Authorization')).toBe(
      'Bearer delete-token',
    );
  });

  it('передаёт EquipmentUpsert в POST JSON без служебных дат', async () => {
    const api = await import('./api');
    await api.saveEquipment(MOCK_EQUIPMENT);
    const [url, init] = fetchMock.mock.calls[0];
    const { created_at, updated_at, ...payload } = MOCK_EQUIPMENT;
    void created_at;
    void updated_at;

    expect(url).toBe('https://api.example/api/equipment');
    expect(init?.method).toBe('POST');
    expect(new Headers(init?.headers).get('Content-Type')).toBe('application/json');
    expect(JSON.parse(init?.body as string)).toEqual(payload);
  });

  it('передаёт file и equipment_id в multipart для inspect', async () => {
    const api = await import('./api');
    const image = new Blob(['frame'], { type: 'image/jpeg' });
    await api.inspectImage(image, MOCK_EQUIPMENT.id, 8, { live: true });
    const [url, init] = fetchMock.mock.calls[0];
    const form = init?.body as FormData;

    expect(url).toBe('https://api.example/api/inspect');
    expect(init?.method).toBe('POST');
    expect(init?.credentials).toBe('include');
    expect(form.get('equipment_id')).toBe(MOCK_EQUIPMENT.id);
    expect(form.get('file')).toMatchObject({ name: 'frame.jpg', type: 'image/jpeg', size: image.size });
    expect(Array.from(form.keys())).toEqual(['file', 'equipment_id']);
    expect(new Headers(init?.headers).has('Content-Type')).toBe(false);
  });

  it('не отправляет inspect без изображения в real-режиме', async () => {
    const api = await import('./api');
    await expect(api.inspectImage(null, MOCK_EQUIPMENT.id)).rejects.toMatchObject({ status: 400 });
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it.each([false, true])('передаёт multipart payload отчёта (photo=%s)', async (withPhoto) => {
    const api = await import('./api');
    const input = reportInput();
    const photo = withPhoto ? new Blob(['report'], { type: 'image/jpeg' }) : null;
    await api.createReport({ ...input, photo });
    const [url, init] = fetchMock.mock.calls[0];
    const form = init?.body as FormData;

    expect(url).toBe('https://api.example/api/reports');
    expect(init?.method).toBe('POST');
    expect(form.get('equipment_id')).toBe(input.equipmentId);
    expect(form.get('inspection_id')).toBe(input.inspectionId);
    expect(form.get('status')).toBe(input.status);
    expect(form.get('comment')).toBe(input.comment);
    expect(form.get('assignee_id')).toBe(input.assigneeId);
    expect(JSON.parse(form.get('payload') as string)).toEqual(input.result);
    expect(form.has('photo')).toBe(withPhoto);
    expect(new Headers(init?.headers).has('Content-Type')).toBe(false);
    if (withPhoto) expect(form.get('photo')).toMatchObject({ name: 'report.jpg', type: 'image/jpeg' });
  });

  it('передаёт смену статуса задачи через PATCH', async () => {
    const api = await import('./api');
    fetchMock.mockResolvedValueOnce(
      new Response(JSON.stringify({ ...MOCK_REPORTS[0], status: 'closed' }), { status: 200 }),
    );
    await api.updateReportStatus('report-1042', 'closed', 'Работы выполнены.');

    const [url, init] = fetchMock.mock.calls[0];
    expect(url).toBe('https://api.example/api/reports/report-1042/status');
    expect(init?.method).toBe('PATCH');
    expect(new Headers(init?.headers).get('Content-Type')).toBe('application/json');
    expect(JSON.parse(init?.body as string)).toEqual({
      status: 'closed',
      comment: 'Работы выполнены.',
    });
  });

  it('сохраняет HTTP-статус и detail при ошибке API', async () => {
    const api = await import('./api');
    fetchMock.mockResolvedValueOnce(new Response(JSON.stringify({ detail: 'Паспорт не найден' }), { status: 404 }));
    await expect(api.fetchEquipmentById('missing')).rejects.toMatchObject({
      name: 'ApiError', status: 404, message: 'Паспорт не найден',
    });
  });

  it('показывает сообщения FastAPI для массива ошибок валидации', async () => {
    const api = await import('./api');
    fetchMock.mockResolvedValueOnce(new Response(JSON.stringify({
      detail: [
        { loc: ['body', 'file'], msg: 'Field required', type: 'missing' },
        { loc: ['body', 'equipment_id'], msg: 'Field required', type: 'missing' },
      ],
    }), { status: 422 }));

    await expect(api.inspectImage(new Blob(['frame']), 'pump-1')).rejects.toMatchObject({
      name: 'ApiError',
      status: 422,
      message: 'file: Field required; equipment_id: Field required',
    });
  });
});

