/**
 * inject-cookies.mjs
 *
 * 在 CI 环境中运行，从 cookies.json 读取 Cookie 并注入到
 * Playwright 持久化浏览器上下文中，使 toutiao-ops 能复用登录会话。
 *
 * 用法：
 *   COOKIES_FILE=data/auth/cookies.json node scripts/inject-cookies.mjs
 */
import { chromium } from 'playwright-extra';
import StealthPlugin from 'puppeteer-extra-plugin-stealth';
import { homedir } from 'os';
import { join } from 'path';
import { mkdirSync, readFileSync, existsSync } from 'fs';

chromium.use(StealthPlugin());

const PROJECT_ROOT = process.cwd();
const userDataDir = join(homedir(), '.toutiao-ops', 'accounts', 'default', 'browser-data');
const cookiesFile = process.env.COOKIES_FILE || join(PROJECT_ROOT, 'data', 'auth', 'cookies.json');

console.log('正在注入 Cookie 到浏览器会话...');
console.log(`  Cookie 文件: ${cookiesFile}`);
console.log(`  浏览器数据目录: ${userDataDir}`);

if (!existsSync(cookiesFile)) {
  console.error('\n❌ Cookie 文件不存在！请先配置 TOUTIAO_COOKIES Secret');
  process.exit(1);
}

let rawData;
try {
  rawData = readFileSync(cookiesFile, 'utf-8');
} catch (err) {
  console.error('\n❌ 读取 Cookie 文件失败:', err.message);
  process.exit(1);
}

let parsed;
try {
  parsed = JSON.parse(rawData);
} catch {
  // 可能是裸数组格式
  try {
    parsed = { cookies: JSON.parse(rawData) };
  } catch (err2) {
    console.error('\n❌ Cookie 文件格式无效:', err2.message);
    process.exit(1);
  }
}

const cookies = parsed.cookies || parsed;
const localStorageData = parsed.localStorage || {};

if (!Array.isArray(cookies) || cookies.length === 0) {
  console.error('\n❌ Cookie 为空或格式不正确');
  process.exit(1);
}

mkdirSync(userDataDir, { recursive: true });

let context;
try {
  context = await chromium.launchPersistentContext(userDataDir, {
    headless: true,
    viewport: { width: 1440, height: 900 },
    locale: 'zh-CN',
    timezoneId: 'Asia/Shanghai',
    args: [
      '--disable-blink-features=AutomationControlled',
      '--no-first-run',
      '--no-default-browser-check',
    ],
    ignoreDefaultArgs: ['--enable-automation'],
  });

  // 注入 Cookie
  await context.addCookies(cookies);

  // 注入 localStorage（如果有）
  if (Object.keys(localStorageData).length > 0) {
    const page = context.pages()[0] || await context.newPage();
    await page.goto('https://mp.toutiao.com/', { waitUntil: 'domcontentloaded', timeout: 30000 }).catch(() => {});

    await page.evaluate((data) => {
      for (const [key, value] of Object.entries(data)) {
        try {
          localStorage.setItem(key, value);
        } catch {}
      }
    }, localStorageData);
  }

  await context.close();

  console.log(`\n✅ 注入成功！`);
  console.log(`   Cookie 数量: ${cookies.length}`);
  console.log(`   localStorage 项: ${Object.keys(localStorageData).length}`);
  console.log(`   浏览器会话已保存到: ${userDataDir}`);
} catch (err) {
  console.error('\n❌ 注入失败:', err.message);
  if (context) await context.close().catch(() => {});
  process.exit(1);
}
