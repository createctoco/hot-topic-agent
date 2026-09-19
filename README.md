# 热搜文章生成与手动发布系统

手动触发 → 采集热搜关键词 → DeepSeek AI 生成文章 → 按需发布到今日头条

## 功能

- **多平台热搜采集**：百度、微博、知乎、头条
- **智能关键词过滤**：跨境电商、外贸、AI 三个领域
- **AI 文章生成**：DeepSeek 自动生成标题+2000-3000字正文
- **手动发布**：需要时通过 toutiao-ops 发布到今日头条
- **按需运行**：GitHub Actions 默认不自动发布，需要时手动触发

## 内容安全规则

- 只写积极、建设性、可操作的内容，不写负面、争议、投诉、处罚、诉讼、事故或资本/市值话题。
- 全文禁止出现任何具体企业、品牌、平台、工具、模型、产品、型号或人物名称。
- 如果热搜或来源材料包含具体名称，系统必须删除或替换为“某类工具”“相关平台”“行业通用方法”等类别词。
- 选题、标题、正文和配图关键词都会经过硬性规则检查；违规内容会被拒绝、重写或清洗，不进入发布流程。
- 汽车企业和消费电子品牌相关话题默认不进入候选池。
- `dry_run` 模式不会注入头条 Cookie、不会登录账号，也不会发布内容。

## 项目结构

```
hot-topic-agent/
├── main.py              # 主程序入口
├── config.yaml          # 配置文件
├── run.bat              # Windows 启动脚本
├── publish_helper.js    # Node.js 发布辅助脚本
├── requirements.txt     # Python 依赖
├── package.json         # Node.js 依赖
├── Dockerfile           # Docker 镜像文件
├── docker-compose.yml   # Docker Compose 配置
├── ecosystem.config.cjs # PM2 进程管理配置
├── .env.example         # 环境变量模板
├── modules/
│   ├── hot_search.py    # 热搜采集模块
│   ├── keyword_filter.py# 关键词过滤模块
│   ├── ai_writer.py     # AI 文章生成模块
│   ├── publisher.py     # 头条发布模块
│   └── scheduler.py     # 定时调度模块
├── deploy/
│   ├── baota_deploy.sh  # 宝塔面板部署脚本
│   └── login_local.sh   # 本地登录脚本
├── .github/workflows/
│   └── auto-publish.yml # GitHub Actions 手动工作流
├── data/
│   ├── articles/        # 生成的文章
│   ├── logs/            # 运行日志
│   ├── cache/           # 缓存文件
│   └── published.json   # 发布记录
```

---

## 部署方式

提供三种部署方式，按推荐程度排序：

| 方式 | 推荐度 | 费用 | 适合场景 |
|------|--------|------|---------|
| 宝塔面板（VPS） | ⭐⭐⭐⭐⭐ | VPS费用 | 有服务器、想稳定运行 |
| Docker 部署 | ⭐⭐⭐⭐ | VPS费用 | 有服务器、熟悉 Docker |
| GitHub Actions | ⭐⭐⭐ | 免费 | 没有服务器、想零成本 |

---

### 方式一：宝塔面板部署（推荐）

#### 前提条件
- 一台 VPS/云服务器（1核2G以上，推荐2核4G）
- 已安装宝塔面板
- 能 SSH 连接服务器

#### 步骤 1：上传项目到服务器

```bash
# 在服务器上创建目录
mkdir -p /www/wwwroot/hot-topic-agent
cd /www/wwwroot/hot-topic-agent

# 方法一：从本地 scp 上传
scp -r hot-topic-agent/* root@你的服务器IP:/www/wwwroot/hot-topic-agent/

# 方法二：宝塔面板文件管理上传压缩包后解压
```

#### 步骤 2：运行部署脚本

```bash
cd /www/wwwroot/hot-topic-agent
bash deploy/baota_deploy.sh
```

脚本会自动安装 Python、Node.js、Playwright、PM2。

#### 步骤 3：登录头条（关键步骤）

服务器没有桌面环境，**需要在本地电脑先登录**，再把会话数据传到服务器：

```bash
# 在本地电脑（你的 Windows）执行：
bash deploy/login_local.sh

# 登录成功后，把 data/ 目录传到服务器：
scp -r data/ root@你的服务器IP:/www/wwwroot/hot-topic-agent/
```

