#!/usr/bin/env node
/* Restore the repository's compatibility patch after every npm install. */

const { copyFileSync, existsSync, mkdirSync } = require('fs');
const { resolve } = require('path');

const projectRoot = resolve(__dirname, '..');
const patchedDir = resolve(__dirname, 'toutiao-ops-patched');
const targetDir = resolve(projectRoot, 'node_modules', '@openclaw-cn', 'toutiao-ops');
const files = ['index.js', 'src/publish-article.js'];

if (!existsSync(targetDir)) {
  console.error(`[restore] toutiao-ops is missing: ${targetDir}`);
  process.exit(1);
}

for (const relativePath of files) {
  const source = resolve(patchedDir, relativePath);
  const target = resolve(targetDir, relativePath);
  if (!existsSync(source)) {
    console.error(`[restore] patch file is missing: ${source}`);
    process.exit(1);
  }
  mkdirSync(resolve(target, '..'), { recursive: true });
  copyFileSync(source, target);
  console.log(`[restore] ${relativePath}`);
}
