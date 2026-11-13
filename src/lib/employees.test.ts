import { beforeEach, describe, expect, it } from 'vitest';
import {
  EMPLOYEES_STORAGE_KEY,
  MOCK_EMPLOYEES,
  findEmployeeById,
  getEngineers,
  loadEmployees,
  saveEmployees,
  toEmployeeRef,
  type Employee,
} from './employees';

beforeEach(() => {
  localStorage.clear();
});

describe('демо-справочник сотрудников', () => {
  it('без сохранённых данных отдаёт копию сидов', () => {
    const employees = loadEmployees();

    expect(employees).toHaveLength(MOCK_EMPLOYEES.length);
    expect(employees).not.toBe(MOCK_EMPLOYEES);
    expect(employees[0]).not.toBe(MOCK_EMPLOYEES[0]);
  });

  it('сохраняет и перечитывает добавленного сотрудника', () => {
    const extra: Employee = {
      id: 'emp-test',
      fullName: 'Пётр Сидоров',
      email: 'p.sidorov@promscan.ru',
      role: 'dispatcher',
      keySalt: 'aa'.repeat(16),
      keyHash: 'bb'.repeat(32),
      keyCreatedAt: '2026-11-14T10:00:00Z',
      invitation: {
        status: 'queued',
        email: 'p.sidorov@promscan.ru',
        provider: 'mock',
        sentAt: null,
        error: null,
      },
    };

    saveEmployees([extra, ...loadEmployees()]);

    const employees = loadEmployees();
    expect(employees[0]).toEqual(extra);
    expect(findEmployeeById('emp-test')?.fullName).toBe('Пётр Сидоров');
    expect(localStorage.getItem(EMPLOYEES_STORAGE_KEY)).toContain('emp-test');
  });

  it('при битом JSON возвращает сиды', () => {
    localStorage.setItem(EMPLOYEES_STORAGE_KEY, '{broken');

    expect(loadEmployees()).toHaveLength(MOCK_EMPLOYEES.length);
  });

  it('отбрасывает записи с неизвестной ролью и без хеша', () => {
    localStorage.setItem(
      EMPLOYEES_STORAGE_KEY,
      JSON.stringify([
        { ...MOCK_EMPLOYEES[0], id: 'ok' },
        { ...MOCK_EMPLOYEES[1], id: 'bad-role', role: 'director' },
        { ...MOCK_EMPLOYEES[2], id: 'no-hash', keyHash: undefined },
      ]),
    );

    const employees = loadEmployees();
    expect(employees.map((employee) => employee.id)).toEqual(['ok']);
  });

  it('возвращает только рабочих для назначения задач', () => {
    const engineers = getEngineers();

    expect(engineers).toHaveLength(2);
    expect(engineers.every((employee) => employee.role === 'engineer')).toBe(true);
  });

  it('EmployeeRef не раскрывает email и ключи', () => {
    const ref = toEmployeeRef(MOCK_EMPLOYEES[0]);

    expect(ref).toEqual({
      id: MOCK_EMPLOYEES[0].id,
      full_name: MOCK_EMPLOYEES[0].fullName,
    });
    expect(ref).not.toHaveProperty('email');
    expect(ref).not.toHaveProperty('keyHash');
    expect(ref).not.toHaveProperty('keySalt');
  });
});
