#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""自动将上传导航集成到 index2.js"""

JS_PATH = r'G:\AI\PZ\engine\index2.js'

with open(JS_PATH, 'r', encoding='utf-8') as f:
    content = f.read()

# 在 nav2 函数中添加 upload 处理
old_nav = "function nav2(view) {\n  if (view === 'memory') { openMemory2(); return; }"
new_nav = "function nav2(view) {\n  if (view === 'memory') { openMemory2(); return; }\n  if (view === 'upload') { window.location.href = '/upload.html'; return; }"

if old_nav in content:
    content = content.replace(old_nav, new_nav)
    print('✓ 已添加 upload 导航')
else:
    print('⚠ nav2 中已有 upload，跳过')

with open(JS_PATH, 'w', encoding='utf-8') as f:
    f.write(content)

print('✓ index2.js 已更新')
