import { mkdirSync, readFileSync } from 'fs';
import { join } from 'path';
import { marked } from 'marked';
import { launchBrowser, closeBrowser, sleep, waitForStable, dismissOverlays } from './browser.js';
import { ensureLoggedIn } from './auth-guard.js';

const PUBLISH_URL = 'https://mp.toutiao.com/profile_v4/graphic/publish';
const TITLE_MAX_LEN = 30;
const TITLE_MIN_LEN = 2;

/**
 * 发布图文文章。
 * 参数:
 *   --title          文章标题（必填）
 *   --content        正文文本
 *   --content-file   从文件读取正文
 *   --cover          封面图片路径（必填，单图模式）
 *   --cover-mode     封面模式: single / triple / none（默认 single）
 *   --first-publish  勾选"头条首发"
 *   --collection     添加至合集名称
 *   --no-weitoutiao  取消"同时发布微头条"
 *   --declaration    作品声明，逗号分隔
 *   --draft          存草稿
 */
export async function publishArticle(opts) {
  const { context, page } = await launchBrowser(opts);
  try {
    await ensureLoggedIn(page);
    await page.goto(PUBLISH_URL, { waitUntil: 'domcontentloaded', timeout: 30000 });
    await waitForStable(page);
    await sleep(1500, 2500);
    await dismissOverlays(page);

    // ── 标题（2~30 字） ──
    let title = opts.title;
    if (title.length < TITLE_MIN_LEN) {
      throw new Error(`标题过短：至少 ${TITLE_MIN_LEN} 个字，当前 ${title.length} 个字`);
    }
    if (title.length > TITLE_MAX_LEN) {
      title = title.slice(0, TITLE_MAX_LEN);
      process.stderr.write(`[warn] 标题超过 ${TITLE_MAX_LEN} 字限制，已自动截断为：${title}\n`);
    }
    const titleSelector = 'textarea[placeholder*="标题"], input[placeholder*="标题"], [class*="title"] textarea, [class*="title"] input';
    await page.waitForSelector(titleSelector, { timeout: 15000 });
    await sleep(300, 600);
    await page.click(titleSelector, { force: true });
    await page.keyboard.type(title, { delay: 50 + Math.random() * 80 });
    await sleep(500, 1000);

    // ── 正文 ──
    let content = opts.content || '';
    if (opts.contentFile) {
      content = readFileSync(opts.contentFile, 'utf-8');
    }
    content = content.replace(/\\n/g, '\n');
    if (content) {
      const editorSelector = '[contenteditable="true"]';
      await page.waitForSelector(editorSelector, { timeout: 15000 });
      await sleep(300, 600);
      await page.click(editorSelector, { force: true });
      await sleep(200, 400);

      if (opts.format === 'markdown' || opts.contentFile?.match(/\.md$/i)) {
        await pasteMarkdownAsRichText(page, content, editorSelector);
      } else {
        await typePlainText(page, content);
      }
    }
    await sleep(500, 1000);

    // ── 展示封面 ──
    await setCoverMode(page, opts.coverMode || 'single', opts.cover, opts.coverKeyword || '');
    await sleep(500, 1000);

    // ── 声明首发 ──
    if (opts.firstPublish) {
      await clickLabel(page, '头条首发');
    }
    await sleep(300, 500);

    // ── 合集 ──
    if (opts.collection) {
      await addToCollection(page, opts.collection);
    }
    await sleep(300, 500);

    // ── 同时发布微头条（默认已勾选，--no-weitoutiao 取消） ──
    if (opts.weitoutiao === false) {
      await uncheckWeitoutiao(page);
    }
    await sleep(300, 500);

    // ── 作品声明 ──
    if (opts.declaration) {
      await setDeclarations(page, opts.declaration);
    }
    await sleep(500, 1000);

    // ── 发布 / 草稿 ──
    await dismissOverlays(page);
    if (opts.draft) {
      // 页面底部没有独立草稿按钮，草稿已自动保存
      return {
        success: true,
        action: 'draft_saved',
        title,
        url: page.url(),
      };
    }

    // Click preview/publish and require observable confirmation. The upstream
    // implementation swallowed missing confirmation buttons and returned a
    // false success even though no article had been published.
    await dismissOverlays(page);
    const publishBtn = page.locator('button:has-text("预览并发布")').first();
    await publishBtn.waitFor({ state: 'visible', timeout: 15000 });
    await publishBtn.scrollIntoViewIfNeeded();
    await sleep(300, 500);
    await publishBtn.click({ force: true, timeout: 10000 });
    await sleep(3000, 5000);
    await waitForStable(page);

    // The preview page normally requires a second confirmation. Some account
    // variants publish directly, so first check for an already completed flow.
    let published = await hasPublishConfirmation(page);
    const confirmPublish = page.locator('button:has-text("确认发布"), button:has-text("发布")').first();
    if (!published && await confirmPublish.isVisible({ timeout: 10000 }).catch(() => false)) {
      await confirmPublish.click({ timeout: 10000 });
      await sleep(2000, 4000);
    }

    // Optional secondary modal.
    const confirmBtn = page.locator('button:has-text("确定"), button:has-text("确认")').first();
    if (await confirmBtn.isVisible({ timeout: 3000 }).catch(() => false)) {
      await confirmBtn.click({ timeout: 5000 });
    }

    published = await waitForPublishConfirmation(page, 20000);
    if (!published) {
      const pageError = await readVisiblePublishError(page);
      const screenshot = await capturePublishFailure(page);
      throw new Error(
        `Toutiao did not confirm publication${pageError ? `: ${pageError}` : ''}. ` +
        `Current URL: ${page.url()}. Screenshot: ${screenshot}`
      );
    }

    return {
      success: true,
      action: 'published',
      title,
      url: page.url(),
    };
  } finally {
    await closeBrowser(context);
  }
}

