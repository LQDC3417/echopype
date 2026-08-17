@echo off
chcp 65001 >nul
title DSH Web 启动器（自动开浏览器）
echo ============================================
echo   DeepSeek Harness Web 一键启动
echo   启动后自动打开浏览器
echo ============================================
echo.

REM 切换到项目目录（可修改为你常用的工作目录）
cd /d "D:\Administrator\Desktop\echopype"

REM 延迟 3 秒后自动打开浏览器（等服务起来）
start "" cmd /c "timeout /t 3 /nobreak >nul && start http://127.0.0.1:3080"

echo 正在启动 DSH Web 服务...
echo 3 秒后自动打开浏览器...
echo 提示：按 Ctrl+C 可停止服务
echo.
npx @deepseek-ai/dsh web

echo.
echo DSH 服务已停止。
pause
