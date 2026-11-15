import puppeteer from 'puppeteer-core';

const browser = await puppeteer.launch({
  executablePath: 'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe',
  headless: true,
  args: [
    '--no-sandbox',
    '--disable-gpu',
    '--use-fake-ui-for-media-stream',
    '--use-fake-device-for-media-stream',
  ],
  defaultViewport: { width: 1440, height: 900 },
});
const page = await browser.newPage();
const base = 'http://127.0.0.1:5173';
const results = [];
const check = (name, value) => {
  results.push(`${value ? 'PASS' : 'FAIL'} ${name}`);
  if (!value) process.exitCode = 1;
};

const go = async (path, role) => {
  await page.goto(`${base}${path}`, { waitUntil: 'domcontentloaded', timeout: 60000 });
  await page.evaluate((nextRole) => {
    sessionStorage.clear();

    if (nextRole === null) return;

    const accounts = {
      director: {
        accountId: 'director',
        fullName: 'Генеральный директор',
        email: 'director@promscan.example',
      },
      admin: {
        accountId: 'emp-admin',
        fullName: 'Администратор',
        email: 'admin@promscan.example',
      },
      dispatcher: {
        accountId: 'emp-001',
        fullName: 'Иван Иванов',
        email: 'i.ivanov@promscan.ru',
      },
      engineer: {
        accountId: 'emp-003',
        fullName: 'Алексей Смирнов',
        email: 'a.smirnov@promscan.ru',
      },
    };
    const account = accounts[nextRole];

    sessionStorage.setItem(
      'promscan:session:v1',
      JSON.stringify({
        ...account,
        role: nextRole,
        issuedAt: new Date().toISOString(),
      }),
    );
  }, role ?? null);
  await page.goto(`${base}${path}`, { waitUntil: 'domcontentloaded', timeout: 60000 });
};

await go('/', null);
await page.waitForSelector('#access-key');
await page.focus('#access-key');
await page.keyboard.type('PSCDRT2345', { delay: 20 });
await page.keyboard.press('Enter');
await page.waitForFunction(() => location.pathname === '/users');
await page.waitForSelector('table');
check('director login lands on /users', page.url().endsWith('/users'));

const newTab = await browser.newPage();
await newTab.goto(base, { waitUntil: 'domcontentloaded' });
await newTab.waitForSelector('#access-key');
const newTabAsksKey = await newTab.evaluate(() =>
  document.body.textContent?.includes('Вход в веб-панель'),
);
check('new tab asks for access key', newTabAsksKey);
await newTab.close();

await page.evaluate(() => {
  [...document.querySelectorAll('button')]
    .find((node) => (node.textContent ?? '').includes('Добавить сотрудника'))
    ?.click();
});
await page.waitForSelector('[role="dialog"]');
await page.type('#employee-full-name', 'Пётр Сидоров');
await page.type('#employee-email', 'p.sidorov@promscan.ru');
await page.evaluate(() => {
  [...document.querySelectorAll('[role="dialog"] button')]
    .find(
      (node) =>
        (node.textContent ?? '').trim() === 'Создать и отправить ключ',
    )
    ?.click();
});
await page.waitForSelector('#key-delivery-title');
const outbox = await page.evaluate(() =>
  JSON.parse(localStorage.getItem('promscan:mail-outbox:v1') ?? '[]'),
);
const accessKey = outbox[0]?.accessKey ?? '';
check(`10-character access key emailed (${accessKey})`, /^[A-HJ-NP-Z2-9]{10}$/.test(accessKey));
const keyHiddenFromAdmin = await page.evaluate((key) => {
  const dialog = document.querySelector('[role="dialog"]');
  return (
    !dialog?.querySelector('[data-access-key]') &&
    !(dialog?.textContent ?? '').includes(key) &&
    !(document.body.textContent ?? '').includes(key)
  );
}, accessKey);
check('access key is not shown to the administrator', keyHiddenFromAdmin);
const footerVisible = await page.evaluate(() => {
  const dialog = document.querySelector('[role="dialog"]');
  const button = [...(dialog?.querySelectorAll('button') ?? [])].find(
    (node) => (node.textContent ?? '').trim() === 'Готово',
  );
  if (!button) return false;
  const rect = button.getBoundingClientRect();
  return rect.bottom <= innerHeight + 1 && rect.top >= 0;
});
check('delivery confirmation visible without scrolling', footerVisible);

await page.evaluate(() => {
  [...document.querySelectorAll('[role="dialog"] button')]
    .find((node) => (node.textContent ?? '').trim() === 'Готово')
    ?.click();
});
await page.waitForSelector('[role="dialog"]', { hidden: true });
const newRow = await page.evaluate(() =>
  [...document.querySelectorAll('tbody tr')].some((row) =>
    (row.textContent ?? '').includes('p.sidorov@promscan.ru'),
  ),
);
check('employee added to table', newRow);
const keyNotInTable = await page.evaluate(
  (key) => !(document.body.textContent ?? '').includes(key),
  accessKey,
);
check('access key is not shown in the table', keyNotInTable);

await go('/users', null);
await page.waitForSelector('#access-key');
await page.focus('#access-key');
await page.keyboard.type(accessKey, { delay: 15 });
await page.keyboard.press('Enter');
await page.waitForFunction(() => location.pathname === '/scanner');
check('new employee key opens the assigned role', page.url().endsWith('/scanner'));