async function setCoverMode(page, mode, coverPath, coverKeyword = '') {
  try {
    const modeLabels = {
      single: '单图',
      triple: '三图',
      none: '无封面',
    };
    // Free-library images still use the single-cover layout. "免费图库" is
    // a tab inside the image picker, not a cover-mode radio on the main page.
    const label = mode === 'free' ? modeLabels.single : (modeLabels[mode] || modeLabels.single);

    const radio = page.locator(`text=${label}`).first();
    await radio.click({ timeout: 5000 });
    await sleep(500, 800);

    if (mode === 'free') {
      await openCoverPanel(page);
      await selectFromFreeLibrary(page, coverKeyword);
    } else if (mode !== 'none' && coverPath) {
      const paths = coverPath.split(',').map(p => p.trim()).filter(Boolean);

      await openCoverPanel(page);

      // 侧边栏打开后，点击"本地上传"按钮触发文件选择
      const [fileChooser] = await Promise.all([
        page.waitForEvent('filechooser', { timeout: 10000 }),
        page.locator('text=本地上传').first().click({ timeout: 5000 }),
      ]);

      if (fileChooser) {
        await fileChooser.setFiles(paths);
        await sleep(3000, 5000);
      }

      // 等待图片上传完成，点击"确定"关闭侧边栏
      const confirmBtn = page.locator('.byte-drawer-wrapper button:has-text("确定"), .upload-image-panel button:has-text("确定")').first();
      await confirmBtn.waitFor({ timeout: 10000 });
      await sleep(500, 800);
      await confirmBtn.click();
      await sleep(1000, 2000);
    }
  } catch (error) {
    // 封面上传失败，尝试关闭可能残留的侧边栏
    await page.locator('.byte-drawer-wrapper button:has-text("取消")').first()
      .click({ timeout: 3000 }).catch(() => {});
    await page.keyboard.press('Escape').catch(() => {});
    await sleep(500, 800);
    if (mode === 'free') {
      console.warn(`[free-library] 免费正版图库不可用，自动切换为无封面: ${error.message}`);
      const noCover = page.getByText('无封面', { exact: true }).first();
      await noCover.click({ timeout: 5000 });
      await sleep(500, 800);
      return;
    }
    if (mode !== 'none' && coverPath) {
      throw new Error(`Cover selection failed: ${error.message}`);
    }
  }
}

async function openCoverPanel(page) {
  const coverArea = page.locator(
    '[class*="cover"] [class*="add"], [class*="cover"] [class*="upload"], ' +
    '[class*="cover"] [class*="plus"], [class*="cover-upload"]'
  ).first();
  await coverArea.waitFor({ state: 'visible', timeout: 10000 });
  await coverArea.click({ timeout: 10000 });
  await sleep(1000, 2000);
}

async function hasPublishConfirmation(page) {
  const success = page.getByText(/发布成功|提交成功|已发布/).first();
  if (await success.isVisible({ timeout: 1000 }).catch(() => false)) return true;
  const url = page.url();
  if (url.includes('/auth/') || url.includes('sso.toutiao.com')) return false;
  return /profile_v4\/(graphic\/)?(content|manage|home)/.test(url);
}

async function waitForPublishConfirmation(page, timeoutMs) {
  const deadline = Date.now() + timeoutMs;
  while (Date.now() < deadline) {
    if (await hasPublishConfirmation(page)) return true;
    await page.waitForTimeout(500);
  }
  return false;
}

async function readVisiblePublishError(page) {
  const selectors = [
    '.byte-message-error',
    '.byte-notification-error',
    '[class*="error"]',
    '[role="alert"]',
  ];
  for (const selector of selectors) {
    const item = page.locator(selector).first();
    if (await item.isVisible({ timeout: 300 }).catch(() => false)) {
      const text = (await item.innerText().catch(() => '')).trim();
      if (text) return text.slice(0, 500);
    }
  }
  return '';
}

async function capturePublishFailure(page) {
  const directory = join(process.cwd(), 'data', 'logs');
  mkdirSync(directory, { recursive: true });
  const target = join(directory, `toutiao-publish-failed-${Date.now()}.png`);
  await page.screenshot({ path: target, fullPage: true }).catch(() => {});
  return target;
}

