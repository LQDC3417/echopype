@echo off
chcp 65001 >nul
title DSH Web 启动器
echo ============================================
echo   DeepSeek Harness Web 一键启动
echo ============================================
echo.

REM 切换到项目目录（可修改为你常用的工作目录）
cd /d "D:\Administrator\Desktop\echopype"

REM 启动 DSH Web 服务
echo 正在启动 DSH Web 服务...
echo 启动完成后请打开浏览器访问 http://127.0.0.1:3080
echo.
echo 提示：按 Ctrl+C 可停止服务
echo.
npx @deepseek-ai/dsh web

echo.
echo DSH 服务已停止。
pause