await go('/scanner', 'dispatcher');
await page.waitForSelector('nav[aria-label="Основная навигация"]');
const dispatcherNav = await page.$$eval(
  'nav[aria-label="Основная навигация"] a',
  (links) => links.map((link) => link.textContent?.trim()),
);
check(
  `dispatcher nav limited (${dispatcherNav.join(', ')})`,
  dispatcherNav.length === 2 && !dispatcherNav.some((label) => label?.includes('Сотрудники')),
);

await go('/users', 'dispatcher');
const denied = await page.evaluate(() =>
  document.body.textContent?.includes('Доступ запрещён'),
);
check('dispatcher gets 403 on /users', denied);

await go('/scanner', 'engineer');
await page.waitForSelector('h1');
const engineerFacts = await page.evaluate(() => ({
  scanner: [...document.querySelectorAll('h1')].some((node) =>
    (node.textContent ?? '').includes('Веб-сканер'),
  ),
  links: [...document.querySelectorAll('nav[aria-label="Основная навигация"] a')].map(
    (link) => link.textContent?.trim() ?? '',
  ),
}));
check('engineer sees the web scanner', engineerFacts.scanner);
check(
  `engineer nav limited to scanner (${engineerFacts.links.join(', ')})`,
  engineerFacts.links.length === 1 &&
    engineerFacts.links[0].includes('Веб-сканер'),
);

await go('/defects', 'engineer');
const engineerDenied = await page.evaluate(() =>
  document.body.textContent?.includes('Доступ запрещён'),
);
check('engineer gets 403 on /defects', engineerDenied);

await go('/scanner', 'dispatcher');
await page.waitForSelector('#llm-heading', { timeout: 20000 });
const openedHandoff = await page.evaluate(() => {
  const button = [...document.querySelectorAll('button')].find(
    (node) => (node.textContent ?? '').trim() === 'Передать задачу',
  );
  button?.click();
  return Boolean(button);
});
check('scanner handoff button opens form', openedHandoff);
await page.waitForSelector('#report-create-panel');
check('assignee select present', (await page.$('#report-assignee')) !== null);
await page.select('#report-assignee', 'emp-003');
await page.type('#report-comment', 'E2E: трещина корпуса');
await page.evaluate(() => {
  document
    .querySelector('#report-create-panel form')
    ?.requestSubmit();
});
await page.waitForFunction(
  () => document.body.textContent?.includes('Задача передана'),
  { timeout: 15000 },
);
const taskHref = await page.$eval('[data-task-link]', (link) => link.href);
check('task link is absolute', taskHref.startsWith(`${base}/task/`));
const taskPath = new URL(taskHref).pathname;
const taskId = taskPath.split('/').pop() ?? '';
const handoffText = await page.evaluate(
  () => document.querySelector('#report-create-panel')?.textContent ?? '',
);
check('handoff shows assignee', handoffText.includes('Алексей Смирнов'));

await go(taskPath, 'engineer');
await page.waitForSelector('h1');
const taskText = await page.evaluate(() => document.body.textContent ?? '');
check('engineer opens task screen', taskText.includes('Задание сотруднику'));
check(
  'task screen shows recommendation',
  taskText.includes('Рекомендация по восстановлению'),
);
await page.evaluate(() => {
  [...document.querySelectorAll('button')]
    .find((node) => (node.textContent ?? '').trim() === 'Выполнить задачу')
    ?.click();
});
await page.waitForFunction(
  () => document.body.textContent?.includes('Отметить выполненной'),
  { timeout: 10000 },
);
check('employee starts task', true);

await go('/defects', 'dispatcher');
await page.waitForSelector('table');
const inProgressRow = await page.evaluate((id) => {
  const row = [...document.querySelectorAll('tbody tr')].find((node) =>
    (node.textContent ?? '').includes(id),
  );
  return row?.textContent ?? '';
}, taskId);
check('dispatcher sees task in progress', inProgressRow.includes('В работе'));
check(
  'dispatcher sees task assignee',
  inProgressRow.includes('Алексей Смирнов'),
);

await go(taskPath, 'engineer');
await page.waitForSelector('#task-comment');
await page.type('#task-comment', 'E2E: ремонт завершён');
await page.evaluate(() => {
  [...document.querySelectorAll('button')]
    .find((node) => (node.textContent ?? '').trim() === 'Отметить выполненной')
    ?.click();
});
await page.waitForFunction(
  () => document.body.textContent?.includes('Задача выполнена'),
  { timeout: 10000 },
);
const completedText = await page.evaluate(
  () => document.body.textContent ?? '',
);
check(
  'employee completes task with comment',
  completedText.includes('E2E: ремонт завершён'),
);

await go('/defects', 'dispatcher');
await page.waitForSelector('table');
const closedRow = await page.evaluate((id) => {
  const row = [...document.querySelectorAll('tbody tr')].find((node) =>
    (node.textContent ?? '').includes(id),
  );
  return row?.textContent ?? '';
}, taskId);
check('dispatcher sees task completed', closedRow.includes('Выполнено'));
check(
  'completed task keeps assignee',
  closedRow.includes('Алексей Смирнов'),
);

console.log(results.join('\n'));
await browser.close();
