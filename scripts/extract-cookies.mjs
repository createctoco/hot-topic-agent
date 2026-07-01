/**
 * extract-cookies.mjs
 *
 * 本地登录头条后运行此脚本，从浏览器持久化会话中提取 Cookie，
 * 保存为 JSON 文件，供 GitHub Actions Secret 使用。
 *
 * 用法：
 *   node scripts/extract-cookies.mjs
 *
 * 输出：data/auth/cookies.json
 */
import { chromium } from 'playwright-extra';
import StealthPlugin from 'puppeteer-extra-plugin-stealth';
import { join } from 'path';
import { mkdirSync, writeFileSync, existsSync } from 'fs';

chromium.use(StealthPlugin());

const PROJECT_ROOT = process.cwd();
const userDataDir = process.env.TOUTIAO_PROFILE_DIR ||
  join(PROJECT_ROOT, 'data', 'auth', 'browser-profile');

const browserCandidates = process.platform === 'win32'
  ? [
      process.env.TOUTIAO_BROWSER_EXECUTABLE,
      'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe',
      'C:\\Program Files (x86)\\Google\\Chrome\\Application\\chrome.exe',
      'C:\\Program Files\\Microsoft\\Edge\\Application\\msedge.exe',
      'C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe',
    ]
  : [process.env.TOUTIAO_BROWSER_EXECUTABLE];
const executablePath = browserCandidates.find(path => path && existsSync(path));

console.log('正在从浏览器会话提取 Cookie...');
console.log(`浏览器数据目录: ${userDataDir}`);

mkdirSync(userDataDir, { recursive: true });

let context;
try {
  context = await chromium.launchPersistentContext(userDataDir, {
    headless: false,
    ...(executablePath ? { executablePath } : {}),
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

  const page = context.pages()[0] || await context.newPage();
  await page.goto('https://mp.toutiao.com/', {
    waitUntil: 'domcontentloaded',
    timeout: 30000,
  });
  await page.waitForTimeout(3000);

  if (!await isCreatorDashboard(page)) {
    console.log('\n请在打开的浏览器中使用今日头条 App 扫码登录。');
    console.log('登录成功后脚本会自动继续，最长等待 5 分钟。');
    const deadline = Date.now() + 300000;
    let loggedIn = false;
    while (Date.now() < deadline) {
      await page.waitForTimeout(1000);
      if (await isCreatorDashboard(page)) {
        loggedIn = true;
        break;
      }
    }
    if (!loggedIn) throw new Error('等待扫码登录超时。');
  }

  await page.waitForLoadState('domcontentloaded').catch(() => {});
  await page.waitForTimeout(1500);

  // 提取所有 Cookie
  const cookies = (await context.cookies()).filter(cookie =>
    cookie.domain === 'toutiao.com' || cookie.domain.endsWith('.toutiao.com')
  );

  // 也提取 localStorage 中的关键信息
  let localStorageData = {};
  try {
    localStorageData = await page.evaluate(() => {
      const data = {};
      const blockedFragments = [
        'runtime_cache',
        'runtime_switcher',
        'console_logs',
        'slardar',
      ];
      for (let i = 0; i < localStorage.length; i++) {
        const key = localStorage.key(i);
        const normalized = key.toLowerCase();
        const value = localStorage.getItem(key) || '';
        if (blockedFragments.some(fragment => normalized.includes(fragment))) continue;
        if (new TextEncoder().encode(value).length > 8192) continue;
        data[key] = value;
      }
      return data;
    });
  } catch {
    // localStorage 可能为空，忽略
  }

  await context.close();

  // 保存
  const outputDir = join(PROJECT_ROOT, 'data', 'auth');
  mkdirSync(outputDir, { recursive: true });

  const outputPath = join(outputDir, 'cookies.json');
  const outputData = {
    cookies: cookies,
    localStorage: localStorageData,
    extracted_at: new Date().toISOString(),
  };

  writeFileSync(outputPath, JSON.stringify(outputData, null, 2));

  console.log(`\n✅ 提取成功！`);
  console.log(`   Cookie 数量: ${cookies.length}`);
  console.log(`   localStorage 项: ${Object.keys(localStorageData).length}`);
  console.log(`   保存到: ${outputPath}`);
  console.log(`\n下一步：将该文件写入 GitHub Secret TOUTIAO_COOKIES。`);
} catch (err) {
  console.error('\n❌ 提取失败:', err.message);
  if (context) await context.close().catch(() => {});
  process.exit(1);
}

async function isCreatorDashboard(page) {
  const url = page.url();
  if (!url.includes('/profile_v4') || url.includes('/auth/')) return false;
  return page.locator(
    '[class*="sidebar"], [class*="sider"], a[href*="graphic/publish"]'
  ).first().isVisible({ timeout: 2000 }).catch(() => false);
}
