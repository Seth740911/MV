"""
尚唯全家桶 7x24 守护进程
- 开机自动启动所有服务
- 每60秒检测端口，挂了自动重启
- 日志写到 G:\AI\watchdog.log
- 用 pythonw.exe 运行，无窗口
"""

import subprocess
import socket
import time
import os
import sys
import datetime

# ===== 服务配置 =====
SERVICES = [
    {"name": "云色",   "dir": r"G:\AI\GL",   "port": 8081},
    {"name": "云影",   "dir": r"G:\AI\MV",   "port": 8082},
    {"name": "云音",   "dir": r"G:\AI\YY",   "port": 8083},
    {"name": "云册",   "dir": r"G:\AI\PZ",   "port": 8084},
    {"name": "云听",   "dir": r"G:\AI\QY",   "port": 8085},
    {"name": "FIFA",   "dir": r"G:\AI\FIFA", "port": 8086},
    {"name": "APK下载", "dir": r"G:\AI\APK",  "port": 8888},
]

LOG_FILE = r"G:\AI\watchdog.log"
CHECK_INTERVAL = 60  # 秒
RESTART_DELAY = 3    # 重启前等待秒数

# ===== 日志 =====
def log(msg):
    ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = "[{}] {}".format(ts, msg)
    print(line)
    try:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except:
        pass

# ===== 端口检测 =====
def port_open(port):
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(2)
        s.connect(("127.0.0.1", port))
        s.close()
        return True
    except:
        return False

# ===== 启动单个服务 =====
def start_service(svc):
    server_py = os.path.join(svc["dir"], "server.py")
    if not os.path.isfile(server_py):
        log("[SKIP] {} - server.py 不存在".format(svc["name"]))
        return None
    try:
        proc = subprocess.Popen(
            [sys.executable, server_py],
            cwd=svc["dir"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=subprocess.CREATE_NO_WINDOW,
        )
        log("[START] {} :{} PID={}".format(svc["name"], svc["port"], proc.pid))
        return proc
    except Exception as e:
        log("[FAIL] {} - {}".format(svc["name"], e))
        return None

# ===== 主循环 =====
def main():
    log("=" * 50)
    log("尚唯全家桶守护进程启动")
    log("=" * 50)

    # 进程表 {name: proc}
    procs = {}

    # 首次启动所有服务
    for svc in SERVICES:
        procs[svc["name"]] = start_service(svc)

    # 等5秒让服务起来
    time.sleep(5)

    # 主循环
    while True:
        for svc in SERVICES:
            name = svc["name"]
            port = svc["port"]
            proc = procs.get(name)

            # 检查进程是否还活着
            if proc and proc.poll() is not None:
                log("[DEAD] {} 进程退出, code={}".format(name, proc.returncode))
                procs[name] = None

            # 检查端口
            if not port_open(port):
                log("[DOWN] {} :{} 端口无响应".format(name, port))
                # 杀掉旧进程
                if proc and proc.poll() is None:
                    try:
                        proc.kill()
                        log("[KILL] {} 已终止".format(name))
                    except:
                        pass
                procs[name] = None
                # 等一会再重启
                time.sleep(RESTART_DELAY)
                procs[name] = start_service(svc)
                time.sleep(3)  # 等服务启动

        time.sleep(CHECK_INTERVAL)

if __name__ == "__main__":
    main()
