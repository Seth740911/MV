@echo off
echo ===================================
echo  尚唯全家桶 7x24 守护 - 安装
echo ===================================
echo.

echo [1/3] 注册开机自启计划任务...
schtasks /create /tn "ShangWei-Watchdog" /tr "C:\Users\seth\AppData\Local\Programs\Python\Python314\pythonw.exe G:\AI\watchdog.py" /sc onlogon /rl highest /f
if %errorlevel% neq 0 (
    echo [错误] 计划任务注册失败
    pause
    exit /b 1
)
echo [OK] 计划任务已注册

echo.
echo [2/3] 立即启动守护进程...
start "" "C:\Users\seth\AppData\Local\Programs\Python\Python314\pythonw.exe" "G:\AI\watchdog.py"
timeout /t 3 /nobreak >nul

echo.
echo [3/3] 验证服务状态...
netstat -aon | findstr ":8081 :8082 :8083 :8084 :8085 :8086 :8088" | findstr "LISTENING"

echo.
echo ===================================
echo  安装完成！
echo  - 开机自动启动所有服务
echo  - 服务挂了自动重启
echo  - 日志: G:\AI\watchdog.log
echo ===================================
pause
