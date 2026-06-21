#!/usr/bin/env python3
"""
尚唯云影 HTTP 服务器
- 服务 G:/AI/MV 下的网页文件
- 代理 H:/ 和 I:/ 下的所有资源（视频/照片/海报）
- 支持 HTTP Range 请求，实现视频拖拽/快进/分段加载
- 自动重写响应内容中的 H:/ I:/ 路径为 /media/H/ /media/I/（HTTP模式兼容）
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
        """路由：/media/H/... → H:/..., /media/I/... → I:/... 其他 → G:/AI/MV/..."""
        parsed = urllib.parse.urlparse(path)
        url_path = urllib.parse.unquote(parsed.path)
        # 支持 /media/H/ /media/I/ /media/J/ 三种盘符代理
        for disk_letter, disk_path in DISK_MAP.items():
            prefix = f'/media/{disk_letter}/'
            if url_path.startswith(prefix):
                rel = url_path[len(prefix):]
                return os.path.normpath(os.path.join(disk_path, rel))
        return super().translate_path(path)

    def do_GET(self):
        # /app → 尚唯系列手机启动器
        if self.path == '/app' or self.path == '/app/':
            self._handle_app_page()
            return

        # /tv → TV2页面（折叠布局，全浏览器兼容）
        if self.path == '/tv' or self.path == '/tv/':
            self._handle_tv2_page()
            return
        # /tv/data/{cat}/{si} → TV系列数据接口（按需加载）
        if self.path.startswith('/tv/data/') and self.path.count('/') >= 4:
            parts = self.path.split('/')
            cat_key = parts[3].lower()
            try:
                si = int(parts[4])
            except (ValueError, IndexError):
                si = -1
            self._handle_tv_series_data(cat_key, si)
            return
        # /tv/data/{cat} → TV分类数据接口（旧接口兼容）
        if self.path.startswith('/tv/data/'):
            cat_key = self.path.split('/')[-1].lower()
            self._handle_tv_data(cat_key)
            return

        # 支持 /api/update 通过 GET 访问（方便浏览器直接测试）
        if self.path.startswith('/api/update'):
            self._handle_update()
            return

        try:
            # /localplay?path=I:/电影/... → 调用本地播放器打开文件
            if self.path.startswith('/localplay'):
                self._handle_localplay()
                return

            fs_path = self.translate_path(self.path)
            ext = os.path.splitext(fs_path)[1].lower()

            # 文本文件：读取内容 → 路径重写 → 直接返回
            if ext in REWRITE_EXTENSIONS and os.path.isfile(fs_path):
                self._send_rewritten(fs_path)
                return

            # 可压缩的静态文件（图片/视频/字体等不压缩）
            if os.path.isfile(fs_path) and ext in ('.js', '.css', '.html', '.htm', '.txt', '.json'):
                self._send_static_gzip(fs_path)
                return

            # Range 请求（视频分段）
            range_header = self.headers.get('Range')
            if range_header and os.path.isfile(fs_path):
                self._handle_range_request(fs_path, range_header)
                return

            # 其他：走默认逻辑
            super().do_GET()

        except (ConnectionResetError, BrokenPipeError, ConnectionAbortedError):
            pass

    def _send_static_gzip(self, fs_path):
        """发送静态文件，支持gzip压缩；JS/CSS/HTML 强制不缓存"""
        with open(fs_path, 'rb') as f:
            encoded = f.read()
        mime = self._guess_mime(fs_path)
        ext = os.path.splitext(fs_path)[1].lower()
        extra = {'Access-Control-Allow-Origin': '*'}
        # JS/CSS/HTML：每次都重新下载，方便TV端调试
        if ext in ('.js', '.css', '.html', '.htm'):
            extra['Cache-Control'] = 'no-cache, no-store, must-revalidate'
            extra['Pragma'] = 'no-cache'
            extra['Expires'] = '0'
        self._send_response_gzip(encoded, mime, extra)

    def do_POST(self):
        if self.path.startswith('/api/kodi'):
            self._handle_kodi_play()
            return
        if self.path.startswith('/api/update'):
            self._handle_update()
            return
        self.send_response(404)
        self.end_headers()

    def _handle_update(self):
        """执行 auto_scan.py 重新扫描硬盘 → 刷新数据文件"""
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
            self.send_response(500)
            self.send_header('Content-Type', 'application/json; charset=utf-8')
            self.end_headers()
            self.wfile.write(json.dumps({'success': False, 'error': str(e)}).encode('utf-8'))

    def _handle_localplay(self):
        """用 KMPlayer 打开本地视频文件（支持多音轨/字幕）"""
        parsed = urllib.parse.urlparse(self.path)
        params = urllib.parse.parse_qs(parsed.query)
        file_path = params.get('path', [None])[0]
        if not file_path or not os.path.isfile(file_path):
            self.send_response(404)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(b'{"ok":false,"error":"file not found"}')
            return
        try:
            subprocess.Popen([LOCAL_PLAYER, file_path],
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(('{"ok":true,"path":"' + file_path.replace('\\','/') + '"}').encode())
        except Exception as e:
            self.send_response(500)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(('{"ok":false,"error":"' + str(e) + '"}').encode())

    # ===== 尚唯系列手机启动器 =====
    _APP_LIST = [
        ('8081', '云色', '影视图库', '#e62429', '&#127916;'),
        ('8082', '云影', '电影剧集', '#8b5cf6', '&#127910;'),
        ('8083', '云册', '漫画图集', '#10b981', '&#128214;'),
        ('8084', '云听', '有声书馆', '#f59e0b', '&#127925;'),
        ('8085', '云音', '佛音梵唱', '#6366f1', '&#127926;'),
    ]

    def _handle_app_page(self):
        """尚唯系列手机启动器：点哪个开哪个浏览器"""
        import socket as _sock
        local_ip = '127.0.0.1'
        try:
            s = _sock.socket(_sock.AF_INET, _sock.SOCK_DGRAM)
            s.connect(('8.8.8.8', 80))
            local_ip = s.getsockname()[0]
            s.close()
        except Exception:
            pass

        html = '<!DOCTYPE html><html><head><meta charset="UTF-8">'
        html += '<meta name="viewport" content="width=device-width,initial-scale=1.0,maximum-scale=1.0,user-scalable=no">'
        html += '<meta name="apple-mobile-web-app-capable" content="yes">'
        html += '<meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">'
        html += '<meta name="mobile-web-app-capable" content="yes">'
        html += '<title>尚唯</title>'
        html += '<style>'
        html += '*{margin:0;padding:0;box-sizing:border-box}'
        html += 'html,body{height:100%;width:100%;overflow:hidden}'
        html += 'body{background:linear-gradient(135deg,#0f0c29,#302b63,#24243e);color:#fff;font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif;display:flex;flex-direction:column;align-items:center;justify-content:center;min-height:100vh;-webkit-tap-highlight-color:transparent}'
        html += '.logo{font-size:36px;font-weight:800;letter-spacing:8px;margin-bottom:6px;text-shadow:0 0 30px rgba(255,255,255,0.3)}'
        html += '.sub{font-size:13px;color:rgba(255,255,255,0.4);letter-spacing:4px;margin-bottom:48px}'
        html += '.grid{display:flex;flex-wrap:wrap;justify-content:center;gap:16px;padding:0 20px;max-width:400px}'
        html += '.app{width:90px;display:flex;flex-direction:column;align-items:center;text-decoration:none;color:#fff}'
        html += '.icon{width:68px;height:68px;border-radius:18px;display:flex;align-items:center;justify-content:center;font-size:32px;margin-bottom:8px;box-shadow:0 4px 15px rgba(0,0,0,0.3);transition:transform .15s}'
        html += '.app:active .icon{transform:scale(0.9)}'
        html += '.name{font-size:14px;font-weight:600}'
        html += '.desc{font-size:10px;color:rgba(255,255,255,0.4);margin-top:2px}'
        html += '</style></head><body>'
        html += '<div class="logo">尚 唯</div>'
        html += '<div class="sub">SHANGWEI</div>'
        html += '<div class="grid">'

        for port, name, desc, color, emoji in self._APP_LIST:
            url = f'http://{local_ip}:{port}/'
            html += f'<a class="app" href="{url}">'
            html += f'<div class="icon" style="background:{color}">{emoji}</div>'
            html += f'<div class="name">{name}</div>'
            html += f'<div class="desc">{desc}</div>'
            html += '</a>'

        html += '</div></body></html>'

        encoded = html.encode('utf-8')
        self._send_response_gzip(encoded, 'text/html; charset=utf-8', {'Cache-Control': 'no-cache, no-store, must-revalidate', 'Pragma': 'no-cache', 'Expires': '0'})

    # ===== 极简TV页面 =====
    _TV_CATS = [
        ('movie', '电影', 'MOVIE'),
        ('tv',    '电视剧', 'TV'),
        ('anime', '动画片', 'ANIME'),
        ('doc',   '纪录片', 'DOC'),
    ]
    _TV_DATA_CACHE = {}

    @classmethod
    def _tv_parse_data(cls, cat_key):
        """解析指定分类数据，返回{data, index, name}，带缓存"""
        if cat_key in cls._TV_DATA_CACHE:
            return cls._TV_DATA_CACHE[cat_key]
        prefix = ''
        cat_name = ''
        for ck, cn, cp in cls._TV_CATS:
            if ck == cat_key:
                prefix = cp
                cat_name = cn
                break
        if not prefix:
            return None
        data_path = os.path.join(MV_DIR, 'data', cat_key + '-data.js')
        index_path = os.path.join(MV_DIR, 'data', cat_key + '-index.js')
        if not os.path.isfile(data_path):
            return None
        with open(data_path, 'r', encoding='utf-8', errors='replace') as f:
            raw = f.read()
        m = re.search(r'var\s+' + prefix + r'_DATA\s*=\s*(\{.*\})\s*;?\s*$', raw, re.DOTALL)
        data_obj = json.loads(m.group(1)) if m else {}
        idx_obj = {}
        if os.path.isfile(index_path):
            with open(index_path, 'r', encoding='utf-8', errors='replace') as f2:
                raw2 = f2.read()
            m2 = re.search(r'var\s+' + prefix + r'_INDEX\s*=\s*(\{.*\})\s*;?\s*$', raw2, re.DOTALL)
            idx_obj = json.loads(m2.group(1)) if m2 else {}
        result = {'data': data_obj, 'index': idx_obj, 'name': cat_name}
        cls._TV_DATA_CACHE[cat_key] = result
        return result

    @staticmethod
    def _tv_escape(s):
        return str(s).replace('&','&amp;').replace('<','&lt;').replace('>','&gt;').replace('"','&quot;').replace("'", '&#39;')

    @staticmethod
    def _tv_media_url(path, filename):
        norm = path.replace('\\','/').rstrip('/')
        parts = norm.split('/')
        disk = parts[0].replace(':','')
        rest = '/'.join(parts[1:] + [filename])
        return '/media/' + disk + '/' + '/'.join([urllib.parse.quote(p) for p in rest.split('/')])

    def _handle_tv_page(self):
        """TV页框架 - 数据按需加载（XHR），兼容Android 4.4"""
        _e = self._tv_escape
        p = []
        p.append('<!DOCTYPE html><html><head><meta charset="UTF-8">')
        p.append('<meta name="viewport" content="width=device-width,initial-scale=1.0">')
        p.append('<title>云影TV</title><style>')
        p.append('*{margin:0;padding:0;box-sizing:border-box}')
        p.append('body{background:#111;color:#eee;font-family:sans-serif;font-size:18px}')
        p.append('a{color:#fff;text-decoration:none}')
        p.append('.tabs{display:flex;background:#222;position:sticky;top:0;z-index:10}')
        p.append('.tab{flex:1;padding:12px 0;text-align:center;font-size:20px;font-weight:bold;cursor:pointer;border-bottom:3px solid transparent}')
        p.append('.tab.active{border-bottom-color:#e62429;color:#e62429}')
        p.append('.tab:focus{outline:2px solid #e62429;outline-offset:-2px}')
        p.append('.section{display:none;padding:10px 16px}')
        p.append('.section.active{display:block}')
        p.append('.series-title{font-size:18px;font-weight:bold;padding:10px 0 6px;border-bottom:1px solid #333;margin-top:16px;cursor:pointer;color:#ccc}')
        p.append('.series-title:hover,.series-title:focus{color:#fff;outline:2px solid #e62429;outline-offset:-2px}')
        p.append('.series-count{font-size:14px;color:#888;margin-left:8px}')
        p.append('.item-list{margin:4px 0 8px 0}')
        p.append('.item{padding:8px 12px;margin:3px 0;border-radius:6px;background:#1a1a1a;display:block;color:#eee;font-size:16px}')
        p.append('.item:hover,.item:focus{background:#2a2a2a;outline:2px solid #e62429;outline-offset:-2px}')
        p.append('.item-sub{font-size:13px;color:#888;margin-left:8px}')
        p.append('.ep-list{margin:4px 0 4px 20px}')
        p.append('.ep{display:inline-block;padding:6px 14px;margin:3px;border-radius:4px;background:#252525;color:#eee;font-size:15px;cursor:pointer}')
        p.append('.ep:hover,.ep:focus{background:#e62429;outline:2px solid #fff;outline-offset:-2px}')
        p.append('.tv-focused{outline:3px solid #fff!important;background:#2a2a2a!important;}')
        p.append('.ep.tv-focused{background:#e62429!important;}')
        p.append('.tab.tv-focused{border-bottom-color:#fff!important;color:#fff!important;}')
        p.append('.loading{color:#888;padding:20px;text-align:center}')
        p.append('.play-page{display:none;position:fixed;top:0;left:0;width:100%;height:100%;background:#000;z-index:100;flex-direction:column;justify-content:center;align-items:center}
        .play-page video{width:100%;height:100%;object-fit:contain}
        .play-ctrls{position:absolute;top:0;left:0;width:100%;padding:10px 20px;display:flex;justify-content:flex-end;gap:12px;z-index:102;background:linear-gradient(to bottom,rgba(0,0,0,0.7) 0%,transparent 100%)}
        .play-ctrl-btn{color:#fff;font-size:20px;background:rgba(0,0,0,0.7);border:2px solid #555;border-radius:8px;padding:8px 16px;cursor:pointer;outline:none}
        .play-ctrl-btn.tv-focused{background:#e62429;border-color:#e62429}')
        p.append('.play-page video{display:block;margin:auto}')
        p.append('.play-close{position:absolute;top:20px;right:20px;color:#fff;font-size:32px;cursor:pointer;z-index:101;background:rgba(0,0,0,0.7);border:none;padding:8px 16px;border-radius:6px}')
        p.append('.play-speed{position:absolute;top:20px;right:90px;color:#fff;font-size:20px;cursor:pointer;z-index:101;background:rgba(0,0,0,0.7);border:none;padding:8px 16px;border-radius:6px;outline:none}')
        p.append('.play-speed.tv-focused{background:#e62429;}')
        p.append('.speed-overlay{display:none;position:fixed;bottom:60px;left:50%;transform:translateX(-50%);background:rgba(0,0,0,0.85);color:#fff;padding:10px 18px;border-radius:10px;display:flex;gap:10px;z-index:9999;font-size:18px;}')
        p.append('.speed-opt{padding:6px 14px;border-radius:6px;cursor:pointer;font-weight:normal;background:transparent;color:#fff;}')
        p.append('.speed-opt.active{font-weight:bold;background:#e62429;}')
        p.append('</style></head><body>')

        active_cats = [ck for ck, cn, _ in self._TV_CATS if os.path.isfile(os.path.join(MV_DIR, 'data', ck + '-data.js'))]
        cat_names = {}
        for ck, cn, _ in self._TV_CATS:
            cat_names[ck] = cn

        if active_cats:
            p.append('<div class="tabs">')
            for i, ck in enumerate(active_cats):
                cls = 'tab active' if i == 0 else 'tab'
                p.append('<div class="' + cls + '" data-action="tab" data-cat="' + ck + '">' + _e(cat_names[ck]) + '</div>')
            p.append('</div>')
            for i, ck in enumerate(active_cats):
                cls = 'section active' if i == 0 else 'section'
                p.append('<div class="' + cls + '" id="cat-' + ck + '"><div class="loading">加载中...</div></div>')

        p.append('<div class="play-page" id="play-page">
        <div class="play-ctrls">
          <button class="play-ctrl-btn" data-action="speed" id="btn-speed">速度 1.0x</button>
          <button class="play-ctrl-btn" data-action="close-play">&#10005;</button>
        </div>
        <video id="tv-video" autoplay></video>
      </div>')
        p.append('<div id="speed-overlay" class="speed-overlay"></div>')

        # JS（ES5兼容）— 事件委托，无内联onclick（VIA .click()不触发innerHTML的onclick）
        p.append('<script>')
        p.append('var cats=' + json.dumps(active_cats) + ';')
        p.append('var _loaded={};var _loading={};var _current="' + (active_cats[0] if active_cats else '') + '";')
        # _doAction — 统一事件分发
        p.append('function _doAction(el){if(!el)return;')
        p.append('var a=el.getAttribute("data-action");if(!a)return;')
        p.append('if(a==="tab"){var c=el.getAttribute("data-cat");if(c)showCat(c);}')
        p.append('else if(a==="toggle"){var id=el.getAttribute("data-id");if(id)toggle(id);}')
        p.append('else if(a==="play"){var url=el.getAttribute("data-url");if(url)play(url);}')
        p.append('else if(a==="close-play"){stopPlay();_inPlayer=false;_tvRebuild();}')
        p.append('else if(a==="speed"){_doSpeed();}}')
        # showCat
        p.append('function showCat(c){')
        p.append('if(_current===c)return;_current=c;')
        p.append('for(var i=0;i<cats.length;i++){')
        p.append('var t=document.querySelector(".tab:nth-child("+(i+1)+")");')
        p.append('var s=document.getElementById("cat-"+cats[i]);')
        p.append('if(cats[i]===c){t.className="tab active";s.className="section active";}')
        p.append('else{t.className="tab";s.className="section";}')
        p.append('}if(!_loaded[c]&&!_loading[c]){loadCat(c);}_tvRebuild();}')
        # loadCat
        p.append('function loadCat(c){')
        p.append('if(_loading[c])return;_loading[c]=1;')
        p.append('var s=document.getElementById("cat-"+c);')
        p.append('s.innerHTML=\'<div class="loading">加载中...</div>\';')
        p.append('var x=new XMLHttpRequest();')
        p.append('x.open("GET","/tv/data/"+c,true);')
        p.append('x.onload=function(){')
        p.append('if(x.status===200){s.innerHTML=x.responseText;_loaded[c]=1;_loading[c]=0;')
        p.append('_tvBuildList();if(!_tvFocused&&_tvList.length)_tvSetFocus(_tvList[0]);}')
        p.append('else{s.innerHTML=\'<div class="loading">加载失败</div>\';_loading[c]=0;}')
        p.append('};x.onerror=function(){s.innerHTML=\'<div class="loading">网络错误</div>\';_loading[c]=0;};')
        p.append('x.send();}')
        # toggle
        p.append('function toggle(id){var el=document.getElementById(id);if(!el)return;')
        p.append('el.style.display=el.style.display==="none"?"block":"none";_tvRebuild();}')
        # play → 跳转到 player.html（带加速播放的专用页面）
        p.append('function play(url){')
        p.append('window.location.href="/player.html?url="+encodeURIComponent(url);}')
        # stopPlay
        p.append('function stopPlay(){var pg=document.getElementById("play-page");var v=document.getElementById("tv-video");')
                // --- 速度控制 ---
        var _spdList=[0.5,0.75,1.0,1.25,1.5,2.0];var _spdIdx=2;
        function _cycleSpeed(){
          _spdIdx=(_spdIdx+1)%_spdList.length;
          var v=document.getElementById("tv-video");
          if(v){v.playbackRate=_spdList[_spdIdx];}
          var b=document.getElementById("btn-speed");
          if(b){b.textContent="速度 "+_spdList[_spdIdx]+"x";}
          _showSpdTip();
        }
        function _showSpdTip(){
          var v=document.getElementById("tv-video");if(!v)return;
          var tip=document.getElementById("spd-tip");
          if(!tip){tip=document.createElement("div");tip.id="spd-tip";
            tip.style.cssText="position:fixed;top:50%;left:50%;transform:translate(-50%,-50%);"+
              "background:rgba(0,0,0,0.85);color:#fff;font-size:36px;padding:20px 40px;"+
              "border-radius:12px;z-index:99999;pointer-events:none;opacity:0;transition:opacity 0.3s";
            document.body.appendChild(tip);
          }
          tip.textContent=_spdList[_spdIdx]+"x";
          tip.style.opacity="1";
          clearTimeout(tip._t);
          tip._t=setTimeout(function(){tip.style.opacity="0";},1500);
        }
        function _setSpeed(idx){
          _spdIdx=idx;
          var v=document.getElementById("tv-video");
          if(v){v.playbackRate=_spdList[idx];}
          var b=document.getElementById("btn-speed");
          if(b){b.textContent="速度 "+_spdList[idx]+"x";}
        }else{_showSpeed();}}
        p.append('v.pause();v.src="";pg.style.display="none";}')
        # focus system — linear prev/next, select by [data-action]
        p.append('var _tvFocused=null;var _tvList=[];var _tvNeedRebuild=true;')
        p.append('function _tvRebuild(){_tvNeedRebuild=true;}')
        p.append('function _tvBuildList(){')
        p.append('_tvList=[];var pg=document.getElementById("play-page");')
        p.append('var inP=pg&&pg.style.display!=="none";var root=inP?pg:document;')
        p.append('var els=root.querySelectorAll("[data-action]");for(var i=0;i<els.length;i++){')
        p.append('var r=els[i].getBoundingClientRect();if(r.width>1&&r.height>1&&r.bottom>0&&r.top<window.innerHeight)_tvList.push(els[i]);}')
        p.append('_tvNeedRebuild=false;}')
        p.append('function _tvSetFocus(el){if(!el)return;if(_tvFocused)_tvFocused.classList.remove("tv-focused");_tvFocused=el;el.classList.add("tv-focused");')
        p.append('try{el.scrollIntoView(false);}catch(e){}}')
        p.append('function _tvNavigate(dir){')
        p.append('if(_tvNeedRebuild)_tvBuildList();')
        p.append('if(!_tvList.length)return;if(!_tvFocused){_tvSetFocus(_tvList[0]);return;}')
        p.append('var idx=-1;for(var i=0;i<_tvList.length;i++){if(_tvList[i]===_tvFocused){idx=i;break;}}')
        p.append('if(idx<0){_tvSetFocus(_tvList[0]);return;}')
        p.append('if(dir==="up"||dir==="left"){if(idx>0)_tvSetFocus(_tvList[idx-1]);}')
        p.append('else{if(idx<_tvList.length-1)_tvSetFocus(_tvList[idx+1]);}}')
        # keyboard — Enter calls _doAction directly, bypasses .click()
        p.append('document.onkeydown=function(e){try{')
        p.append('var k=e.keyCode;var pg=document.getElementById("play-page");')
        p.append('if(pg&&pg.style.display!=="none"){')
        p.append('if(k===13||k===32){var pg2=document.getElementById("play-page");var v2=document.getElementById("tv-video");if(pg2&&pg2.style.display!=="none"){if(k===13){_cycleSpeed();}else{if(v2.paused){try{v2.play();}catch(ex){v2.muted=true;v2.play();}}else{v2.pause();}}e.preventDefault();return false;}')
        p.append('if(k===4||k===27){stopPlay();_inPlayer=false;_tvRebuild();e.preventDefault();return false;}')
        p.append('return true;}')
        p.append('if(k===38){_tvNavigate("up");e.preventDefault();return false;}')
        p.append('if(k===40){_tvNavigate("down");e.preventDefault();return false;}')
        p.append('if(k===37){_tvNavigate("left");e.preventDefault();return false;}')
        p.append('if(k===39){_tvNavigate("right");e.preventDefault();return false;}')
        p.append('if(k===13||k===32){if(_tvFocused){_doAction(_tvFocused);}e.preventDefault();return false;}')
        p.append('}catch(err){}return true;};')
        # click event delegation
        p.append('document.addEventListener("click",function(e){var el=e.target;')
        p.append('while(el&&el!==document){if(el.getAttribute("data-action")){_tvBuildList();')
        p.append('_tvSetFocus(el);_doAction(el);break;}el=el.parentNode;}},true);')
        # Back key
        p.append('var _inPlayer=false;')
        p.append('window.onpopstate=function(e){if(_inPlayer){stopPlay();_inPlayer=false;_tvRebuild();}};')
        # auto-load first cat
        if active_cats:
            p.append('loadCat("' + active_cats[0] + '");')
        p.append('</script></body></html>')

        html = ''.join(p)
        encoded = html.encode('utf-8')
        self._send_response_gzip(encoded, 'text/html; charset=utf-8', {'Cache-Control': 'no-cache, no-store, must-revalidate', 'Pragma': 'no-cache', 'Expires': '0'})

    def _handle_tv_series_data(self, cat_key, series_index):
        """返回指定系列内的影片/剧集HTML片段（data-action方式，VIA确定键兼容）"""
        _e = self._tv_escape
        cd = self._tv_parse_data(cat_key)
        if cd is None:
            self._send_simple_html('<div class="loading">暂无数据</div>')
            return
        data_obj = cd.get('data', {})
        idx_obj = cd.get('index', {})
        series_names = sorted(data_obj.keys(), key=lambda k: (idx_obj.get(k,{}).get('count',0)), reverse=True)
        if series_index < 0 or series_index >= len(series_names):
            self._send_simple_html('<div class="loading">暂无数据</div>')
            return
        sname = series_names[series_index]
        series = data_obj[sname]
        spath = series.get('path', '').replace('\\','/')
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
                title_html += '<span class="vsub">' + str(year) + '年</span>'
            p.append('<div class="vitem" data-action="play" data-url="' + _e(url) + '">' + title_html + '</div>')
        for item in series.get('shows', []):
            stitle = item.get('title', '')
            episodes = item.get('episodes', [])
            epath = (item.get('path') or spath).replace('\\','/')
            ep_count = item.get('episodeCount', len(episodes))
            p.append('<div class="show-label">' + _e(stitle)
                     + '<span class="vsub">' + str(ep_count) + '集</span></div>')
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
                p.append('<div class="vitem" style="display:inline-block;padding:6px 14px;margin:3px;border-radius:4px;background:#252525;font-size:15px" data-action="play" data-url="' + _e(eurl) + '">' + _e(ep_label) + '</div>')
            p.append('</div>')
        html = ''.join(p) if p else '<div class="loading">暂无内容</div>'
        encoded = html.encode('utf-8')
        self._send_response_gzip(encoded, 'text/html; charset=utf-8', {'Cache-Control': 'no-cache, no-store, must-revalidate', 'Pragma': 'no-cache', 'Expires': '0'})

    def _send_simple_html(self, html_str):
        self.send_response(200)
        self.send_header('Content-Type', 'text/html; charset=utf-8')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        self.wfile.write(html_str.encode('utf-8'))

    def _handle_tv_data(self, cat_key):
        """返回指定分类的HTML片段（按需加载）"""
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
        if not data_obj:
            self.send_response(200)
            self.send_header('Content-Type', 'text/html; charset=utf-8')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            self.wfile.write('<div class="loading">暂无数据</div>'.encode('utf-8'))
            return
        p = []
        series_names = sorted(data_obj.keys(), key=lambda k: (idx_obj.get(k,{}).get('count',0)), reverse=True)
        for sname in series_names:
            series = data_obj[sname]
            spath = series.get('path', '').replace('\\','/')
            display_name = idx_obj.get(sname, {}).get('displayName', sname)
            count = series.get('count', 0)
            series_id = 's-' + cat_key + '-' + _e(sname).replace(' ','-')
            p.append('<div class="series-title" data-action="toggle" data-id="' + series_id + '">'
                     + _e(display_name) + '<span class="series-count">(' + str(count) + '部)</span></div>')
            p.append('<div class="item-list" id="' + series_id + '" style="display:none">')
            movies = series.get('movies', [])
            shows = series.get('shows', [])
            for item in movies:
                f = item.get('file','')
                subdir = item.get('subdir', '')
                media_file = subdir + '/' + f if subdir else f
                url = self._tv_media_url(spath, media_file) if f else ''
                title = item.get('title', f)
                year = item.get('year','')
                actor = item.get('actor','')
                sub = ''
                if year: sub += str(year) + '年 '
                if actor: sub += _e(actor)
                if url:
                    p.append('<div class="vitem" data-action="play" data-url="' + _e(url) + '">' + _e(title))
                    if sub: p.append('<span class="vsub">' + sub + '</span>')
                    p.append('</div>')
            for item in shows:
                stitle = item.get('title', '')
                episodes = item.get('episodes', [])
                epath = (item.get('path') or spath).replace('\\','/')
                ep_count = item.get('episodeCount', len(episodes))
                p.append('<div class="vitem" style="cursor:default">' + _e(stitle)
                         + '<span class="vsub">' + str(ep_count) + '集</span></div>')
                p.append('<div class="ep-list">')
                for ep in episodes:
                    ef = ep.get('file','')
                    subdir = ep.get('subdir','')
                    if subdir:
                        eurl = self._tv_media_url(epath, subdir + '/' + ef)
                    else:
                        eurl = self._tv_media_url(epath, ef)
                    ep_num = ep.get('episode', None)
                    if ep_num is not None and ep_num != 0:
                        ep_label = str(ep_num)
                    else:
                        ep_label = str(episodes.index(ep) + 1)
                    p.append('<div class="ep" data-action="play" data-url="' + _e(eurl) + '">' + _e(ep_label) + '</div>')
                p.append('</div>')
            p.append('</div>')
        html = ''.join(p)
        encoded = html.encode('utf-8')
        self._send_response_gzip(encoded, 'text/html; charset=utf-8', {'Cache-Control': 'no-cache, no-store, must-revalidate', 'Pragma': 'no-cache', 'Expires': '0'})

    # 可 gzip 压缩的 MIME 类型
    _GZIP_TYPES = {
        'application/javascript', 'text/css', 'text/html',
        'application/json', 'text/plain',
    }

    def _should_gzip(self, content_type):
        base = content_type.split(';')[0].strip().lower()
        return base in self._GZIP_TYPES

    def _handle_tv2_page(self):
        """TV页面 - 服务端全量渲染，onclick直接在HTML里，确认键走.click()"""
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
        p.append('.tab.tv-focused{outline:3px solid #fff;border-bottom-color:#fff!important;color:#fff!important}')
        p.append('.cat{display:none;padding:10px 16px}')
        p.append('.cat.active{display:block}')
        p.append('.stitle{font-size:18px;font-weight:bold;padding:10px 0 6px;border-bottom:1px solid #333;margin-top:12px;cursor:pointer;color:#ccc}')
        p.append('.stitle.tv-focused{outline:3px solid #fff;color:#fff!important}')
        p.append('.scount{font-size:14px;color:#888;margin-left:8px}')
        p.append('.ilist{margin:4px 0 8px 0;display:none}')
        p.append('.ilist.open{display:block;overflow:hidden}')
        p.append('.vitem{display:block;padding:10px 12px;background:#1a1a1a;border-radius:6px;cursor:pointer;font-size:17px;min-height:44px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}')
        p.append('.vitem.tv-focused{outline:3px solid #fff;background:#333}')
        p.append('.ep{display:inline-block;padding:6px 14px;margin:3px 4px 3px 0;border-radius:4px;background:#252525;font-size:15px;cursor:pointer}')
        p.append('.ep.tv-focused{outline:2px solid #fff;background:#444}')
        p.append('.vsub{font-size:13px;color:#888;margin-left:8px}')
        p.append('.show-label{padding:10px 12px;margin:4px 0 0 0;color:#aaa;font-size:17px;display:block;clear:both}')
        p.append('.loading{color:#888;padding:10px 12px;font-size:14px}')
        p.append('.play-page{display:none;position:fixed;top:0;left:0;width:100%;height:100%;background:#000;z-index:100;flex-direction:column;justify-content:center;align-items:center}
        .play-page video{width:100%;height:100%;object-fit:contain}
        .play-ctrls{position:absolute;top:0;left:0;width:100%;padding:10px 20px;display:flex;justify-content:flex-end;gap:12px;z-index:102;background:linear-gradient(to bottom,rgba(0,0,0,0.7) 0%,transparent 100%)}
        .play-ctrl-btn{color:#fff;font-size:20px;background:rgba(0,0,0,0.7);border:2px solid #555;border-radius:8px;padding:8px 16px;cursor:pointer;outline:none}
        .play-ctrl-btn.tv-focused{background:#e62429;border-color:#e62429}')
        p.append('.play-page video{display:block;margin:auto}')
        p.append('.play-close{position:absolute;top:20px;right:20px;color:#fff;font-size:32px;cursor:pointer;z-index:101;background:rgba(0,0,0,0.7);border:none;padding:8px 16px;border-radius:6px}')
        p.append('.speed-overlay{display:none;position:fixed;bottom:60px;left:50%;transform:translateX(-50%);background:rgba(0,0,0,0.85);color:#fff;padding:10px 18px;border-radius:10px;display:flex;gap:10px;z-index:9999;font-size:18px;}')
        p.append('.speed-opt{padding:6px 14px;border-radius:6px;cursor:pointer;font-weight:normal;background:transparent;color:#fff;}')
        p.append('.speed-opt.active{font-weight:bold;background:#e62429;}')
        p.append('</style></head><body>')
        p.append('<script src="/tv-speed.js"></script>')

        # 只渲染tabs + 系列标题，内容按需XHR加载
        active_cats = [('movie','电影'),('tv','电视剧'),('anime','动画片'),('doc','纪录片')]
        cat_data = {}
        for ck, cn in active_cats:
            cd = self._tv_parse_data(ck)
            if cd and cd.get('data'):
                cat_data[ck] = cd

        # tabs（data-action统一事件分发，兼容VIA）
        p.append('<div class="tabs">')
        first = True
        for ck, cn in active_cats:
            if ck not in cat_data:
                continue
            cls = 'tab active' if first else 'tab'
            p.append('<div class="' + cls + '" data-action="switchCat" data-cat="' + ck + '">' + cn + '</div>')
            first = False
        p.append('</div>')

        # 只渲染系列标题（折叠），不渲染影片列表
        first = True
        for ck, cn in active_cats:
            if ck not in cat_data:
                continue
            cls = 'cat active' if first else 'cat'
            p.append('<div class="' + cls + '" id="cat-' + ck + '">')
            first = False
            cd = cat_data[ck]
            data_obj = cd.get('data', {})
            idx_obj = cd.get('index', {})
            series_names = sorted(data_obj.keys(), key=lambda k: (idx_obj.get(k,{}).get('count',0)), reverse=True)
            for si, sname in enumerate(series_names):
                series = data_obj[sname]
                display_name = idx_obj.get(sname, {}).get('displayName', sname)
                count = series.get('count', 0)
                sid = ck + '-s' + str(si)
                p.append('<div class="stitle" data-action="toggle" data-sid="' + sid + '" data-ck="' + ck + '" data-si="' + str(si) + '">'
                         + _e(display_name) + '<span class="scount">(' + str(count) + '部)</span></div>')
                p.append('<div class="ilist" id="il-' + sid + '"></div>')
            p.append('</div>')

        # player
        p.append('<div class="play-page" id="play-page">')
        p.append('<button class="play-close" data-action="close-play">&#10005;</button>')
        p.append('<button id="btn-spd" data-action="cycle-spd" style="position:absolute;top:20px;right:90px;padding:8px 18px;background:rgba(230,36,41,0.9);color:#fff;border:none;border-radius:6px;font-size:18px;cursor:pointer;z-index:101;font-weight:bold">▶ 1.0x</button>')
        p.append('<video id="vid" controls autoplay></video>')
        p.append('<button class="kodi-btn" data-action="play-kodi" style="position:absolute;bottom:20px;right:20px;padding:10px 20px;background:#e62429;color:#fff;border:none;border-radius:6px;font-size:16px;cursor:pointer">用KODI播放</button>')
        p.append('</div>')

        # JS — 引用独立文件，避免Python字符串拼接问题
        p.append('<script src="/tv2.js"></script>')
        p.append('</body></html>')
        html = ''.join(p)
        encoded = html.encode('utf-8')
        self._send_response_gzip(encoded, 'text/html; charset=utf-8', {'Cache-Control': 'no-cache, no-store, must-revalidate', 'Pragma': 'no-cache', 'Expires': '0'})

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

    def _send_rewritten(self, fs_path):
        """读取文件，H:/ → /media/H/, I:/ → /media/I/，直接发送（支持gzip）"""
        with open(fs_path, 'r', encoding='utf-8', errors='replace') as f:
            content = f.read()

        # 核心替换：盘符路径 → HTTP路径
        for disk_letter, disk_path in DISK_MAP.items():
            http_prefix = f'/media/{disk_letter}/'
            content = content.replace(disk_path, http_prefix).replace(
                disk_path.replace('/', '\\'), http_prefix)

        encoded = content.encode('utf-8')
        mime = self._guess_mime(fs_path)
        ext = os.path.splitext(fs_path)[1].lower()
        extra = {'Access-Control-Allow-Origin': '*'}
        if ext in ('.js', '.css', '.html', '.htm'):
            extra['Cache-Control'] = 'no-cache, no-store, must-revalidate'
            extra['Pragma'] = 'no-cache'
            extra['Expires'] = '0'
        self._send_response_gzip(encoded, mime, extra)

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
        self.send_header('Content-Range', f'bytes {start}-{end}/{file_size}')
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
        if ext in ('.jpg', '.jpeg'):
            return 'image/jpeg'
        if ext == '.png':
            return 'image/png'
        if ext == '.webp':
            return 'image/webp'
        return 'application/octet-stream'

    def end_headers(self):
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Headers', 'Range')
        # 开发阶段：HTML/JS/CSS/数据文件禁用缓存
        path_lower = self.path.lower().split('?')[0]
        if path_lower.endswith(('.html', '.htm', '.js', '.css')) or path_lower == '/':
            self.send_header('Cache-Control', 'no-cache, no-store, must-revalidate')
            self.send_header('Pragma', 'no-cache')
            self.send_header('Expires', '0')
        if any(self.path.endswith(ext) for ext in VIDEO_EXTENSIONS):
            self.send_header('Accept-Ranges', 'bytes')
        super().end_headers()

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Range, Content-Type')
        self.end_headers()

    def log_message(self, format, *args):
        sys.stdout.write("%s  %s\n" % (self.log_date_time_string(), args[0]))
        sys.stdout.flush()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='尚唯云影库 HTTP 服务器')
    parser.add_argument('--port', type=int, default=PORT, help=f'监听端口（默认 {PORT}）')
    parser.add_argument('--quiet', action='store_true', help='静默模式')
    args = parser.parse_args()

    listen_port = args.port

    # pythonw.exe 后台运行时 stdout/stderr 为 None，写入会崩溃
    if sys.executable.endswith('pythonw.exe'):
        sys.stdout = open(os.devnull, 'w')
        sys.stderr = sys.stdout

    server = socketserver.ThreadingTCPServer(('0.0.0.0', listen_port), MediaServer)
    server.daemon_threads = True

    # Also listen on IPv6 for hostname resolution (e.g. http://SETH:8082)
    server_v6 = None
    try:
        import socket as _sock2
        v6_class = type(server)  # same class
        # Create IPv6 server with dual-stack
        class IPv6Server(socketserver.ThreadingTCPServer):
            address_family = _sock2.AF_INET6
            allow_reuse_address = True
            def server_bind(self):
                self.socket.setsockopt(_sock2.IPPROTO_IPV6, _sock2.IPV6_V6ONLY, 0)
                super().server_bind()
        server_v6 = IPv6Server(('::', listen_port), MediaServer)
        server_v6.daemon_threads = True
        import threading
        threading.Thread(target=server_v6.serve_forever, daemon=True).start()
    except Exception as e:
        if not args.quiet:
            print(f'  IPv6监听未启动: {e}')
        server_v6 = None

    import socket as _sock
    _local_ip = '127.0.0.1'
