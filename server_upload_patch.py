#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
server.py 上传功能补丁

将此文件中的代码合并到 G:\AI\PZ\server.py 中
需要在 do_POST 方法中添加 /api/upload 路由
"""

# ===== 在 do_POST 方法中添加以下路由 =====
# 在 do_POST 中 /api/scan 之后添加:
#
#     if self.path == '/api/upload':
#         return self.handle_upload()

# ===== 在 PhotoHandler 类中添加以下方法 =====

HANDLE_UPLOAD_CODE = '''
    # ---- 照片上传 ----
    def handle_upload(self):
        """处理照片上传
        
        接收 multipart/form-data，包含：
        - owner: 归属 (R/S/S&R)
        - date: 日期 (YYYY-MM-DD 或 YYYY-MM 或 YYYY)
        - event: 事件类型
        - persons: 人物（可选）
        - location: 地点（可选）
        - photos: 多个照片文件
        """
        content_type = self.headers.get('Content-Type', '')
        if 'multipart/form-data' not in content_type:
            self._send_json(400, {'success': False, 'error': '需要 multipart/form-data'})
            return

        try:
            # 解析 boundary
            boundary = None
            for part in content_type.split(';'):
                part = part.strip()
                if part.startswith('boundary='):
                    boundary = part[9:].strip('"')
                    break

            if not boundary:
                self._send_json(400, {'success': False, 'error': '缺少 boundary'})
                return

            # 读取所有数据
            content_length = int(self.headers.get('Content-Length', 0))
            body = self.rfile.read(content_length)

            # 解析 multipart
            fields = {}
            files = []
            self._parse_multipart(body, boundary.encode(), fields, files)

            # 提取表单字段
            owner = fields.get('owner', '')
            date_str = fields.get('date', '')
            event = fields.get('event', '')
            persons = fields.get('persons', '')
            location = fields.get('location', '')

            # 验证必填字段
            if not owner or not event:
                self._send_json(400, {'success': False, 'error': '归属和事件类型为必填'})
                return

            if len(files) == 0:
                self._send_json(400, {'success': False, 'error': '请选择至少一张照片'})
                return

            # 格式化日期为 YYYYMMDD
            date_compact = self._format_date_compact(date_str)

            # 构建文件夹名称：[归属]-[日期]-[事件]-[人物或地点]
            folder_parts = [owner, date_compact, event]
            if persons:
                folder_parts.append(persons.replace('/', '-'))
            elif location:
                folder_parts.append(location)
            
            target_folder_name = '-'.join(folder_parts)

            # 目标目录
            photo_root = r'G:\\照片'
            target_dir = os.path.join(photo_root, target_folder_name)

            # 创建目录
            os.makedirs(target_dir, exist_ok=True)

            # 保存文件
            saved_count = 0
            for file_info in files:
                filename = file_info['filename']
                data = file_info['data']

                # 确保文件名安全
                safe_name = os.path.basename(filename)
                if not safe_name:
                    safe_name = f'upload_{saved_count + 1}.jpg'

                # 如果文件已存在，添加序号
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

            # 自动触发增量扫描更新网站数据
            self._trigger_rescan()

            self._send_json(200, {
                'success': True,
                'count': saved_count,
                'folder': target_folder_name,
                'path': target_dir
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

        for part in parts[1:]:  # 跳过第一个空部分和最后的结束标记
            if part.strip() == b'--' or part.strip() == b'--\\r\\n':
                continue
            if not part.strip():
                continue

            # 分离头部和内容
            if b'\\r\\n\\r\\n' in part:
                header_section, content = part.split(b'\\r\\n\\r\\n', 1)
            else:
                continue

            # 解析 Content-Disposition
            header_text = header_section.decode('utf-8', errors='replace')
            
            name = None
            filename = None
            for line in header_text.split('\\r\\n'):
                if 'Content-Disposition' in line:
                    import re
                    name_match = re.search(r'name="([^"]+)"', line)
                    if name_match:
                        name = name_match.group(1)
                    filename_match = re.search(r'filename="([^"]+)"', line)
                    if filename_match:
                        filename = filename_match.group(1)

            if not name:
                continue

            # 去除尾部 \\r\\n
            if content.endswith(b'\\r\\n'):
                content = content[:-2]

            if filename:
                files.append({
                    'name': name,
                    'filename': filename,
                    'data': content
                })
            else:
                fields[name] = content.decode('utf-8', errors='replace').strip()

    def _format_date_compact(self, date_str):
        """将日期字符串转为 YYYYMMDD 格式"""
        if not date_str:
            return '00000000'
        
        parts = date_str.replace('/', '-').split('-')
        
        if len(parts) == 3:
            year = parts[0].zfill(4)
            month = parts[1].zfill(2) if parts[1] else '00'
            day = parts[2].zfill(2) if parts[2] else '00'
            return f'{year}{month}{day}'
        elif len(parts) == 2:
            year = parts[0].zfill(4)
            month = parts[1].zfill(2) if parts[1] else '00'
            return f'{year}{month}00'
        elif len(parts) == 1:
            year = parts[0].zfill(4)
            return f'{year}0000'
        
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

print("请将以下代码添加到 G:\\AI\\PZ\\server.py 中：")
print("1. 在 do_POST 方法中添加: if self.path == '/api/upload': return self.handle_upload()")
print("2. 在 PhotoHandler 类中添加以下方法：")
print(HANDLE_UPLOAD_CODE)
