import puppeteer from 'puppeteer-core';

/**
 * Проверка адаптивности на реальных размерах: нет горизонтального переполнения,
 * таблицы на узких экранах заменены карточками, ключевые блоки присутствуют.
 *
 * Запускать при работающем `npm run dev`:
 *   node .taste-skill/adaptivity-check.mjs
 */

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

const ACCOUNTS = {
  director: {
    accountId: 'director',
    fullName: 'Генеральный директор',
    email: 'director@promscan.example',
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

async function open(path, role = null, waitMs = 700) {
  await page.goto(`${base}/`, { waitUntil: 'domcontentloaded', timeout: 60000 });
  await page.evaluate(
    ({ account, nextRole }) => {
      sessionStorage.clear();

      if (!account) return;

      sessionStorage.setItem(
        'promscan:session:v1',
        JSON.stringify({
          ...account,
          role: nextRole,
          issuedAt: new Date().toISOString(),
        }),
      );
    },
    { account: role ? ACCOUNTS[role] : null, nextRole: role },
  );
  await page.goto(`${base}${path}`, {
    waitUntil: 'domcontentloaded',
    timeout: 60000,
  });
  await page.waitForFunction(() => document.querySelector('#root')?.children.length, {
    timeout: 30000,
  });
  await new Promise((resolve) => setTimeout(resolve, waitMs));
}

async function noHorizontalOverflow() {
  return page.evaluate(() => {
    const root = document.documentElement;
    const body = document.body;

    return (
      root.scrollWidth <= window.innerWidth + 1 &&
      body.scrollWidth <= window.innerWidth + 1
    );
  });
}

async function pageFacts() {
  return page.evaluate(() => ({
    tables: document.querySelectorAll('table').length,
    articles: document.querySelectorAll('main article').length,
    hasKeyInput: Boolean(document.querySelector('#access-key')),
    hasCamera: Boolean(document.querySelector('[aria-label="Окно камеры"]')),
    hasReport: Boolean(
      document.querySelector('[aria-label="Результат распознавания"]'),
    ),
    hasTaskHeading: Boolean(document.querySelector('h1')),
    hasUsersHeading: Boolean(
      [...document.querySelectorAll('h1')].some((node) =>
        (node.textContent ?? '').includes('Сотрудники'),
      ),
    ),
    hasDefectsHeading: Boolean(
      [...document.querySelectorAll('h1')].some((node) =>
        (node.textContent ?? '').includes('Панель диспетчера'),
      ),
    ),
  }));
}

const viewports = [
  { width: 390, height: 844, isMobile: true, hasTouch: true },
  { width: 768, height: 1024 },
  { width: 1024, height: 768 },
  { width: 1440, height: 900 },
];

for (const viewport of viewports) {
  await page.setViewport(viewport);
  const label = viewport.width;

  await open('/', null);
  check(`${label}: login without horizontal overflow`, await noHorizontalOverflow());
  check(`${label}: login shows access key field`, (await pageFacts()).hasKeyInput);

  await open('/users', 'director');
  let facts = await pageFacts();
  check(`${label}: users without horizontal overflow`, await noHorizontalOverflow());
  check(`${label}: users heading rendered`, facts.hasUsersHeading);

  if (viewport.width < 1024) {
    check(`${label}: users uses cards instead of a table`, facts.tables === 0 && facts.articles >= 4);
  } else {
    check(`${label}: users uses a table on desktop`, facts.tables === 1);
  }

  await open('/defects', 'dispatcher');
  facts = await pageFacts();
  check(`${label}: defects without horizontal overflow`, await noHorizontalOverflow());
  check(`${label}: defects heading rendered`, facts.hasDefectsHeading);

  if (viewport.width < 1024) {
    check(
      `${label}: defects uses cards instead of a table`,
      facts.tables === 0 && facts.articles >= 3,
    );
  } else {
    check(`${label}: defects uses a table on desktop`, facts.tables === 1);
  }

  await open('/scanner', 'director', 2600);
  facts = await pageFacts();
  check(`${label}: scanner without horizontal overflow`, await noHorizontalOverflow());
  check(`${label}: scanner shows camera`, facts.hasCamera);
  check(`${label}: scanner shows live report`, facts.hasReport);

  await open('/task/report-1042', null);
  facts = await pageFacts();
  check(`${label}: task without horizontal overflow`, await noHorizontalOverflow());
  check(`${label}: task heading rendered`, facts.hasTaskHeading);
}

await browser.close();
console.log(results.join('\n'));
