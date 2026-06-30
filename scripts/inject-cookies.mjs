/**
 * inject-cookies.mjs
 *
 * 在 CI 环境中运行，从 cookies.json 读取 Cookie 并注入到
 * Playwright 持久化浏览器上下文中，使 toutiao-ops 能复用登录会话。
 *
 * 用法：
 *   node scripts/inject-cookies.mjs
 *
 * 环境变量：
 *   COOKIES_FILE - Cookie 文件路径（默认 data/auth/cookies.json）
 *   TOUTIAO_ACCOUNT - 账号名（默认 default）
 */
import { chromium } from 'playwright';
import { homedir } from 'os';
import { join, resolve } from 'path';
import { mkdirSync, readFileSync, existsSync } from 'fs';

const PROJECT_ROOT = process.cwd();
const account = process.env.TOUTIAO_ACCOUNT || 'default';
const userDataDir = join(homedir(), '.toutiao-ops', 'accounts', account, 'browser-data');
const cookiesFile = resolve(process.env.COOKIES_FILE || join(PROJECT_ROOT, 'data', 'auth', 'cookies.json'));

console.log('正在注入 Cookie 到浏览器会话...');
console.log(`  Cookie 文件: ${cookiesFile}`);
console.log(`  浏览器数据目录: ${userDataDir}`);

if (!existsSync(cookiesFile)) {
  console.error('\n❌ Cookie 文件不存在！请先配置 TOUTIAO_COOKIES Secret');
  process.exit(1);
}

let parsed;
try {
  const rawData = readFileSync(cookiesFile, 'utf-8');
  parsed = JSON.parse(rawData);
} catch (err) {
  console.error('\n❌ 读取/解析 Cookie 文件失败:', err.message);
  process.exit(1);
}

const cookies = parsed.cookies || parsed;
const localStorageData = parsed.localStorage || {};

if (!Array.isArray(cookies) || cookies.length === 0) {
  console.error('\n❌ Cookie 为空或格式不正确');
  process.exit(1);
}

// 确保目录存在
mkdirSync(userDataDir, { recursive: true });

let browser;
try {
  // 启动持久化浏览器上下文（与 toutiao-ops 使用相同的 userDataDir）
  browser = await chromium.launchPersistentContext(userDataDir, {
    headless: true,
    viewport: { width: 1440, height: 900 },
    locale: 'zh-CN',
    timezoneId: 'Asia/Shanghai',
    args: [
      '--disable-blink-features=AutomationControlled',
      '--no-first-run',
      '--no-default-browser-check',
    ],
  });

  const pages = browser.pages();
  const page = pages.length > 0 ? pages[0] : await browser.newPage();

  // 先访问头条域名，使 Cookie 能正确设置
  await page.goto('https://www.toutiao.com/', { waitUntil: 'domcontentloaded', timeout: 30000 }).catch(() => {});

  // 注入 Cookie
  await page.context().addCookies(cookies);

  // 注入 localStorage（如果有）
  if (Object.keys(localStorageData).length > 0) {
    await page.goto('https://mp.toutiao.com/', { waitUntil: 'domcontentloaded', timeout: 30000 }).catch(() => {});
    await page.evaluate((data) => {
      for (const [key, value] of Object.entries(data)) {
        try { localStorage.setItem(key, value); } catch {}
      }
    }, localStorageData);
  }

  await browser.close();

  console.log(`\n✅ 注入成功！`);
  console.log(`   Cookie 数量: ${cookies.length}`);
  console.log(`   localStorage 项: ${Object.keys(localStorageData).length}`);
  console.log(`   浏览器会话已保存到: ${userDataDir}`);
  console.log(`\n下一步：运行 npx @openclaw-cn/toutiao-ops auth check --headless 验证登录状态`);
} catch (err) {
  console.error('\n❌ 注入失败:', err.message);
  if (browser) await browser.close().catch(() => {});
  process.exit(1);
}
