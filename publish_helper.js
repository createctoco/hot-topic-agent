/**
 * toutiao-ops 发布辅助脚本
 * 用法: node publish_helper.js <content_json_file>
 * 
 * content_json_file 格式:
 * {
 *   "title": "文章标题",
 *   "content": "HTML内容",
 *   "first_publish": true,
 *   "ai_declared": true
 * }
 */

const fs = require('fs');
const path = require('path');

async function main() {
    const args = process.argv.slice(2);
    if (args.length < 1) {
        console.error('用法: node publish_helper.js <content_json_file>');
        process.exit(1);
    }

    const contentFile = args[0];
    if (!fs.existsSync(contentFile)) {
        console.error(`文件不存在: ${contentFile}`);
        process.exit(1);
    }

    const articleData = JSON.parse(fs.readFileSync(contentFile, 'utf-8'));
    console.log(`正在发布文章: ${articleData.title}`);

    try {
        // 尝试加载 toutiao-ops
        let toutiaoOps;
        try {
            toutiaoOps = require('@openclaw-cn/toutiao-ops');
        } catch (e) {
            console.error('请先安装 toutiao-ops: npm install @openclaw-cn/toutiao-ops');
            console.error('以及 Playwright: npx playwright install chromium');
            process.exit(1);
        }

        // 发布文章
        const result = await toutiaoOps.publishArticle({
            title: articleData.title,
            content: articleData.content,
            firstPublish: articleData.first_publish || true,
            aiDeclared: articleData.ai_declared || true,
        });

        if (result.success) {
            console.log('发布成功！');
            console.log('文章链接:', result.url || '无');
        } else {
            console.error('发布失败:', result.message || '未知错误');
            process.exit(1);
        }
    } catch (error) {
        console.error('发布过程出错:', error.message);
        process.exit(1);
    }
}

main();
