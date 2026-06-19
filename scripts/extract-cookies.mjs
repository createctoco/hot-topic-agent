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
import { homedir } from 'os';
import { join } from 'path';
import { mkdirSync, writeFileSync, existsSync } from 'fs';

chromium.use(StealthPlugin());

const PROJECT_ROOT = process.cwd();
const userDataDir = join(homedir(), '.toutiao-ops', 'accounts', 'default', 'browser-data');

console.log('正在从浏览器会话提取 Cookie...');
console.log(`浏览器数据目录: ${userDataDir}`);

if (!existsSync(userDataDir)) {
  console.error('\n❌ 未找到浏览器会话数据！');
  console.error('请先运行登录: npx toutiao-ops auth login');
  process.exit(1);
}

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

  // 提取所有 Cookie
  const cookies = await context.cookies();

  // 也提取 localStorage 中的关键信息
  const pages = context.pages();
  let localStorageData = {};
  if (pages.length > 0) {
    try {
      localStorageData = await pages[0].evaluate(() => {
        const data = {};
        for (let i = 0; i < localStorage.length; i++) {
          const key = localStorage.key(i);
          data[key] = localStorage.getItem(key);
        }
        return data;
      });
    } catch {
      // localStorage 可能为空，忽略
    }
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
  console.log(`\n📋 下一步：`);
  console.log(`   1. 打开 ${outputPath}`);
  console.log(`   2. 复制全部内容`);
  console.log(`   3. 在 GitHub 仓库 Settings → Secrets → Actions 中添加 TOUTIAO_COOKIES`);
} catch (err) {
  console.error('\n❌ 提取失败:', err.message);
  if (context) await context.close().catch(() => {});
  process.exit(1);
}
