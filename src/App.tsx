import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom';
import { Layout } from './components/Layout';
import { RoleGuard } from './components/RoleGuard';
import { Unauthorized } from './components/Unauthorized';
import { RoleProvider, useRole } from './context/RoleContext';
import { Defects } from './pages/Defects';
import { Scanner } from './pages/Scanner';
import { Task } from './pages/Task';
import { Users } from './pages/Users';

/**
 * Точка входа зависит от роли: директор после входа попадает в «Сотрудники»,
 * остальные — сразу к сканеру. Это устраняет гонку с navigate() после логина.
 */
function HomeRedirect() {
  const { role } = useRole();

  return (
    <Navigate
      to={role === 'director' || role === 'admin' ? '/users' : '/scanner'}
      replace
    />
  );
}

/**
 * Маршрутизация вынесена отдельно от BrowserRouter, чтобы её можно было
 * тестировать через MemoryRouter без подмены истории браузера.
 */
export function AppRoutes() {
  const { role } = useRole();

  /**
   * Мобильное задание остаётся отдельным экраном вне Layout и открывается
   * по демо-ссылке без сессии. Остальные URL закрыты: без роли показывается
   * форма входа, рабочему доступен только сканер.
   */
  if (!role) {
    return (
      <Routes>
        <Route path="task/:id" element={<Task />} />
        <Route path="*" element={<Unauthorized />} />
      </Routes>
    );
  }

  return (
    <Routes>
      {/* Карточка задания открывается вне Layout, без боковой панели. */}
      <Route path="task/:id" element={<Task />} />
      <Route element={<Layout />}>
        <Route index element={<HomeRedirect />} />
        <Route path="scanner" element={<Scanner />} />
        <Route
          path="defects"
          element={
            <RoleGuard allow={['director', 'admin', 'dispatcher']}>
              <Defects />
            </RoleGuard>
          }
        />
        <Route
          path="users"
          element={
            <RoleGuard allow={['director', 'admin']}>
              <Users />
            </RoleGuard>
          }
        />
        <Route path="*" element={<Navigate to="/scanner" replace />} />
      </Route>
    </Routes>
  );
}

export function App() {
  return (
    <RoleProvider>
      <BrowserRouter>
        <AppRoutes />
      </BrowserRouter>
    </RoleProvider>
  );
}
