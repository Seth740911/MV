@echo off
title 尚唯云影库
echo ============================================
echo   尚唯云影库 启动中...
echo ============================================
echo.

cd /d %~dp0

REM 启动网关（自动管理后端）
start "影库网关" python gateway.py

echo.
echo   网关已启动: http://localhost:8052/
echo   按 Ctrl+C 关闭后端，或直接关闭此窗口
echo.
echo ============================================

REM 保持窗口
pause
