#!/usr/bin/env node
/**
 * restore-toutiao-ops.js
 * 
 * 将修补后的 toutiao-ops 文件复制到 node_modules
 * 在 npm install 后运行
 */
import { copyFileSync, existsSync, mkdirSync } from 'fs';
import { resolve, dirname } from 'path';
import { fileURLToPath } from 'url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);
const PROJECT_ROOT = resolve(__dirname, '..');
const PATCHED_DIR = resolve(__dirname, 'toutiao-ops-patched');
const TARGET_DIR = resolve(PROJECT_ROOT, 'node_modules/@openclaw-cn/toutiao-ops');

console.log('[restore] 恢复修补后的 toutiao-ops 文件...');

// 复制 index.js
const indexSrc = resolve(PATCHED_DIR, 'index.js');
const indexDst = resolve(TARGET_DIR, 'index.js');
if (existsSync(indexSrc)) {
  copyFileSync(indexSrc, indexDst);
  console.log('  ✅ index.js 已恢复');
} else {
  console.error('  ❌ index.js 源文件不存在');
}

// 复制 src/publish-article.js
const publishArticleSrc = resolve(PATCHED_DIR, 'src', 'publish-article.js');
const publishArticleDst = resolve(TARGET_DIR, 'src', 'publish-article.js');
if (existsSync(publishArticleSrc)) {
  // 确保目标目录存在
  const targetDir = resolve(TARGET_DIR, 'src');
  try {
    mkdirSync(targetDir, { recursive: true });
  } catch {}
  copyFileSync(publishArticleSrc, publishArticleDst);
  console.log('  ✅ src/publish-article.js 已恢复');
} else {
  console.error('  ❌ src/publish-article.js 源文件不存在');
}

console.log('[restore] 完成！');
