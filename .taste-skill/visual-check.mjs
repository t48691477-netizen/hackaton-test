import fs from 'node:fs';
import puppeteer from 'puppeteer-core';

const OUT = '.taste-skill/shots';
fs.mkdirSync(OUT, { recursive: true });

const browser = await puppeteer.launch({
  executablePath: 'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe',
  headless: true,
  args: [
    '--no-sandbox',
    '--disable-gpu',
    '--use-fake-ui-for-media-stream',
    '--use-fake-device-for-media-stream',
    '--font-render-hinting=none',
  ],
  defaultViewport: { width: 1440, height: 900, deviceScaleFactor: 1 },
});

const page = await browser.newPage();
const base = 'http://127.0.0.1:5173';
const wait = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

async function settle(ms = 500) {
  await page.evaluate(() => document.fonts.ready);
  await wait(ms);
}

async function shot(name, fullPage = false) {
  await page.screenshot({ path: `${OUT}/${name}.png`, fullPage });
  console.log(`saved ${name}`);
}

async function clickText(text, selector = 'button, a') {
  const clicked = await page.evaluate(
    ({ text, selector }) => {
      const nodes = [...document.querySelectorAll(selector)];
      const element = nodes.find((node) =>
        (node.textContent ?? '').replace(/\s+/g, ' ').includes(text),
      );
      if (!element) {
        return false;
      }
      element.click();
      return true;
    },
    { text, selector },
  );

  if (!clicked) {
    throw new Error(`Не найден элемент: ${text}`);
  }
}

await page.goto(`${base}/`, { waitUntil: 'domcontentloaded' });
await page.waitForSelector('#access-key');
await settle(800);
await shot('01-login-1440');

await page.focus('#access-key');
await page.keyboard.type('PSCDRT2345', { delay: 25 });
await clickText('Войти по ключу');
await page.waitForFunction(() => window.location.pathname === '/users');
await page.waitForSelector('table');
await settle();
await shot('02-users-1440');
await shot('02-users-1440-full', true);

await clickText('Добавить сотрудника');
await settle(350);
await shot('03-user-sheet-1440');
await page.keyboard.press('Escape');
await wait(350);

await clickText('Веб-сканер', 'nav a');
await page.waitForFunction(() => window.location.pathname === '/scanner');
await settle(2600);
await shot('04-scanner-live-1440');

await page.hover('[aria-label^="Рамка дефекта: Трещина корпуса"]');
await wait(350);
await shot('05-scanner-hover-1440');

await page.evaluate(() => {
  const row = [...document.querySelectorAll('button')].find((node) =>
    (node.getAttribute('aria-label') ?? '').startsWith('Дефект: Износ крепления'),
  );
  row?.click();
});
await page.mouse.move(10, 10);
await settle(350);
await shot('06-scanner-selected-1440');

await clickText('Как это работает');
await wait(400);
await page.evaluate(() => {
  document
    .querySelector('[aria-label="Как это работает"]')
    ?.scrollIntoView({ block: 'start' });
});
await wait(300);
await shot('07-how-it-works-1440');

await clickText('Панель диспетчера', 'nav a');
await page.waitForFunction(() => window.location.pathname === '/defects');
await page.evaluate(() => window.scrollTo(0, 0));
await settle();
await shot('08-defects-1440');
await shot('08-defects-1440-full', true);

await page.setViewport({
  width: 390,
  height: 844,
  deviceScaleFactor: 1,
  isMobile: true,
  hasTouch: true,
});
await page.goto(`${base}/defects`, { waitUntil: 'domcontentloaded' });
await page.waitForSelector('h1');
await settle();
await shot('08b-defects-390');
await shot('08c-defects-390-full', true);

await page.goto(`${base}/users`, { waitUntil: 'domcontentloaded' });
await page.waitForSelector('h1');
await settle();
await shot('09-users-390');
await shot('09-users-390-full', true);

await clickText('Добавить сотрудника');
await settle(350);
await shot('09b-user-sheet-390');
await page.keyboard.press('Escape');
await wait(350);

await page.goto(`${base}/scanner`, { waitUntil: 'domcontentloaded' });
await page.waitForSelector('video, [aria-label="Окно камеры"]');
await settle(2600);
await shot('10-scanner-390');

await page.evaluate(() => {
  document.querySelector('#llm-heading')?.scrollIntoView({ block: 'start' });
});
await wait(300);
await shot('10b-scanner-report-390');

await page.evaluate(() => {
  const button = [...document.querySelectorAll('button')].find(
    (node) => (node.textContent ?? '').trim() === 'Передать задачу',
  );
  button?.click();
});
await page.waitForSelector('#report-create-panel');
await page.evaluate(() => {
  document
    .querySelector('#report-create-panel')
    ?.scrollIntoView({ block: 'start' });
});
await wait(300);
await shot('10c-scanner-handoff-390');

await page.setViewport({ width: 768, height: 1024, deviceScaleFactor: 1 });
await page.goto(`${base}/task/report-1042`, { waitUntil: 'domcontentloaded' });
await page.waitForSelector('h1');
await settle();
await shot('10d-task-768');

await page.setViewport({
  width: 390,
  height: 844,
  deviceScaleFactor: 1,
  isMobile: true,
  hasTouch: true,
});
await page.goto(`${base}/scanner`, { waitUntil: 'domcontentloaded' });
await settle(2600);
await page.evaluate(() => {
  const button = [...document.querySelectorAll('button')].find(
    (node) => node.getAttribute('aria-label') === 'Открыть меню',
  );
  button?.click();
});
await wait(350);
await shot('11-menu-390');

await page.evaluate(() => {
  localStorage.clear();
  sessionStorage.clear();
});
await page.goto(`${base}/`, { waitUntil: 'domcontentloaded' });
await page.waitForSelector('#access-key');
await settle();
await shot('12-login-390');

await page.setViewport({ width: 768, height: 1024, deviceScaleFactor: 1 });
await page.goto(`${base}/`, { waitUntil: 'domcontentloaded' });
await page.waitForSelector('#access-key');
await settle();
await shot('13-login-768');

await page.evaluate(() => {
  sessionStorage.setItem(
    'promscan:session:v1',
    JSON.stringify({
      accountId: 'director',
      fullName: 'Генеральный директор',
      email: 'director@promscan.example',
      role: 'director',
      issuedAt: new Date().toISOString(),
    }),
  );
});
await page.goto(`${base}/users`, { waitUntil: 'domcontentloaded' });
await page.waitForSelector('h1');
await settle();
await shot('14-users-768');

await page.goto(`${base}/scanner`, { waitUntil: 'domcontentloaded' });
await settle(2600);
await shot('15-scanner-768');

await page.setViewport({ width: 1024, height: 768, deviceScaleFactor: 1 });
await page.goto(`${base}/scanner`, { waitUntil: 'domcontentloaded' });
await settle(2600);
await shot('16-scanner-1024');
await page.evaluate(() => {
  document.querySelector('#llm-heading')?.scrollIntoView({ block: 'start' });
});
await wait(300);
await shot('16b-scanner-report-1024');

await page.setViewport({ width: 1440, height: 900, deviceScaleFactor: 1 });
await page.goto(`${base}/task/report-1042`, { waitUntil: 'domcontentloaded' });
await page.waitForSelector('h1');
await settle();
await shot('17-task-1440');

await browser.close();
