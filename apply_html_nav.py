#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""在 index2.html 导航栏添加"上传"菜单项"""

HTML_PATH = r'G:\AI\PZ\index2.html'

with open(HTML_PATH, 'r', encoding='utf-8') as f:
    content = f.read()

# 在导航栏的"回忆"后面添加"上传"
old_nav = '''        <div class="menu-item"><a href="javascript:void(0)" onclick="nav2('memory')"><span>回忆</span></a></div>
      </div>
    </div>'''

new_nav = '''        <div class="menu-item"><a href="javascript:void(0)" onclick="nav2('memory')"><span>回忆</span></a></div>
        <div class="menu-item"><a href="javascript:void(0)" onclick="nav2('upload')"><span>上传</span></a></div>
      </div>
    </div>'''

if 'nav2(\'upload\')' in content:
    print('⚠ 导航中已有"上传"入口，跳过')
elif old_nav in content:
    content = content.replace(old_nav, new_nav)
    print('✓ 已在导航栏添加"上传"入口')
else:
    print('✗ 未找到导航栏插入位置，尝试备选方案')
    # 备选：在 main-menu-center 的最后一个 menu-item 后插入
    old2 = '''onclick="nav2('memory')"><span>回忆</span></a></div>'''
    new2 = '''onclick="nav2('memory')"><span>回忆</span></a></div>
        <div class="menu-item"><a href="javascript:void(0)" onclick="nav2('upload')"><span>上传</span></a></div>'''
    if old2 in content:
        content = content.replace(old2, new2)
        print('✓ 已通过备选方案添加"上传"入口')

with open(HTML_PATH, 'w', encoding='utf-8') as f:
    f.write(content)

print('✓ index2.html 已更新')
