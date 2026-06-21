#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""自动将上传功能补丁应用到 server.py"""
import os
import re

SERVER_PATH = r'G:\AI\PZ\server.py'

# 读取 server.py
with open(SERVER_PATH, 'r', encoding='utf-8') as f:
    content = f.read()

# 1. 在 do_POST 中添加上传路由
old_post = '''    def do_POST(self):
        if self.path == '/api/scan':
            return self.handle_scan()
        self.send_error(404)'''

new_post = '''    def do_POST(self):
        if self.path == '/api/scan':
            return self.handle_scan()
        if self.path == '/api/upload':
            return self.handle_upload()
        self.send_error(404)'''

if old_post in content:
    content = content.replace(old_post, new_post)
    print('✓ 已添加 /api/upload 路由')
else:
    print('⚠ do_POST 中已有 /api/upload 路由，跳过')

# 2. 在 handle_scan 方法前插入上传相关方法
upload_methods = '''
    # ---- 照片上传 ----
    def handle_upload(self):
        """处理照片上传"""
        content_type = self.headers.get('Content-Type', '')
        if 'multipart/form-data' not in content_type:
            self._send_json(400, {'success': False, 'error': '需要 multipart/form-data'})
            return

        try:
            boundary = None
            for part in content_type.split(';'):
                part = part.strip()
                if part.startswith('boundary='):
                    boundary = part[9:].strip('"')
                    break

            if not boundary:
                self._send_json(400, {'success': False, 'error': '缺少 boundary'})
                return

            content_length = int(self.headers.get('Content-Length', 0))
            body = self.rfile.read(content_length)

            fields = {}
            files = []
            self._parse_multipart(body, boundary.encode(), fields, files)

            owner = fields.get('owner', '')
            date_str = fields.get('date', '')
            event = fields.get('event', '')
            persons = fields.get('persons', '')
            location = fields.get('location', '')

            if not owner or not event:
                self._send_json(400, {'success': False, 'error': '归属和事件类型为必填'})
                return

            if len(files) == 0:
                self._send_json(400, {'success': False, 'error': '请选择至少一张照片'})
                return

            date_compact = self._format_date_compact(date_str)

            folder_parts = [owner, date_compact, event]
            if persons:
                folder_parts.append(persons.replace('/', '-'))
            elif location:
                folder_parts.append(location)
            
            target_folder_name = '-'.join(folder_parts)
            photo_root = r'G:\\照片'
            target_dir = os.path.join(photo_root, target_folder_name)
            os.makedirs(target_dir, exist_ok=True)

            saved_count = 0
            for file_info in files:
                filename = file_info['filename']
                data = file_info['data']
                safe_name = os.path.basename(filename)
                if not safe_name:
                    safe_name = f'upload_{saved_count + 1}.jpg'
                target_path = os.path.join(target_dir, safe_name)
                base, ext = os.path.splitext(safe_name)
                counter = 1
                while os.path.exists(target_path):
                    target_path = os.path.join(target_dir, f'{base}_{counter}{ext}')
                    counter += 1
                with open(target_path, 'wb') as f:
                    f.write(data)
                saved_count += 1

            print(f'[Upload] 已上传 {saved_count} 张照片到 {target_folder_name}')
            self._trigger_rescan()
            self._send_json(200, {
                'success': True, 'count': saved_count,
                'folder': target_folder_name, 'path': target_dir
            })
        except Exception as e:
            print(f'[Upload] 错误: {e}')
            import traceback
            traceback.print_exc()
            self._send_json(500, {'success': False, 'error': str(e)})

    def _parse_multipart(self, body, boundary, fields, files):
        """解析 multipart/form-data"""
        delimiter = b'--' + boundary
        parts = body.split(delimiter)
        for part in parts[1:]:
            if part.strip() == b'--' or part.strip() == b'--\\r\\n':
                continue
            if not part.strip():
                continue
            if b'\\r\\n\\r\\n' in part:
                header_section, content = part.split(b'\\r\\n\\r\\n', 1)
            else:
                continue
            header_text = header_section.decode('utf-8', errors='replace')
            name = None
            filename = None
            for line in header_text.split('\\r\\n'):
                if 'Content-Disposition' in line:
                    name_match = re.search(r'name="([^"]+)"', line)
                    if name_match:
                        name = name_match.group(1)
                    filename_match = re.search(r'filename="([^"]+)"', line)
                    if filename_match:
                        filename = filename_match.group(1)
            if not name:
                continue
            if content.endswith(b'\\r\\n'):
                content = content[:-2]
            if filename:
                files.append({'name': name, 'filename': filename, 'data': content})
            else:
                fields[name] = content.decode('utf-8', errors='replace').strip()

    def _format_date_compact(self, date_str):
        """将日期字符串转为 YYYYMMDD 格式"""
        if not date_str:
            return '00000000'
        parts = date_str.replace('/', '-').split('-')
        if len(parts) == 3:
            return parts[0].zfill(4) + (parts[1] or '00').zfill(2) + (parts[2] or '00').zfill(2)
        elif len(parts) == 2:
            return parts[0].zfill(4) + (parts[1] or '00').zfill(2) + '00'
        elif len(parts) == 1:
            return parts[0].zfill(4) + '0000'
        return '00000000'

    def _trigger_rescan(self):
        """触发增量扫描以更新网站数据"""
        import subprocess
        script = os.path.join(WEB_DIR, 'auto_scan.py')
        try:
            subprocess.Popen(
                [sys.executable, script],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )
            print('[Upload] 已触发后台扫描更新')
        except Exception as e:
            print(f'[Upload] 扫描触发失败: {e}')

    def _send_json(self, code, data):
        """发送 JSON 响应"""
        resp = json.dumps(data, ensure_ascii=False).encode('utf-8')
        self.send_response(code)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Content-Length', len(resp))
        self.end_headers()
        self.wfile.write(resp)

'''

# 在 handle_scan 方法之前插入
if 'def handle_upload' not in content:
    marker = '    # ---- 数据扫描 ----'
    if marker in content:
        content = content.replace(marker, upload_methods + marker)
        print('✓ 已添加上传相关方法')
    else:
        # 尝试在 handle_scan 之前插入
        marker2 = '    def handle_scan(self):'
        if marker2 in content:
            content = content.replace(marker2, upload_methods + marker2)
            print('✓ 已添加上传相关方法（备选位置）')
        else:
            print('✗ 未找到插入位置')

# 写回
with open(SERVER_PATH, 'w', encoding='utf-8') as f:
    f.write(content)

print('✓ server.py 已更新')
