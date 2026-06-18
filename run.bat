@echo off
chcp 65001 >nul
title 热搜自动发文系统

echo ============================================
echo   热搜自动发文系统
echo   跨境电商 / 外贸 / AI / 科技
echo ============================================
echo.

cd /d "%~dp0"

:menu
echo 请选择操作:
echo   [1] 立即执行一次（测试）
echo   [2] 启动定时调度（每天10篇）
echo   [3] 登录今日头条
echo   [4] 测试热搜采集
echo   [5] 测试关键词过滤
echo   [6] 安装依赖
echo   [0] 退出
echo.
set /p choice=请输入选项: 

if "%choice%"=="1" goto run_once
if "%choice%"=="2" goto run_scheduler
if "%choice%"=="3" goto login
if "%choice%"=="4" goto test_search
if "%choice%"=="5" goto test_filter
if "%choice%"=="6" goto install
if "%choice%"=="0" exit
goto menu

:run_once
echo.
echo 正在执行一次完整流程...
python main.py --once
echo.
pause
goto menu

:run_scheduler
echo.
echo 启动定时调度...
python main.py
pause
goto menu

:login
echo.
echo 正在启动头条登录...
python main.py --login
echo.
pause
goto menu

:test_search
echo.
echo 测试热搜采集...
python main.py --test-search
echo.
pause
goto menu

:test_filter
echo.
echo 测试关键词过滤...
python main.py --test-filter
echo.
pause
goto menu

:install
echo.
echo 安装 Python 依赖...
pip install -r requirements.txt
echo.
echo 安装 Node.js 依赖...
call npm install
echo.
echo 安装 Playwright 浏览器...
call npx playwright install chromium
echo.
echo 依赖安装完成！
pause
goto menu
