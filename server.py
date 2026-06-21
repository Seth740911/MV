#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
尚唯云影 HTTP 服务器
- 服务 G:/AI/MV 下的网页文件
- 代理 H:/ 和 I:/ 下的所有资源
- 支持 HTTP Range 请求
"""

import gzip
import http.server
import http.client
import io
import json
import os
import re
import socketserver
import sys
import argparse
import subprocess
import urllib.parse
import base64

PORT = 8082
MV_DIR = os.path.dirname(os.path.abspath(__file__))
DISK_MAP = {'H': 'H:/', 'I': 'I:/', 'J': 'J:/'}
LOCAL_PLAYER = r'C:\Program Files\KMPlayer 64X\KMPlayer64.exe'

# 默认 host（仅在没有请求上下文时 fallback 用）
_DEFAULT_HOST = '192.168.0.10:8082'

# 常见视频 MIME 类型
VIDEO_EXTENSIONS = {
    '.mp4': 'video/mp4', '.mkv': 'video/x-matroska',
    '.avi': 'video/x-msvideo', '.webm': 'video/webm',
    '.ts': 'video/mp2t', '.wmv': 'video/x-ms-wmv',
    '.rmvb': 'application/vnd.rn-realmedia-vbr'
}

# 需要做路径重写的文本文件扩展名
REWRITE_EXTENSIONS = {'.js', '.html', '.htm', '.css', '.txt'}


class MediaServer(http.server.SimpleHTTPRequestHandler):
    default_request_version = "HTTP/1.1"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=MV_DIR, **kwargs)

    def translate_path(self, path):
        """路由：/media/H/... -> H:/..."""
        parsed = urllib.parse.urlparse(path)
        url_path = urllib.parse.unquote(parsed.path)
        for disk_letter, disk_path in DISK_MAP.items():
            prefix = '/media/{}/'.format(disk_letter)
            if url_path.startswith(prefix):
                rel = url_path[len(prefix):]
                return os.path.normpath(os.path.join(disk_path, rel))
        return super().translate_path(path)

    def do_GET(self):
        # /app -> 手机启动器
        if self.path == '/app' or self.path == '/app/':
            self._handle_app_page()
            return

        # /vlc -> VLC导航页（极简分类列表，每个分类一个M3U链接）
        if self.path == '/vlc' or self.path == '/vlc/':
            self._handle_vlc_nav()
            return

        # /m3u/<磁盘>/<路径...> -> 动态生成该目录的M3U播放列表
        if self.path.startswith('/m3u/'):
            self._handle_m3u_dir()
            return

        # /tv/simple -> 极简 VLC 播放页（已验证成功的机制）
        _tv_path = self.path.split('?')[0]
        if _tv_path == '/tv/simple':
            self._handle_simple_vlc_page()
            return

        # /tv/vlcgo?url=xxx -> VLC 自动发射页（最小化页面，避免主页 JS 干扰）
        if self.path.startswith('/tv/vlcgo'):
            self._handle_vlc_go()
            return

        # /tv/vlctest?url=xxx -> VLC 调起测试页
        if self.path.startswith('/tv/vlctest'):
            self._handle_vlc_test()
            return

        # /tv -> 重定向到 /tv/simple（兼容原版 SVTV.apk）
        if _tv_path == '/tv' or _tv_path == '/tv/':
            self.send_response(302)
            self.send_header('Location', '/tv/simple')
            self.send_header('Content-Length', '0')
            self.end_headers()
            return

        # /playlist.m3u -> VLC播放列表（全量）
        if self.path == '/playlist.m3u' or self.path == '/playlist':
            self._handle_playlist()
            return

        # /playlist/{cat}.m3u -> VLC分类播放列表
        if self.path.startswith('/playlist/') and self.path.endswith('.m3u'):
            cat = self.path.split('/')[2].replace('.m3u', '')
            self._handle_playlist(cat)
            return

        # /tv/data/{cat}/{si} -> TV系列数据
        if self.path.startswith('/tv/data/') and self.path.count('/') >= 4:
            parts = self.path.split('/')
            cat_key = parts[3].lower()
            try:
                si = int(parts[4])
            except (ValueError, IndexError):
                si = -1
            self._handle_tv_series_data(cat_key, si)
            return

        # /api/update -> 更新数据
        if self.path.startswith('/api/update'):
            self._handle_update()
            return

        try:
            if self.path.startswith('/localplay'):
                self._handle_localplay()
                return

            fs_path = self.translate_path(self.path)
            ext = os.path.splitext(fs_path)[1].lower()

            if ext in REWRITE_EXTENSIONS and os.path.isfile(fs_path):
                self._send_rewritten(fs_path)
                return

            if os.path.isfile(fs_path) and ext in ('.js', '.css', '.html', '.htm', '.txt', '.json'):
                self._send_static_gzip(fs_path)
                return

            range_header = self.headers.get('Range')
            if range_header and os.path.isfile(fs_path):
                self._handle_range_request(fs_path, range_header)
                return

            super().do_GET()

        except (ConnectionResetError, BrokenPipeError, ConnectionAbortedError):
            pass

    def do_POST(self):
        if self.path.startswith('/api/kodi'):
            self._handle_kodi_play()
            return
        if self.path.startswith('/api/update'):
            self._handle_update()
            return
        self.send_response(404)
        self.end_headers()

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Range, Content-Type')
        self.end_headers()

    def end_headers(self):
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Headers', 'Range')
        path_lower = self.path.lower().split('?')[0]
        if path_lower.endswith(('.html', '.htm', '.js', '.css')) or path_lower == '/':
            self.send_header('Cache-Control', 'no-cache, no-store, must-revalidate')
            self.send_header('Pragma', 'no-cache')
            self.send_header('Expires', '0')
        if any(self.path.endswith(ext) for ext in VIDEO_EXTENSIONS):
            self.send_header('Accept-Ranges', 'bytes')
        super().end_headers()

    def log_message(self, format, *args):
        try:
            msg = format % args
            log_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'access.log')
            with open(log_path, 'a', encoding='utf-8') as f:
                f.write(msg + '\n')
                f.flush()
        except Exception:
            pass

    # ============ 工具方法 ============

    def _get_host(self):
        """获取当前请求的 Host，优先用网关透传的原始 Host"""
        return (self.headers.get('X-Forwarded-Host')
                or self.headers.get('Host', _DEFAULT_HOST))

    def _tv_escape(self, s):
        """HTML转义"""
        if not isinstance(s, str):
            s = str(s)
        return s.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;').replace('"', '&quot;').replace("'", '&#39;')

    def _tv_parse_data(self, cat_key):
        """解析分类数据文件和索引文件，返回 {'data': {...}, 'index': {...}}"""
        result = {'data': None, 'index': None}
        
        # 解析数据文件
        data_file = os.path.join(MV_DIR, 'data', cat_key + '-data.js')
        if os.path.isfile(data_file):
            try:
                with open(data_file, 'r', encoding='utf-8') as f:
                    content = f.read()
                # 匹配 var XXX_DATA = {...}; 这样的模式
                m = re.search(r'var\s+\w+_DATA\s*=\s*(\{.*\})\s*;', content, re.DOTALL)
                if m:
                    result['data'] = json.loads(m.group(1))
            except Exception as e:
                print('[数据解析错误]', cat_key, 'data:', e)
        
        # 解析索引文件
        index_file = os.path.join(MV_DIR, 'data', cat_key + '-index.js')
        if os.path.isfile(index_file):
            try:
                with open(index_file, 'r', encoding='utf-8') as f:
                    content = f.read()
                # 匹配 var XXX_INDEX = {...}; 这样的模式
                m = re.search(r'var\s+\w+_INDEX\s*=\s*(\{.*\})\s*;', content, re.DOTALL)
                if m:
                    result['index'] = json.loads(m.group(1))
            except Exception as e:
                print('[数据解析错误]', cat_key, 'index:', e)
        
        if result['data'] is None and result['index'] is None:
            return None
        return result

    def _tv_media_url(self, base_path, file_path):
        """生成视频的HTTP访问URL"""
        full = os.path.normpath(os.path.join(base_path, file_path)).replace('\\', '/')
        for disk_letter, disk_path in DISK_MAP.items():
            if full.startswith(disk_path):
                rel = full[len(disk_path):]
                return '/media/' + disk_letter + '/' + rel
        return full

    def _should_gzip(self, content_type):
        """判断是否应该gzip压缩"""
        if not content_type:
            return False
        no_gzip = ['video/', 'image/', 'audio/']
        for prefix in no_gzip:
            if content_type.startswith(prefix):
                return False
        return True

    # ============ 响应发送方法 ============

    def _send_response_gzip(self, encoded, content_type, extra_headers=None):
        """检查客户端是否支持 gzip，如果支持则压缩后发送"""
        accept_enc = self.headers.get('Accept-Encoding', '')
        use_gzip = 'gzip' in accept_enc and self._should_gzip(content_type)

        if use_gzip:
            buf = io.BytesIO()
            with gzip.GzipFile(fileobj=buf, mode='wb') as gz:
                gz.write(encoded)
            compressed = buf.getvalue()
            self.send_response(200)
            self.send_header('Content-Type', content_type)
            self.send_header('Content-Encoding', 'gzip')
            self.send_header('Content-Length', str(len(compressed)))
            if extra_headers:
                for k, v in extra_headers.items():
                    self.send_header(k, v)
            self.end_headers()
            self.wfile.write(compressed)
        else:
            self.send_response(200)
            self.send_header('Content-Type', content_type)
            self.send_header('Content-Length', str(len(encoded)))
            if extra_headers:
                for k, v in extra_headers.items():
                    self.send_header(k, v)
            self.end_headers()
            self.wfile.write(encoded)

    def _send_static_gzip(self, fs_path):
        """发送静态文件，支持gzip压缩"""
        with open(fs_path, 'rb') as f:
            encoded = f.read()
        mime = self._guess_mime(fs_path)
        self._send_response_gzip(encoded, mime, {'Access-Control-Allow-Origin': '*'})

    def _send_rewritten(self, fs_path):
        """读取文件，H:/ -> /media/H/, I:/ -> /media/I/"""
        with open(fs_path, 'r', encoding='utf-8', errors='replace') as f:
            content = f.read()

        for disk_letter, disk_path in DISK_MAP.items():
            http_prefix = '/media/{}/'.format(disk_letter)
            content = content.replace(disk_path, http_prefix).replace(
                disk_path.replace('/', '\\'), http_prefix)

        encoded = content.encode('utf-8')
        mime = self._guess_mime(fs_path)
        self._send_response_gzip(encoded, mime, {'Access-Control-Allow-Origin': '*'})

    def _handle_range_request(self, fs_path, range_header):
        """处理 HTTP Range 请求，返回 206 Partial Content"""
        file_size = os.path.getsize(fs_path)
        m = re.match(r'bytes=(\d+)-(\d*)', range_header)
        if not m:
            self.send_error(416, 'Requested Range Not Satisfiable')
            return

        start = int(m.group(1))
        end_str = m.group(2)
        end = int(end_str) if end_str else file_size - 1

        if start >= file_size or end >= file_size or start > end:
            self.send_error(416, 'Requested Range Not Satisfiable')
            return

        content_length = end - start + 1
        self.send_response(206)
        self.send_header('Content-Range', 'bytes {}-{}/{}'.format(start, end, file_size))
        self.send_header('Content-Length', str(content_length))
        self.send_header('Accept-Ranges', 'bytes')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Expose-Headers', 'Content-Range, Accept-Ranges, Content-Length')
        self.send_header('Content-Type', self._guess_video_type(fs_path))
        self.end_headers()

        try:
            with open(fs_path, 'rb') as f:
                f.seek(start)
                remaining = content_length
                while remaining > 0:
                    chunk_size = min(65536, remaining)
                    chunk = f.read(chunk_size)
                    if not chunk:
                        break
                    self.wfile.write(chunk)
                    remaining -= len(chunk)
        except (ConnectionResetError, BrokenPipeError, ConnectionAbortedError):
            pass

    def _guess_video_type(self, path):
        _, ext = os.path.splitext(path)
        return VIDEO_EXTENSIONS.get(ext.lower(), 'application/octet-stream')

    def _guess_mime(self, path):
        _, ext = os.path.splitext(path)
        ext = ext.lower()
        if ext in VIDEO_EXTENSIONS:
            return VIDEO_EXTENSIONS[ext]
        if ext == '.js':
            return 'application/javascript; charset=utf-8'
        if ext in ('.html', '.htm'):
            return 'text/html; charset=utf-8'
        if ext == '.css':
            return 'text/css; charset=utf-8'
        if ext == '.txt':
            return 'text/plain; charset=utf-8'
        if ext == '.json':
            return 'application/json; charset=utf-8'
        if ext in ('.jpg', '.jpeg'):
            return 'image/jpeg'
        if ext == '.png':
            return 'image/png'
        if ext == '.webp':
            return 'image/webp'
        return 'application/octet-stream'

    def _send_simple_html(self, html_str):
        """发送HTML片段，支持gzip压缩"""
        encoded = html_str.encode('utf-8')
        self._send_response_gzip(encoded, 'text/html; charset=utf-8',
                                 {'Access-Control-Allow-Origin': '*'})

    # ============ 页面处理方法 ============

    def _handle_app_page(self):
        """手机启动器页面"""
        html = '''<!DOCTYPE html>
<html>
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>尚唯云影</title>
<style>
*{margin:0;padding:0;box-sizing:border-box}
body{background:#111;color:#eee;font-family:sans-serif;min-height:100vh;display:flex;flex-direction:column;align-items:center;justify-content:center}
.btn{display:block;width:80%;max-width:300px;margin:12px 0;padding:16px;background:#e62429;color:#fff;border:none;border-radius:8px;font-size:18px;font-weight:bold;cursor:pointer;text-align:center;text-decoration:none}
.btn:active{background:#c41e23}
</style>
</head>
<body>
<a class="btn" href="/tv">电视浏览</a>
<a class="btn" href="/">卡片浏览</a>
</body>
</html>'''
        encoded = html.encode('utf-8')
        self._send_response_gzip(encoded, 'text/html; charset=utf-8')

    def _handle_playlist(self, cat_key=None):
        """生成 M3U 播放列表供 VLC 加载
        cat_key=None: 入口列表（只含4个分类链接）
        cat_key='movie'/'tv'/'anime'/'doc': 该分类的完整列表
        """
        host = self._get_host()
        cat_map = {'movie': '电影', 'tv': '电视剧', 'anime': '动画片', 'doc': '纪录片'}

        # 入口列表：只列分类
        if cat_key is None:
            lines = ['#EXTM3U']
            for ck, cn in cat_map.items():
                lines.append('#EXTINF:-1,🎬 {}'.format(cn))
                lines.append('http://{}/playlist/{}.m3u'.format(host, ck))
            m3u = '\n'.join(lines).encode('utf-8')
            self.send_response(200)
            self.send_header('Content-Type', 'audio/mpegurl; charset=utf-8')
            self.send_header('Content-Length', str(len(m3u)))
            self.end_headers()
            self.wfile.write(m3u)
            return

        # 分类列表
        cn = cat_map.get(cat_key, cat_key)
        cd = self._tv_parse_data(cat_key)
        lines = ['#EXTM3U']
        if cd and cd.get('data'):
            data_obj = cd.get('data', {})
            idx_obj = cd.get('index', {})
            series_names = sorted(data_obj.keys(), key=lambda k: idx_obj.get(k, {}).get('count', 0), reverse=True)
            for sname in series_names:
                series = data_obj[sname]
                display_name = idx_obj.get(sname, {}).get('displayName', sname)
                spath = series.get('path', '').replace('\\', '/')
                group = cn + ' - ' + display_name
                for item in series.get('movies', []):
                    title = item.get('title', item.get('file', ''))
                    year = item.get('year', '')
                    label = title + (' (' + str(year) + ')' if year else '')
                    f = item.get('file', '')
                    subdir = item.get('subdir', '')
                    url = self._tv_media_url(spath, subdir + '/' + f if subdir else f)
                    lines.append('#EXTINF:-1 group-title="{}",{}'.format(group, label))
                    lines.append('http://' + host + url)
                for item in series.get('shows', []):
                    stitle = item.get('title', '')
                    epath = (item.get('path') or spath).replace('\\', '/')
                    for ep in item.get('episodes', []):
                        ep_num = ep.get('episode', None)
                        if ep_num is not None and ep_num != 0:
                            ep_label = str(ep_num)
                        else:
                            ep_label = ep.get('file', '')
                        label = (stitle or display_name) + ' 第' + str(ep_label) + '集'
                        subdir = ep.get('subdir', '')
                        ef = ep.get('file', '')
                        if subdir:
                            eurl = self._tv_media_url(epath, subdir + '/' + ef)
                        else:
                            eurl = self._tv_media_url(epath, ef)
                        lines.append('#EXTINF:-1 group-title="{}",{}'.format(group, label))
                        lines.append('http://' + host + eurl)
        m3u = '\n'.join(lines).encode('utf-8')
        self.send_response(200)
        self.send_header('Content-Type', 'audio/mpegurl; charset=utf-8')
        self.send_header('Content-Length', str(len(m3u)))
        self.end_headers()
        self.wfile.write(m3u)

    # ============ VLC播放相关 ============

    def _handle_vlc_nav(self):
        """VLC导航页 - 快速列出M3U链接，不扫描视频数（M3U生成时才扫描）"""
        _e = self._tv_escape
        host = self._get_host()
        p = []
        p.append('<!DOCTYPE html><html><head><meta charset="UTF-8">')
        p.append('<meta name="viewport" content="width=device-width,initial-scale=1.0">')
        p.append('<title>VLC播放导航</title>')
        p.append('<style>')
        p.append('*{margin:0;padding:0;box-sizing:border-box}')
        p.append('body{background:#111;color:#eee;font-family:sans-serif;font-size:18px;padding:20px}')
        p.append('h1{font-size:24px;margin-bottom:16px;color:#e62429}')
        p.append('.hint{color:#888;font-size:14px;margin-bottom:20px;line-height:1.6}')
        p.append('.disk-section{margin:16px 0}')
        p.append('.disk-title{font-size:20px;font-weight:bold;color:#ff8c00;padding:8px 0;border-bottom:1px solid #333}')
        p.append('.dir-item{display:block;padding:10px 16px;margin:4px 0;background:#1a1a1a;border-radius:6px;cursor:pointer;text-decoration:none;color:#eee;word-break:break-all}')
        p.append('.dir-item:visited{color:#eee}')
        p.append('.dir-item:hover{background:#2a2a2a}')
        p.append('.dir-sub{display:block;padding:6px 16px 6px 36px;margin:2px 0;background:#1a1a1a;border-radius:4px;cursor:pointer;text-decoration:none;color:#ccc;font-size:16px;word-break:break-all}')
        p.append('.dir-sub:visited{color:#ccc}')
        p.append('</style></head><body>')
        p.append('<h1>VLC播放导航</h1>')
        p.append('<div class="hint">在VLC中：菜单 → 打开网络串流 → 粘贴M3U链接 → 播放<br>每个链接是某个目录的视频列表，VLC加载后可浏览选片</div>')

        for disk_letter in sorted(DISK_MAP.keys()):
            disk_path = DISK_MAP[disk_letter]
            if not os.path.isdir(disk_path):
                continue
            p.append('<div class="disk-section">')
            p.append('<div class="disk-title">{0}: 盘</div>'.format(disk_letter))

            try:
                top_dirs = sorted(os.listdir(disk_path))
            except PermissionError:
                continue

            for td in top_dirs:
                td_path = os.path.join(disk_path, td)
                if not os.path.isdir(td_path):
                    continue
                m3u_url = '/m3u/{}/{}'.format(disk_letter, urllib.parse.quote(td))
                full_url = 'http://{}{}'.format(host, m3u_url)
                p.append('<a class="dir-item" href="{}">{}</a>'.format(_e(full_url), _e(td)))
                # 列出一级子目录的M3U链接（不递归）
                try:
                    sub_dirs = sorted([d for d in os.listdir(td_path)
                                       if os.path.isdir(os.path.join(td_path, d)) and not d.startswith('.')])
                except PermissionError:
                    sub_dirs = []
                for sd in sub_dirs:
                    sd_m3u_url = '/m3u/{}/{}'.format(disk_letter, urllib.parse.quote(td + '/' + sd))
                    sd_full_url = 'http://{}{}'.format(host, sd_m3u_url)
                    p.append('<a class="dir-sub" href="{}">└ {}</a>'.format(_e(sd_full_url), _e(sd)))

            p.append('</div>')

        p.append('</body></html>')
        html = ''.join(p)
        encoded = html.encode('utf-8')
        self._send_response_gzip(encoded, 'text/html; charset=utf-8')

    def _handle_m3u_dir(self):
        """动态生成指定目录的M3U播放列表
        URL格式: /m3u/H/电影/动作片
        会扫描该目录下所有视频文件，生成M3U
        """
        parsed = urllib.parse.urlparse(self.path)
        url_path = urllib.parse.unquote(parsed.path)
        # 去掉 /m3u/ 前缀
        rel = url_path[len('/m3u/'):]
        parts = rel.split('/', 1)
        if len(parts) < 2:
            self.send_error(400, '格式: /m3u/<磁盘>/<目录路径>')
            return

        disk_letter = parts[0].upper()
        dir_rel = parts[1]
        disk_path = DISK_MAP.get(disk_letter)
        if not disk_path:
            self.send_error(400, '无效磁盘: {}'.format(disk_letter))
            return

        # 构建文件系统路径
        fs_dir = os.path.normpath(os.path.join(disk_path, dir_rel.replace('/', os.sep)))
        if not os.path.isdir(fs_dir):
            self.send_error(404, '目录不存在: {}'.format(dir_rel))
            return

        # 安全检查：确保路径在磁盘根目录下
        if not os.path.normpath(fs_dir).startswith(os.path.normpath(disk_path)):
            self.send_error(403, '路径越权')
            return

        host = self._get_host()
        lines = ['#EXTM3U']

        # 只扫描当前目录的视频（不递归子目录，避免M3U过大）
        try:
            entries = sorted(os.listdir(fs_dir))
        except PermissionError:
            entries = []

        current_group = os.path.basename(fs_dir)
        subdirs_with_video = []

        for entry in entries:
            full_path = os.path.join(fs_dir, entry)
            if os.path.isdir(full_path):
                # 检查子目录是否有视频（只看直接子项）
                has_video = False
                try:
                    for sub_entry in os.listdir(full_path):
                        sub_full = os.path.join(full_path, sub_entry)
                        if os.path.isfile(sub_full) and os.path.splitext(sub_entry)[1].lower() in VIDEO_EXTENSIONS:
                            has_video = True
                            break
                        elif os.path.isdir(sub_full):
                            # 二级子目录也算有视频（后续可在VLC中打开更深层的M3U）
                            has_video = True
                            break
                except PermissionError:
                    pass
                if has_video:
                    subdirs_with_video.append(entry)
                continue
            if os.path.isfile(full_path):
                ext = os.path.splitext(entry)[1].lower()
                if ext not in VIDEO_EXTENSIONS:
                    continue
                try:
                    rel_path = os.path.relpath(full_path, disk_path).replace('\\', '/')
                except ValueError:
                    continue
                url = 'http://{}/media/{}/{}'.format(host, disk_letter, urllib.parse.quote(rel_path))
                display = os.path.splitext(entry)[0]
                lines.append('#EXTINF:-1 group-title="{}",{}'.format(current_group, display))
                lines.append(url)

        # 在M3U末尾添加子目录的M3U链接（作为"入口"项）
        for sd in sorted(subdirs_with_video):
            sd_m3u = 'http://{}/m3u/{}/{}'.format(host, disk_letter,
                urllib.parse.quote(dir_rel + '/' + sd))
            lines.append('#EXTINF:-1 group-title="[子目录]",📂 {}'.format(sd))
            lines.append(sd_m3u)

        if len(lines) == 1:
            lines.append('#EXTINF:-1,此目录无视频文件')
            lines.append('http://localhost/')

        m3u = '\n'.join(lines).encode('utf-8')
        self.send_response(200)
        self.send_header('Content-Type', 'audio/mpegurl; charset=utf-8')
        self.send_header('Content-Length', str(len(m3u)))
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        self.wfile.write(m3u)

    # === 服务端缓存：解析后的分类HTML ===
    _tv_cat_cache = {}  # {cat_key: html_str}

    @classmethod
    def warmup_cache(cls):
        """启动时预热所有分类的HTML缓存"""
        from urllib.parse import quote as _q
        cats = ['movie', 'tv', 'anime', 'doc']
        for cat_key in cats:
            if cat_key in cls._tv_cat_cache:
                continue
            # 复用 _render_cat 的逻辑（直接调用内部解析）
            cd = cls._tv_parse_data_static(cat_key)
            if cd is None:
                cls._tv_cat_cache[cat_key] = '<p style="color:#666;padding:20px;">\u65e0\u6570\u636e</p>'
                continue
            html = cls._render_cat_static(cat_key, cd)
            cls._tv_cat_cache[cat_key] = html
            print('[缓存预热] {} -> {} KB'.format(cat_key, len(html) // 1024))

    @staticmethod
    def _tv_parse_data_static(cat_key):
        """解析分类数据（静态版，不依赖self）"""
        result = {'data': None, 'index': None}
        data_file = os.path.join(MV_DIR, 'data', cat_key + '-data.js')
        if os.path.isfile(data_file):
            try:
                with open(data_file, 'r', encoding='utf-8') as f:
                    content = f.read()
                m = re.search(r'var\s+\w+_DATA\s*=\s*(\{.*\})\s*;', content, re.DOTALL)
                if m:
                    result['data'] = json.loads(m.group(1))
            except Exception as e:
                print('[数据解析错误]', cat_key, 'data:', e)
        index_file = os.path.join(MV_DIR, 'data', cat_key + '-index.js')
        if os.path.isfile(index_file):
            try:
                with open(index_file, 'r', encoding='utf-8') as f:
                    content = f.read()
                m = re.search(r'var\s+\w+_INDEX\s*=\s*(\{.*\})\s*;', content, re.DOTALL)
                if m:
                    result['index'] = json.loads(m.group(1))
            except Exception as e:
                print('[数据解析错误]', cat_key, 'index:', e)
        if result['data'] is None and result['index'] is None:
            return None
        return result

    @staticmethod
    def _render_cat_static(cat_key, cd, host=None):
        """渲染分类HTML（静态版）
        host: 当前请求的 Host（含端口），如 '192.168.0.10:8082' 或 'tunnel.sethshi.xyz'
              缓存预热时为 None，此时用默认值
        """
        from urllib.parse import quote as _q
        _host = host or _DEFAULT_HOST
        data_obj = cd.get('data', {})
        idx_obj = cd.get('index', {})
        series_names = sorted(data_obj.keys(),
            key=lambda k: idx_obj.get(k, {}).get('count', 0), reverse=True)
        if not series_names:
            return '<p style="color:#666;padding:20px;">\u6682\u65e0\u6570\u636e</p>'

        def _make_intent(video_path):
            # 生成 localplay:// URI，APK内SVWVC直接拦截调起VLC
            # 对路径每段单独编码，方括号等特殊字符保持编码状态
            # CDN来源（host无端口）：视频URL不加端口（CDN走80）
            # 局域网来源（host含端口）：保留原端口
            from urllib.parse import quote as _q2, urlparse as _up
            full_url = 'http://' + _host + video_path
            parsed = _up(full_url)
            parts = [p for p in parsed.path.split('/') if p]
            encoded_path = '/'.join(_q2(s, safe='') for s in parts)
            if parsed.port:
                safe_url = 'http://{}:{}/{}'.format(parsed.hostname, parsed.port, encoded_path)
            else:
                safe_url = 'http://{}/{}'.format(parsed.hostname, encoded_path)
            return 'localplay://' + _q2(safe_url, safe='')

        def _video_url(spath, media_file):
            full = os.path.normpath(os.path.join(spath, media_file)).replace('\\', '/')
            for dl, dp in DISK_MAP.items():
                if full.startswith(dp):
                    return '/media/' + dl + '/' + full[len(dp):]
            return None

        body = ''
        for si, sname in enumerate(series_names):
            series = data_obj[sname]
            dn = idx_obj.get(sname, {}).get('displayName', sname)
            cnt = series.get('count', 0)
            spath = series.get('path', '').replace('\\', '/')

            body += '<details style="margin-bottom:8px;"><summary style="font-size:18px;font-weight:bold;padding:10px 12px;background:#1a1a1a;border-radius:6px;cursor:pointer;color:#ccc;list-style:none;">'
            body += '<span style="color:#e62429;margin-right:8px;">\u25b6</span>{} <span style="color:#666;font-size:14px;">({}\u90e8)</span></summary>'.format(dn, cnt)
            body += '<div style="padding:8px 0;">'

            movies = series.get('movies') or []
            if movies:
                body += '<div style="display:grid;grid-template-columns:1fr 1fr;gap:6px;">'
                idx = 0
                for item in movies:
                    f = item.get('file', '')
                    if not f: continue
                    subdir = item.get('subdir', '')
                    mf = subdir + '/' + f if subdir else f
                    vurl = _video_url(spath, mf)
                    if not vurl: continue
                    idx += 1
                    title = item.get('title', f)
                    year = item.get('year', '')
                    intent = _make_intent(vurl)
                    yhtml = ' <span style="color:#555;font-size:12px;">{}</span>'.format(year) if year else ''
                    body += (
                        '<a href="{intent}" style="display:block;padding:10px 12px;background:#1a1a1a;'
                        'border-radius:4px;color:#ddd;text-decoration:none;font-size:16px;'
                        'white-space:nowrap;overflow:hidden;text-overflow:ellipsis;">'
                        '{idx}.{title}{year}</a>'
                    ).format(intent=intent, idx=idx, title=title, year=yhtml)
                body += '</div>'

            shows = series.get('shows') or []
            for show in shows:
                stitle = show.get('title', '')
                eps = show.get('episodes', [])
                epath = (show.get('path') or spath).replace('\\', '/')
                if stitle and stitle != dn:
                    body += '<div style="color:#e62429;font-size:16px;font-weight:bold;padding:10px 0 6px;">{}</div>'.format(stitle)
                body += '<div style="display:flex;flex-wrap:wrap;gap:6px;">'
                for ei, ep in enumerate(eps):
                    ef = ep.get('file', '')
                    if not ef: continue
                    subdir = ep.get('subdir', '')
                    mf = subdir + '/' + ef if subdir else ef
                    vurl = _video_url(epath, mf)
                    if not vurl: continue
                    intent = _make_intent(vurl)
                    ep_num = ep.get('episodeNum') or ep.get('index') or (ei + 1)
                    body += (
                        '<a href="{intent}" style="display:inline-flex;align-items:center;justify-content:center;'
                        'width:48px;height:48px;background:#222;color:#ccc;border-radius:6px;'
                        'font-size:16px;font-weight:bold;text-decoration:none;">{num}</a>'
                    ).format(intent=intent, num=ep_num)
                body += '</div>'

            body += '</div></details>'
        return body

    def _handle_simple_vlc_page(self):
        """极简 VLC 电影列表页 - 点击直接调起 VLC
        导航栏固定顶部 + 懒加载（AJAX按需加载 + 服务端内存缓存）"""
        qs = urllib.parse.urlparse(self.path).query
        params = urllib.parse.parse_qs(qs)
        active_cat = params.get('cat', ['movie'])[0]
        is_ajax = 'ajax' in params

        cats = [('movie', u'\u7535\u5f71'), ('tv', u'\u7535\u89c6\u5267'),
                ('anime', u'\u52a8\u753b\u7247'), ('doc', u'\u7eaa\u5f55\u7247')]

        def _render_cat(cat_key):
            """渲染单个分类HTML，带服务端内存缓存（按cat_key+host缓存，不同来源生成不同URL）"""
            current_host = self._get_host()
            cache_key = cat_key + '@' + current_host
            if cache_key in self._tv_cat_cache:
                return self._tv_cat_cache[cache_key]
            cd = self._tv_parse_data_static(cat_key)
            if cd is None:
                html = '<p style="color:#666;padding:20px;">\u65e0\u6570\u636e</p>'
            else:
                html = self._render_cat_static(cat_key, cd, self._get_host())
            self._tv_cat_cache[cache_key] = html
            return html

        # --- AJAX 模式：只返回分类 HTML 片段 ---
        if is_ajax:
            fragment = _render_cat(active_cat)
            self._send_simple_html(fragment)
            return

        # --- 正常模式：只渲染当前分类，其他留空（点击时 AJAX 加载）---
        active_html = _render_cat(active_cat)

        cat_divs = ''
        for ck, cn in cats:
            if ck == active_cat:
                cat_divs += '<div class="cat on" id="c-{k}" data-loaded="1">{html}</div>\n'.format(k=ck, html=active_html)
            else:
                cat_divs += '<div class="cat" id="c-{k}" data-loaded="0"><p style="color:#555;padding:30px;text-align:center;">\u70b9\u51fb\u52a0\u8f7d...</p></div>\n'.format(k=ck)

        html = '''<!DOCTYPE html><html><head><meta charset="utf-8">
<title>VLC \u7535\u5f71</title>
<style>
*{{margin:0;padding:0;box-sizing:border-box}}
body{{background:#111;color:#fff;font-family:sans-serif;padding:60px 12px 12px;max-width:960px;margin:0 auto}}
.nav{{position:fixed;top:0;left:0;width:100%;z-index:10;display:flex;background:#222;border-bottom:2px solid #333}}
.nav a{{flex:1;text-align:center;padding:14px 0;font-size:20px;font-weight:bold;color:#666;text-decoration:none}}
.nav a.active{{color:#e62429;border-bottom:3px solid #e62429}}
.cat{{display:none}}.cat.on{{display:block}}
details[open] summary span:first-child{{transform:rotate(90deg);display:inline-block}}
</style></head><body>
<div class="nav" id="nav">
<a href="#" data-c="movie">\u7535\u5f71</a>
<a href="#" data-c="tv">\u7535\u89c6\u5267</a>
<a href="#" data-c="anime">\u52a8\u753b\u7247</a>
<a href="#" data-c="doc">\u7eaa\u5f55\u7247</a>
</div>
{divs}
<script>
var act="{active}";
function sw(c){{
  act=c;
  var ts=document.getElementById("nav").getElementsByTagName("a");
  for(var i=0;i<ts.length;i++){{ts[i].className=(ts[i].getAttribute("data-c")==c)?"active":""}}
  var ds=document.getElementsByTagName("div");
  for(var i=0;i<ds.length;i++){{
    if(ds[i].className&&ds[i].className.indexOf("cat")>-1){{
      ds[i].className=(ds[i].id=="c-"+c)?"cat on":"cat";
    }}
  }}
  var el=document.getElementById("c-"+c);
  if(el&&el.getAttribute("data-loaded")=="0"){{
    el.setAttribute("data-loaded","2");
    el.innerHTML="<p style='color:#555;padding:30px;text-align:center;'>\u52a0\u8f7d\u4e2d...</p>";
    var x=new XMLHttpRequest();
    x.open("GET","/tv/simple?cat="+c+"&ajax=1",true);
    x.onreadystatechange=function(){{
      if(x.readyState==4&&x.status==200){{
        el.innerHTML=x.responseText;
        el.setAttribute("data-loaded","1");
      }}
    }};
    x.send(null);
  }}
}}
var ts=document.getElementById("nav").getElementsByTagName("a");
for(var i=0;i<ts.length;i++){{(function(a){{a.onclick=function(){{sw(a.getAttribute("data-c"));return false}}}})(ts[i])}}
sw(act);
</script>
</body></html>'''.format(divs=cat_divs, active=active_cat)
        encoded = html.encode('utf-8')
        self._send_response_gzip(encoded, 'text/html; charset=utf-8')

    def _handle_vlc_go(self):
        """VLC 自动发射页 - 最小化页面，服务器端构造 intent URI"""
        qs = urllib.parse.urlparse(self.path).query
        params = urllib.parse.parse_qs(qs)
        video_url = params.get('url', [''])[0]
        if not video_url:
            self._send_simple_html('<h2>缺少 url 参数</h2><a href="/tv/simple">返回</a>')
            return
        # 构造 localplay:// URI（APK内SVWVC拦截后 ACTION_VIEW + video/* 调起VLC）
        from urllib.parse import quote as _q
        localplay_uri = 'localplay://' + _q(video_url, safe='')
        html = '''<!DOCTYPE html><html><head><meta charset="utf-8"><title>VLC</title>
<style>body{{background:#000;color:#fff;font-family:sans-serif;display:flex;
align-items:center;justify-content:center;height:100vh;margin:0;font-size:24px;
flex-direction:column}}
a{{color:#e62429;text-decoration:none}}.back{{color:#999;font-size:16px;margin-top:20px}}
</style></head><body>
<a id="play" href="{localplay}" style="display:block;padding:20px 60px;background:#e62429;
color:#fff;border-radius:12px;font-size:28px;font-weight:bold;text-decoration:none">
点击播放</a>
<a class="back" href="/tv/simple">返回列表</a>
<script>
var lp="{localplay}";
setTimeout(function(){{location.href=lp;}},300);
</script>
</body></html>'''.format(localplay=localplay_uri)
        encoded = html.encode('utf-8')
        self.send_response(200)
        self.send_header('Content-Type', 'text/html; charset=utf-8')
        self.send_header('Content-Length', str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)

    def _handle_vlc_test(self):
        """VLC 调起测试页 - 用指定 URL 测试 intent URI"""
        qs = urllib.parse.urlparse(self.path).query
        params = urllib.parse.parse_qs(qs)
        url = params.get('url', ['/media/I/1.mp4'])[0]
        # 确保绝对地址
        if url.startswith('/'):
            url = 'http://{}{}'.format(self._get_host(), url)
        # 编码路径部分
        from urllib.parse import urlparse as _up, quote as _q
        parsed = _up(url)
        encoded_path = '/'.join(_q(s, safe='') for s in parsed.path.split('/') if s)
        encoded_url = '{}://{}:{}/{}'.format(parsed.scheme, parsed.hostname, parsed.port or 8082, encoded_path)
        # intent URI (scheme=http 版)
        intent_sh = 'intent://{}:{}{}#Intent;scheme=http;type=video/*;package=org.videolan.vlc;end'.format(
            parsed.hostname, parsed.port or 8082, '/' + encoded_path)
        # intent URI (无 scheme 版)
        intent_no = 'intent://{}:{}{}#Intent;type=video/*;package=org.videolan.vlc;end'.format(
            parsed.hostname, parsed.port or 8082, '/' + encoded_path)

        html = '''<!DOCTYPE html><html><head><meta charset="utf-8">
<title>VLC Test</title>
<style>
body{{background:#111;color:#fff;font-family:sans-serif;padding:30px;font-size:18px}}
.info{{color:#999;margin:8px 0;word-break:break-all;max-width:900px}}
.btn{{display:inline-block;background:#e62429;color:#fff;padding:14px 28px;margin:10px 6px;
border-radius:10px;font-size:20px;cursor:pointer;border:none}}
.btn:hover{{background:#ff3040}}
</style></head><body>
<h2>VLC Intent 测试</h2>
<div class="info">原始 URL: {raw}</div>
<div class="info">编码 URL: {enc}</div>
<div class="info">Intent(scheme=http): {ish}</div>
<div class="info">Intent(无scheme): {ino}</div>
<br>
<button class="btn" onclick="launch(1)">方式1: scheme=http</button>
<button class="btn" onclick="launch(2)">方式2: 无scheme</button>
<button class="btn" onclick="launch(3)">方式3: 直接跳转URL</button>
<div id="log" style="margin-top:20px;color:#0f0;font-size:16px"></div>
<script>
var ish="{ish}", ino="{ino}", enc="{enc}";
function log(s){{var d=document.getElementById("log");d.innerHTML+=s+"<br>"}}
function launch(m){{
  log("尝试方式"+m+" @ "+new Date().toLocaleTimeString());
  if(m==1) window.location.href=ish;
  else if(m==2) window.location.href=ino;
  else if(m==3) window.location.href=enc;
  setTimeout(function(){{log("页面仍在(VLC未接管)")}}, 5000);
}}
</script>
</body></html>'''.format(raw=url, enc=encoded_url, ish=intent_sh, ino=intent_no)
        encoded = html.encode('utf-8')
        self.send_response(200)
        self.send_header('Content-Type', 'text/html; charset=utf-8')
        self.send_header('Content-Length', str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)

    def _handle_tv2_page(self, js_file='tv2.js'):
        """TV页面 - 始终渲染页面结构，数据按需加载"""
        _e = self._tv_escape
        p = []
        p.append('<!DOCTYPE html><html><head><meta charset="UTF-8">')
        p.append('<meta name="viewport" content="width=device-width,initial-scale=1.0">')
        p.append('<title>云影TV</title>')
        p.append('<style>')
        p.append('*{margin:0;padding:0;box-sizing:border-box}')
        p.append('body{background:#111;color:#eee;font-family:sans-serif;font-size:20px;padding-top:54px}')
        p.append('.tabs{display:flex;background:#222;position:fixed;top:0;left:0;width:100%;z-index:10}')
        p.append('.tab{flex:1;padding:12px 0;text-align:center;font-size:20px;font-weight:bold;cursor:pointer;border-bottom:3px solid transparent}')
        p.append('.tab.active{border-bottom-color:#e62429;color:#e62429}')
        p.append('.tv-focused{border:2px solid #fff!important;background:rgba(230,36,41,0.35)!important;box-shadow:0 0 6px #fff}')
        p.append('.cat{display:none;padding:10px 16px}')
        p.append('.cat.active{display:block}')
        p.append('.stitle{font-size:18px;font-weight:bold;padding:10px 0 6px;border-bottom:1px solid #333;margin-top:12px;cursor:pointer;color:#ccc}')
        p.append('.scount{font-size:14px;color:#888;margin-left:8px}')
        p.append('.ilist{margin:4px 0 8px 0;display:none}')
        p.append('.ilist.open{display:block;overflow:hidden}')
        p.append('.vitem{display:block;padding:10px 12px;background:#1a1a1a;border-radius:6px;cursor:pointer;font-size:17px;min-height:44px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}')
        p.append('.ep{display:inline-block;padding:6px 14px;margin:3px 4px 3px 0;border-radius:4px;background:#252525;font-size:15px;cursor:pointer}')
        p.append('.vsub{font-size:13px;color:#888;margin-left:8px}')
        p.append('.show-label{padding:10px 12px;margin:4px 0 0 0;color:#aaa;font-size:17px;display:block;clear:both}')
        p.append('.loading{color:#888;padding:10px 12px;font-size:14px}')
        p.append('.play-page{display:none;position:fixed;top:0;left:0;width:100%;height:100%;background:#000;z-index:100}')
        p.append('.play-page video{display:block;margin:auto;max-width:100%;max-height:100%}')
        p.append('.play-close{position:absolute;top:20px;right:20px;color:#fff;font-size:32px;cursor:pointer;z-index:101;background:rgba(0,0,0,0.7);border:none;padding:8px 16px;border-radius:6px}')
        p.append('</style></head><body>')

        # 始终渲染tabs
        active_cats = [('movie', '电影'), ('tv', '电视剧'), ('anime', '动画片'), ('doc', '纪录片')]
        
        p.append('<div class="tabs">')
        first = True
        for ck, cn in active_cats:
            cls = 'tab active' if first else 'tab'
            p.append('<div class="{}" data-action="switchCat" data-cat="{}">{}</div>'.format(cls, ck, cn))
            first = False
        p.append('</div>')

        # 尝试加载系列标题（如果数据文件存在）
        first = True
        for ck, cn in active_cats:
            cls = 'cat active' if first else 'cat'
            p.append('<div class="{}" id="cat-{}">'.format(cls, ck))
            first = False
            
            # 尝试解析数据文件
            cd = self._tv_parse_data(ck)
            if cd and cd.get('data'):
                data_obj = cd.get('data', {})
                idx_obj = cd.get('index', {})
                series_names = sorted(data_obj.keys(), key=lambda k: idx_obj.get(k, {}).get('count', 0), reverse=True)
                for si, sname in enumerate(series_names):
                    series = data_obj[sname]
                    display_name = idx_obj.get(sname, {}).get('displayName', sname)
                    count = series.get('count', 0)
                    sid = '{}-s{}'.format(ck, si)
                    p.append('<div class="stitle" data-action="toggle" data-sid="{}" data-ck="{}" data-si="{}">{}<span class="scount">({}部)</span></div>'.format(
                        sid, ck, si, _e(display_name), count))
                    p.append('<div class="ilist" id="il-{}"></div>'.format(sid))
            else:
                p.append('<div class="loading">暂无数据，请检查数据文件</div>')
            
            p.append('</div>')

        # player
        p.append('<div class="play-page" id="play-page">')
        p.append('<button class="play-close" data-action="close-play">&#10005;</button>')
        p.append('<video id="vid" controls autoplay></video>')
        p.append('</div>')

        # JS
        p.append('<script src="/' + js_file + '?v=12"></script>')
        p.append('</body></html>')
        html = ''.join(p)
        encoded = html.encode('utf-8')
        self._send_response_gzip(encoded, 'text/html; charset=utf-8')

    def _handle_tv_series_data(self, cat_key, series_index):
        """返回指定系列内的影片/剧集HTML片段"""
        _e = self._tv_escape
        host = self._get_host()
        cd = self._tv_parse_data(cat_key)
        if cd is None:
            self._send_simple_html('<div class="loading">暂无数据</div>')
            return
        data_obj = cd.get('data', {})
        idx_obj = cd.get('index', {})
        series_names = sorted(data_obj.keys(), key=lambda k: idx_obj.get(k, {}).get('count', 0), reverse=True)
        if series_index < 0 or series_index >= len(series_names):
            self._send_simple_html('<div class="loading">暂无数据</div>')
            return
        sname = series_names[series_index]
        series = data_obj[sname]
        spath = series.get('path', '').replace('\\', '/')
        p = []
        for item in series.get('movies', []):
            f = item.get('file', '')
            if not f:
                continue
            subdir = item.get('subdir', '')
            media_file = subdir + '/' + f if subdir else f
            url = self._tv_media_url(spath, media_file)
            title = item.get('title', f)
            year = item.get('year', '')
            title_html = _e(title)
            if year:
                title_html += '<span class="vsub">{}年</span>'.format(year)
            p.append('<div class="vitem" data-action="play" data-url="{}" data-vlcgo="/tv/vlcgo?url=http://{}{}">{}</div>'.format(_e(url), _e(host), _e(url), title_html))
        for item in series.get('shows', []):
            stitle = item.get('title', '')
            episodes = item.get('episodes', [])
            epath = (item.get('path') or spath).replace('\\', '/')
            ep_count = item.get('episodeCount', len(episodes))
            p.append('<div class="show-label">{}<span class="vsub">{}集</span></div>'.format(_e(stitle), ep_count))
            p.append('<div style="margin:2px 0 8px 20px">')
            for ep in episodes:
                ef = ep.get('file', '')
                if not ef:
                    continue
                subdir = ep.get('subdir', '')
                if subdir:
                    eurl = self._tv_media_url(epath, subdir + '/' + ef)
                else:
                    eurl = self._tv_media_url(epath, ef)
                ep_num = ep.get('episode', None)
                if ep_num is not None and ep_num != 0:
                    ep_label = str(ep_num)
                else:
                    ep_label = str(episodes.index(ep) + 1)
                p.append('<div class="vitem" style="display:inline-block;padding:6px 14px;margin:3px;border-radius:4px;background:#252525;font-size:15px" data-action="play" data-url="{}" data-vlcgo="/tv/vlcgo?url=http://{}{}">{}</div>'.format(_e(eurl), _e(host), _e(eurl), _e(ep_label)))
            p.append('</div>')
        html = ''.join(p) if p else '<div class="loading">暂无内容</div>'
        encoded = html.encode('utf-8')
        self._send_response_gzip(encoded, 'text/html; charset=utf-8')

    def _handle_tv_data(self, cat_key):
        """返回指定分类的HTML片段（旧接口，兼容）"""
        _e = self._tv_escape
        cd = self._tv_parse_data(cat_key)
        if cd is None:
            self.send_response(200)
            self.send_header('Content-Type', 'text/html; charset=utf-8')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            self.wfile.write('<div class="loading">暂无数据</div>'.encode('utf-8'))
            return
        data_obj = cd.get('data', {})
        idx_obj = cd.get('index', {})
        p = []
        series_names = sorted(data_obj.keys(), key=lambda k: idx_obj.get(k, {}).get('count', 0), reverse=True)
        for sname in series_names:
            series = data_obj[sname]
            display_name = idx_obj.get(sname, {}).get('displayName', sname)
            count = series.get('count', 0)
            p.append('<div class="stitle">{}<span class="scount">({}部)</span></div>'.format(_e(display_name), count))
        html = ''.join(p) if p else '<div class="loading">暂无数据</div>'
        encoded = html.encode('utf-8')
        self._send_response_gzip(encoded, 'text/html; charset=utf-8')

    # ============ 功能方法 ============

    def _handle_update(self):
        """执行 auto_scan.py 重新扫描硬盘"""
        try:
            script = os.path.join(MV_DIR, 'auto_scan.py')
            r = subprocess.run(
                [sys.executable, script],
                capture_output=True, text=True, timeout=300,
                cwd=MV_DIR
            )
            success = (r.returncode == 0)
            output = r.stdout or r.stderr or ''
            self.send_response(200)
            self.send_header('Content-Type', 'application/json; charset=utf-8')
            self.end_headers()
            self.wfile.write(json.dumps({'success': success, 'output': output[-500:]}).encode('utf-8'))
        except Exception as e:
            self.send_response(200)
            self.send_header('Content-Type', 'application/json; charset=utf-8')
            self.end_headers()
            self.wfile.write(json.dumps({'success': False, 'error': str(e)}).encode('utf-8'))

    def _handle_localplay(self):
        """调用本地播放器打开文件"""
        parsed = urllib.parse.urlparse(self.path)
        params = urllib.parse.parse_qs(parsed.query)
        file_path = params.get('path', [''])[0]
        if not file_path or not os.path.isfile(file_path):
            self.send_response(404)
            self.end_headers()
            return
        try:
            subprocess.Popen([LOCAL_PLAYER, file_path])
            self.send_response(200)
            self.end_headers()
        except Exception as e:
            self.send_response(500)
            self.end_headers()



if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='尚唯云影库 HTTP 服务器')
    parser.add_argument('--port', type=int, default=PORT, help='监听端口（默认 {}）'.format(PORT))
    parser.add_argument('--quiet', action='store_true', help='静默模式')
    args = parser.parse_args()

    listen_port = args.port

    # pythonw.exe 后台运行时 stdout/stderr 为 None，写入会崩溃
    if sys.executable.endswith('pythonw.exe'):
        sys.stdout = open(os.devnull, 'w')
        sys.stderr = sys.stdout

    import socket as _sock

    # 双栈监听: [::] 同时接受IPv4和IPv6连接
    class DualStackTCPServer(socketserver.ThreadingTCPServer):
        address_family = _sock.AF_INET6
        def server_bind(self):
            self.socket.setsockopt(_sock.IPPROTO_IPV6, _sock.IPV6_V6ONLY, 0)
            super().server_bind()

    server = DualStackTCPServer(('::', listen_port), MediaServer)
    server.daemon_threads = True

    _local_ip = '127.0.0.1'
    try:
        _s = _sock.socket(_sock.AF_INET, _sock.SOCK_DGRAM)
        _s.connect(('8.8.8.8', 80))
        _local_ip = _s.getsockname()[0]
        _s.close()
    except Exception:
        pass

    if not args.quiet:
        print('============================================')
        print('  尚唯云影 HTTP 服务器')
        print('  本机访问: http://localhost:{}/'.format(listen_port))
        print('  局域网访问: http://{}:{}/'.format(_local_ip, listen_port))
        print('  资源代理: /media/H/...->H:/  /media/I/...->I:/')
        print('  Range 请求: 已启用')
        print('============================================')

    # 预热分类HTML缓存
    if not args.quiet:
        print('\u7f13\u5b58\u9884\u70ed\u4e2d...')
    MediaServer.warmup_cache()

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        if not args.quiet:
            print('\n服务器已停止')
        server.server_close()
