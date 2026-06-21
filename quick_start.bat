@echo off
chcp 65001 >nul
title 尚唯云册 - 快速启动

echo ============================================
echo   尚唯云册 - 快速启动脚本
echo ============================================
echo.

cd /d "G:\AI\PZ"

echo [1/3] 检查 Python 环境...
python --version >nul 2>&1
if errorlevel 1 (
    echo 错误: 未找到 Python，请先安装 Python 3.x
    pause
    exit /b 1
)
echo   ✓ Python 已安装
echo.

echo [2/3] 检查数据文件...
if not exist "data\search_index.json" (
    echo   正在构建搜索索引...
    python search_engine.py --build
) else (
    echo   ✓ 搜索索引已存在
)

if not exist "data\timeline.json" (
    echo   正在生成时间轴...
    python timeline_generator.py --timeline
) else (
    echo   ✓ 时间轴已存在
)
echo.

echo [3/3] 启动服务...
echo   端口: 8084
echo   访问地址: http://192.168.0.100:8084
echo.
echo   按 Ctrl+C 可停止服务
echo ============================================
echo.

python server.py --port 8084

pause