#### 步骤 4：启动定时调度

```bash
# 在服务器上启动
pm2 start ecosystem.config.cjs

# 查看状态
pm2 status
pm2 logs hot-topic-agent

# 设置开机自启
pm2 save
pm2 startup
```

#### 步骤 5（可选）：宝塔面板添加计划任务

在宝塔面板 → 计划任务 → 添加：

| 类型 | 脚本 |
|------|------|
| Shell脚本 | `cd /www/wwwroot/hot-topic-agent && python3 main.py --once --count 1` |
| 执行周期 | 每2小时 |

---

### 方式二：Docker 部署

#### 步骤 1：创建 .env 文件

```bash
cp .env.example .env
# 编辑 .env，填入 DeepSeek API Key
vi .env
```

#### 步骤 2：构建并启动

```bash
# 构建镜像
docker-compose build

# 启动（定时调度模式）
docker-compose up -d

# 查看日志
docker-compose logs -f

# 执行一次测试
docker-compose run --rm hot-topic-agent python3 main.py --once --count 1
```

#### 步骤 3：登录头条

```bash
# Docker 内无法扫码，需要从本地复制会话数据
# 在本地登录后，将 data/ 目录挂载到容器中（docker-compose.yml 已配置）
```

---

### 方式三：GitHub Actions 部署（免费）

#### 步骤 1：Fork 或上传项目到 GitHub

```bash
# 初始化 Git 仓库
cd hot-topic-agent
git init
git add .
git commit -m "Initial commit"
git remote add origin https://github.com/你的用户名/hot-topic-agent.git
git push -u origin main
```

#### 步骤 2：配置 GitHub Secrets

在 GitHub 仓库 → Settings → Secrets and variables → Actions → New repository secret：

| Secret 名称 | 值 |
|-------------|---|
| `DEEPSEEK_API_KEY` | 你的 DeepSeek API Key |

#### 步骤 3：手动发布

在 GitHub 仓库 → Actions → "热搜手动发文" → Run workflow

默认 `dry_run=true`，只生成不发布；确认内容符合安全规则后，再显式改为 `false` 才会发布。

#### 步骤 4：按需运行

已移除 GitHub Actions 定时自动发布。需要发文时手动运行工作流，每次默认发布 1 篇。

#### ⚠️ GitHub Actions 限制

| 限制 | 说明 |
|------|------|
| 登录会话 | 首次需要手动处理，用 Cache 持久化会话 |
| 运行时间 | 每次最多30分钟 |
| 免费额度 | 私有仓库2000分钟/月，公开仓库无限 |
| 会话过期 | 头条登录过期后需要重新登录 |

---

## 本地使用

### 快速开始（Windows）

双击 `run.bat`，选择对应功能。

### 手动安装

```bash
# Python 依赖
pip install -r requirements.txt

# Node.js 依赖
npm install
npx playwright install chromium
```

### 配置

编辑 `config.yaml` 或设置环境变量 `DEEPSEEK_API_KEY`。

### 命令

```bash
python main.py --login         # 登录头条
python main.py --test-search   # 测试热搜采集
python main.py --test-filter   # 测试关键词过滤
python main.py --once          # 执行一次完整流程
python main.py --once --count 3  # 执行一次，发3篇
python main.py                 # 启动定时调度
```

---

## 发布方式

已移除 GitHub Actions 定时自动发布。需要发布时，在 GitHub Actions 中手动运行 `热搜手动发文`，或本地执行 `python main.py --once`。发布数量可通过 `--count` 指定。

## 注意事项

1. **DeepSeek API**：需要在 https://platform.deepseek.com/ 注册并充值
2. **头条登录**：登录会过期，需要定期重新扫码
3. **发布频率**：建议每天不超过 10 篇，避免被风控
4. **内容质量**：AI 生成的文章建议定期人工抽查
5. **首发声明**：已开启"头条首发"和"AI生成声明"

## 成本估算

| 部署方式 | 月费用 |
|---------|--------|
| 本地电脑运行 | ¥0（电费除外） |
| VPS（2核4G） | ¥30-60/月 |
| GitHub Actions | ¥0（免费额度内） |
| DeepSeek API | ¥30-90/月 |