async function selectFromFreeLibrary(page, keyword) {
  try {
    console.log('[free-library] 正在使用免费图库，关键词:', keyword);
    await sleep(1000, 2000);
    
    // Different editor variants use "免费图库", "免费正版图库" or
    // "免费正版图片" for the same licensed-image picker.
    const freeTab = page.getByText(/免费(?:正版)?(?:图库|图片)/).first();
    await freeTab.waitFor({ state: 'visible', timeout: 10000 });
    await freeTab.click({ timeout: 5000 });
    await sleep(1500, 2500);
    
    // 在搜索框输入关键词
    const searchInput = page.locator(
      '.byte-drawer-wrapper input[placeholder*="搜索"], ' +
      '[class*="image"] input[placeholder*="搜索"], [class*="library"] input'
    ).first();
    await searchInput.fill(keyword || '科技', { timeout: 5000 });
    await sleep(500, 800);
    await page.keyboard.press('Enter');
    await sleep(2500, 3500);
    
    // 选择第一张图片
    const firstImage = page.locator('[class*="image-item"], [class*="img-item"], [class*="library"] img').first();
    await firstImage.click({ timeout: 10000 });
    await sleep(1000, 2000);
    
    // 点击"确定"确认选择
    const confirmBtn = page.locator('button:has-text("确定"), button:has-text("确认")').first();
    await confirmBtn.click({ timeout: 5000 });
    await sleep(1000, 2000);
    console.log('[free-library] 免费图库选择完成');
  } catch (e) {
    console.error('[free-library] 免费图库选择失败:', e.message);
    throw e;
  }
}

async function addToCollection(page, collectionName) {
  try {
    const addBtn = page.locator('text=添加至合集').first();
    await addBtn.click({ timeout: 5000 });
    await sleep(500, 1000);

    // 在弹出的合集选择面板中搜索或选择
    const searchInput = page.locator('[class*="collection"] input, [class*="search"] input').first();
    await searchInput.fill(collectionName, { timeout: 5000 }).catch(async () => {
      // 没有搜索框，直接找匹配的合集名
    });
    await sleep(500, 1000);

    const item = page.locator(`text=${collectionName}`).first();
    await item.click({ timeout: 5000 });
    await sleep(300, 600);

    // 点确认
    const confirmBtn = page.locator('button:has-text("确定"), button:has-text("确认")').first();
    await confirmBtn.click({ timeout: 3000 }).catch(() => {});
  } catch {
    // 合集添加失败不阻塞
  }
}

async function uncheckWeitoutiao(page) {
  try {
    // "同时发布微头条" 默认已勾选，点击取消
    const checkbox = page.locator('text=发布得更多收益').first();
    await checkbox.click({ timeout: 5000 });
    await sleep(200, 400);
  } catch {
    // 取消失败不阻塞
  }
}

async function clickLabel(page, labelText) {
  try {
    const el = page.locator(`text=${labelText}`).first();
    await el.scrollIntoViewIfNeeded().catch(() => {});
    await el.click({ timeout: 5000 });
    await sleep(200, 400);
  } catch {}
}

async function setDeclarations(page, declarationStr) {
  const declarations = declarationStr.split(',').map(d => d.trim()).filter(Boolean);
  const labelMap = {
    '取材网络': '取材网络',
    '引用站内': '引用站内',
    '个人观点': '个人观点，仅供参考',
    '引用AI': '引用AI',
    '虚构演绎': '虚构演绎，故事经历',
    '投资观点': '投资观点，仅供参考',
    '健康医疗': '健康医疗分享，仅供参考',
  };

  for (const decl of declarations) {
    const fullLabel = labelMap[decl] || decl;
    try {
      const checkbox = page.locator(`text=${fullLabel}`).first();
      await checkbox.scrollIntoViewIfNeeded().catch(() => {});
      await checkbox.click({ timeout: 3000 });
      await sleep(200, 400);
    } catch {}
  }
}

async function pasteMarkdownAsRichText(page, markdownContent, editorSelector) {
  const html = marked.parse(markdownContent, { breaks: true, gfm: true });
  await page.evaluate(
    ({ html, selector }) => {
      const editor = document.querySelector(selector);
      if (!editor) return;
      editor.focus();
      const dt = new DataTransfer();
      dt.setData('text/html', html);
      dt.setData('text/plain', editor.textContent);
      const evt = new ClipboardEvent('paste', {
        clipboardData: dt,
        bubbles: true,
        cancelable: true,
      });
      editor.dispatchEvent(evt);
    },
    { html, selector: editorSelector },
  );
  await sleep(500, 1000);
}

async function typePlainText(page, content) {
  const paragraphs = content.split('\n');
  for (let i = 0; i < paragraphs.length; i++) {
    const para = paragraphs[i];
    if (para) {
      await page.keyboard.type(para, { delay: 30 + Math.random() * 50 });
    }
    if (i < paragraphs.length - 1) {
      await page.keyboard.press('Enter');
      await sleep(100, 300);
    }
  }
}
