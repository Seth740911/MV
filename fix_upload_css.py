#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""修复 upload.css - 添加 body 暗色背景和全局样式"""

CSS_PATH = r'G:\AI\PZ\engine\upload.css'

with open(CSS_PATH, 'r', encoding='utf-8') as f:
    content = f.read()

# 在文件开头添加全局样式
global_css = '''/* ============================================
   尚唯云册 - 照片上传页面样式
   ============================================ */

/* 全局暗色主题 */
* {
  margin: 0;
  padding: 0;
  box-sizing: border-box;
}

body {
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
  background: #0d0d0d;
  color: #e0e0e0;
  min-height: 100vh;
  -webkit-font-smoothing: antialiased;
}

'''

old_header = '/* ============================================\n   尚唯云册 - 照片上传页面样式\n   ============================================ */\n\n.upload-container {'
new_header = global_css + '.upload-container {'

if 'body {' in content and 'background: #0d0d0d' in content:
    print('⚠ 全局样式已存在，跳过')
else:
    content = content.replace(old_header, new_header)
    print('✓ 已添加全局暗色主题样式')

with open(CSS_PATH, 'w', encoding='utf-8') as f:
    f.write(content)

print('✓ upload.css 已更新')
