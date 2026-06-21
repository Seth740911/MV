@echo off
chcp 65001 >nul
echo ============================================================
echo   TMDB 电影刮削脚本
echo ============================================================
echo.

REM 检查 Python
set PYTHON=C:\Users\seth\AppData\Local\Programs\Python\Python314\python.exe
if not exist "%PYTHON%" (
    echo [错误] 找不到 Python: %PYTHON%
    echo 请确认 Python 安装路径是否正确
    pause
    exit /b 1
)

REM 安装依赖
echo [1/3] 检查依赖包...
"%PYTHON%" -m pip install requests openpyxl pillow --quiet --timeout 60 -i https://pypi.tuna.tsinghua.edu.cn/simple/ 2>nul

REM 运行脚本
echo.
echo [2/3] 开始刮削电影数据...
echo ============================================================
echo 提示：每部电影间隔0.25秒，1855部约需50分钟
echo 可以最小化窗口去做别的事，Ctrl+C 可中断（进度已自动保存）
echo ============================================================
echo.
"%PYTHON%" "G:\AI\MV\tmdb_scraper.py"

echo.
echo [3/3] 运行结束，按任意键关闭窗口...
pause >nul
