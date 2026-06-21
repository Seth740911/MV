#!/usr/bin/env python3
"""
尚唯云影 按需启动网关
- 轻量级常驻进程，监听 8052 端口
- 有局域网请求时自动唤醒 server.py（8082 端口）
- 闲置 5 分钟后自动关闭 server.py 释放资源
- 所有请求透明代理到后端
"""

import http.server
import socketserver
import subprocess
import urllib.request
import urllib.error
import threading
import time
import sys
import os

GATEWAY_PORT = 8052
BACKEND_PORT = 8082
MV_DIR = os.path.dirname(os.path.abspath(__file__))
IDLE_TIMEOUT = 300  # 5 分钟无请求后关闭后端


class GatewayHandler(http.server.SimpleHTTPRequestHandler):
    backend_process = None
    lock = threading.Lock()
    idle_timer = None
    last_request_time = 0

    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=MV_DIR, **kwargs)

    def _ensure_backend(self):
        with GatewayHandler.lock:
            now = time.time()
            if GatewayHandler.idle_timer:
                GatewayHandler.idle_timer.cancel()
                GatewayHandler.idle_timer = None

            if GatewayHandler.backend_process is None or GatewayHandler.backend_process.poll() is not None:
                print(f'  → 启动后端服务器（端口 {BACKEND_PORT}）...')
                GatewayHandler.backend_process = subprocess.Popen(
                    [sys.executable, 'server.py', '--port', str(BACKEND_PORT), '--quiet'],
                    cwd=MV_DIR,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL
                )
                for _ in range(30):
                    try:
                        urllib.request.urlopen(f'http://127.0.0.1:{BACKEND_PORT}/', timeout=0.1)
                        break
                    except Exception:
                        time.sleep(0.1)
                print(f'  ✓ 后端已就绪')

            GatewayHandler.last_request_time = now

    def _schedule_idle_shutdown(self):
        with GatewayHandler.lock:
            if GatewayHandler.idle_timer:
                GatewayHandler.idle_timer.cancel()

            def shutdown():
                with GatewayHandler.lock:
                    if time.time() - GatewayHandler.last_request_time >= IDLE_TIMEOUT:
                        if GatewayHandler.backend_process and GatewayHandler.backend_process.poll() is None:
                            print(f'  ⏸ 闲置 {IDLE_TIMEOUT}s，关闭后端服务器...')
                            GatewayHandler.backend_process.terminate()
                            try:
                                GatewayHandler.backend_process.wait(timeout=3)
                            except subprocess.TimeoutExpired:
                                GatewayHandler.backend_process.kill()
                            GatewayHandler.backend_process = None
                            print(f'  ✓ 后端已休眠')

            GatewayHandler.idle_timer = threading.Timer(IDLE_TIMEOUT, shutdown)
            GatewayHandler.idle_timer.daemon = True
            GatewayHandler.idle_timer.start()

    def _proxy_request(self, method='GET', body=None):
        try:
            self._ensure_backend()
            backend_url = f'http://127.0.0.1:{BACKEND_PORT}{self.path}'

            headers = {k: v for k, v in self.headers.items()
                       if k.lower() not in ('host', 'connection')}

            if method == 'POST' and body is None:
                content_length = int(self.headers.get('Content-Length', 0))
                body = self.rfile.read(content_length) if content_length > 0 else None

            req = urllib.request.Request(backend_url, data=body, headers=headers,
                                         method=method)

            try:
                resp = urllib.request.urlopen(req, timeout=300)
                self.send_response(resp.status)
                for header, value in resp.getheaders():
                    if header.lower() not in ('transfer-encoding', 'connection'):
                        self.send_header(header, value)
                # 开发阶段：所有请求禁用缓存，确保刷新即更新
                self.send_header('Cache-Control', 'no-cache, no-store, must-revalidate')
                self.send_header('Pragma', 'no-cache')
                self.send_header('Expires', '0')
                self.end_headers()
                while True:
                    chunk = resp.read(65536)
                    if not chunk:
                        break
                    self.wfile.write(chunk)
            except urllib.error.HTTPError as e:
                self.send_response(e.code)
                self.end_headers()
            except urllib.error.URLError:
                self.send_response(502)
                self.send_header('Content-Type', 'text/plain')
                self.end_headers()
                self.wfile.write(b'Backend unavailable')

            self._schedule_idle_shutdown()
        except (ConnectionResetError, BrokenPipeError, ConnectionAbortedError):
            pass

    def do_GET(self):
        self._proxy_request('GET')

    def do_HEAD(self):
        self._proxy_request('GET')

    def do_POST(self):
        content_length = int(self.headers.get('Content-Length', 0))
        body = self.rfile.read(content_length) if content_length > 0 else None
        self._proxy_request('POST', body)

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Range, Content-Type')
        self.end_headers()

    def log_message(self, format, *args):
        mode = 'RUN' if GatewayHandler.backend_process and GatewayHandler.backend_process.poll() is None else 'SLEEP'
        sys.stdout.write(f"{mode} {self.log_date_time_string()}  {args[0]}\n")
        sys.stdout.flush()


if __name__ == '__main__':
    import socket

    def _kill_port(p):
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(1)
            if sock.connect_ex(('127.0.0.1', p)) == 0:
                print(f'  → 端口 {p} 已被占用，尝试释放...')
            sock.close()
        except:
            pass

    _kill_port(GATEWAY_PORT)
    _kill_port(BACKEND_PORT)

    if sys.executable.endswith('pythonw.exe'):
        log_path = os.path.join(MV_DIR, 'gateway.log')
        sys.stdout = open(log_path, 'a', encoding='utf-8')
        sys.stderr = sys.stdout

    server = socketserver.ThreadingTCPServer(('0.0.0.0', GATEWAY_PORT), GatewayHandler)
    server.daemon_threads = True

    import socket as _sock
    _local_ip = '127.0.0.1'
    try:
        _s = _sock.socket(_sock.AF_INET, _sock.SOCK_DGRAM)
        _s.connect(('8.8.8.8', 80))
        _local_ip = _s.getsockname()[0]
        _s.close()
    except Exception:
        pass

    now = time.strftime('%Y-%m-%d %H:%M:%S')
    print('=' * 44)
    print(f'  尚唯云影 按需启动网关  [{now}]')
    print(f'  监听端口: {GATEWAY_PORT}')
    print(f'  后端端口: {BACKEND_PORT}')
    print(f'  闲置关闭: {IDLE_TIMEOUT}s 无请求后')
    print(f'  本机地址: http://localhost:{GATEWAY_PORT}/')
    print(f'  局域网地址: http://{_local_ip}:{GATEWAY_PORT}/')
    print('=' * 44)
    print()

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print('\n  ⏹ 网关已停止')
        if GatewayHandler.backend_process:
            GatewayHandler.backend_process.terminate()
        server.server_close()
