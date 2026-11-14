import { render, screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import { beforeEach, describe, expect, it } from 'vitest';
import { AppRoutes } from './App';
import { RoleProvider } from './context/RoleContext';
import type { Role } from './lib/roles';

function renderApp(role: Role | string | null, route = '/defects') {
  return render(
    <MemoryRouter initialEntries={[route]}>
      <RoleProvider initialRole={role as Role | null}>
        <AppRoutes />
      </RoleProvider>
    </MemoryRouter>,
  );
}

function getMainNav() {
  return screen.getByRole('navigation', { name: 'Основная навигация' });
}

beforeEach(() => {
  localStorage.clear();
  sessionStorage.clear();
});

describe('динамическое меню по ролям', () => {
  it('директор видит все три раздела', () => {
    renderApp('director');

    const nav = getMainNav();
    expect(within(nav).getByRole('link', { name: /Веб-сканер/ })).toBeInTheDocument();
    expect(
      within(nav).getByRole('link', { name: /Панель диспетчера/ }),
    ).toBeInTheDocument();
    expect(within(nav).getByRole('link', { name: /Сотрудники/ })).toBeInTheDocument();
    expect(screen.getAllByText('Генеральный директор').length).toBeGreaterThan(0);
  });

  it('диспетчер не видит вкладку «Сотрудники»', () => {
    renderApp('dispatcher');

    const nav = getMainNav();
    expect(within(nav).getByRole('link', { name: /Веб-сканер/ })).toBeInTheDocument();
    expect(
      within(nav).getByRole('link', { name: /Панель диспетчера/ }),
    ).toBeInTheDocument();
    expect(
      within(nav).queryByRole('link', { name: /Сотрудники/ }),
    ).not.toBeInTheDocument();
    expect(screen.getAllByText('Диспетчер').length).toBeGreaterThan(0);
  });

  it('диспетчер не может открыть /users напрямую', () => {
    renderApp('dispatcher', '/users');

    expect(
      screen.getByRole('heading', { name: 'Доступ запрещён' }),
    ).toBeInTheDocument();
    expect(screen.queryByRole('table')).not.toBeInTheDocument();
    expect(
      within(getMainNav()).queryByRole('link', { name: /Сотрудники/ }),
    ).not.toBeInTheDocument();
  });

  it('директор открывает таблицу сотрудников по /users', () => {
    renderApp('director', '/users');

    expect(
      screen.getByRole('heading', { level: 1, name: 'Сотрудники' }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole('button', { name: /Добавить сотрудника/ }),
    ).toBeInTheDocument();
    expect(screen.getByRole('table')).toBeInTheDocument();
  });

  it('администратор видит сотрудников, но не создаёт администратора', async () => {
    const user = userEvent.setup();
    renderApp('admin', '/users');

    expect(
      screen.getByRole('heading', { level: 1, name: 'Сотрудники' }),
    ).toBeInTheDocument();
    expect(
      within(getMainNav()).getByRole('link', { name: /Сотрудники/ }),
    ).toBeInTheDocument();

    await user.click(
      screen.getByRole('button', { name: /Добавить сотрудника/ }),
    );
    const dialog = screen.getByRole('dialog', {
      name: 'Добавление сотрудника',
    });

    expect(
      within(dialog).queryByRole('option', { name: /Администратор/ }),
    ).not.toBeInTheDocument();
    expect(
      within(dialog).getByRole('option', { name: /Диспетчер/ }),
    ).toBeInTheDocument();
    expect(
      within(dialog).getByRole('option', { name: /Рабочий/ }),
    ).toBeInTheDocument();
  });

  it('директор может перейти в «Сотрудники» из меню', async () => {
    const user = userEvent.setup();
    renderApp('director', '/defects');

    await user.click(
      within(getMainNav()).getByRole('link', { name: /Сотрудники/ }),
    );

    expect(
      screen.getByRole('heading', { level: 1, name: 'Сотрудники' }),
    ).toBeInTheDocument();
  });
});

describe('ограничение доступа', () => {
  it('рабочий видит только сканер', () => {
    renderApp('engineer', '/scanner');

    expect(
      screen.getByRole('heading', { level: 1, name: 'Веб-сканер' }),
    ).toBeInTheDocument();
    const nav = getMainNav();
    expect(within(nav).getByRole('link', { name: /Веб-сканер/ })).toBeInTheDocument();
    expect(
      within(nav).queryByRole('link', { name: /Панель диспетчера/ }),
    ).not.toBeInTheDocument();
    expect(
      within(nav).queryByRole('link', { name: /Сотрудники/ }),
    ).not.toBeInTheDocument();
  });

  it('рабочему закрыта панель диспетчера по прямому URL', () => {
    renderApp('engineer', '/defects');

    expect(
      screen.getByRole('heading', { level: 1, name: 'Доступ запрещён' }),
    ).toBeInTheDocument();
    expect(screen.queryByRole('table')).not.toBeInTheDocument();
  });

  it('без сессии показывает форму входа по ключу', () => {
    renderApp(null);

    expect(
      screen.getByRole('heading', { name: 'Вход в веб-панель' }),
    ).toBeInTheDocument();
    expect(screen.getByLabelText('Индивидуальный ключ')).toBeInTheDocument();
    expect(screen.queryByRole('navigation')).not.toBeInTheDocument();
  });

  it('неизвестная роль в сессии не открывает панель', () => {
    sessionStorage.setItem(
      'promscan:session:v1',
      JSON.stringify({
        accountId: 'bad',
        fullName: 'Неизвестный',
        email: 'bad@promscan.example',
        role: 'superuser',
        issuedAt: '2026-11-13T09:00:00Z',
      }),
    );
    render(
      <MemoryRouter initialEntries={['/defects']}>
        <RoleProvider>
          <AppRoutes />
        </RoleProvider>
      </MemoryRouter>,
    );

    expect(
      screen.getByRole('heading', { name: 'Вход в веб-панель' }),
    ).toBeInTheDocument();
    expect(screen.queryByRole('navigation')).not.toBeInTheDocument();
  });

  it('неверный ключ не открывает панель', async () => {
    const user = userEvent.setup();
    renderApp(null);

    await user.type(screen.getByLabelText('Индивидуальный ключ'), 'PSCXXX2345');
    await user.click(screen.getByRole('button', { name: 'Войти по ключу' }));

    expect(await screen.findByRole('alert')).toHaveTextContent('Ключ не подошёл');
    expect(screen.queryByRole('navigation')).not.toBeInTheDocument();
    expect(sessionStorage.getItem('promscan:session:v1')).toBeNull();
  });

  it('ключ директора PSCDRT2345 открывает раздел «Сотрудники»', async () => {
    const user = userEvent.setup();
    renderApp(null);

    await user.type(screen.getByLabelText('Индивидуальный ключ'), 'PSCDRT2345');
    await user.click(screen.getByRole('button', { name: 'Войти по ключу' }));

    expect(
      await screen.findByRole('heading', { level: 1, name: 'Сотрудники' }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole('button', { name: /Добавить сотрудника/ }),
    ).toBeInTheDocument();
    expect(sessionStorage.getItem('promscan:session:v1')).toContain(
      '"role":"director"',
    );
  });

  it('ключ диспетчера открывает сканер без раздела сотрудников', async () => {
    const user = userEvent.setup();
    renderApp(null);

    await user.type(screen.getByLabelText('Индивидуальный ключ'), 'PSCDSP4826');
    await user.click(screen.getByRole('button', { name: 'Войти по ключу' }));

    expect(
      await screen.findByRole('heading', { level: 1, name: 'Веб-сканер' }),
    ).toBeInTheDocument();
    expect(
      within(getMainNav()).queryByRole('link', { name: /Сотрудники/ }),
    ).not.toBeInTheDocument();
    expect(sessionStorage.getItem('promscan:session:v1')).toContain(
      '"role":"dispatcher"',
    );
  });

  it('ключ рабочего открывает только сканер', async () => {
    const user = userEvent.setup();
    renderApp(null);

    await user.type(screen.getByLabelText('Индивидуальный ключ'), 'PSCENG5542');
    await user.click(screen.getByRole('button', { name: 'Войти по ключу' }));

    expect(
      await screen.findByRole('heading', { level: 1, name: 'Веб-сканер' }),
    ).toBeInTheDocument();
    const nav = getMainNav();
    expect(within(nav).getAllByRole('link')).toHaveLength(1);
    expect(
      within(nav).queryByRole('link', { name: /Сотрудники/ }),
    ).not.toBeInTheDocument();
    expect(sessionStorage.getItem('promscan:session:v1')).toContain(
      '"role":"engineer"',
    );
  });
});
