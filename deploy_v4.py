"""部署云册4.0到PZ目录"""
import shutil, os

src_dir = r'G:\AI\MV'
dst_dir = r'G:\AI\PZ'

# 备份旧版
old_html = os.path.join(dst_dir, 'index.html')
backup = os.path.join(dst_dir, 'index-old-v3.html')
if os.path.exists(old_html) and not os.path.exists(backup):
    shutil.copy2(old_html, backup)
    print('Backup: index.html -> index-old-v3.html')

# 1. index.html
shutil.copy2(os.path.join(src_dir, 'index-new.html'), os.path.join(dst_dir, 'index.html'))
print('Deployed: index.html')

# 2. style-new.css
shutil.copy2(os.path.join(src_dir, 'style-new-v4.css'), os.path.join(dst_dir, 'engine', 'style-new.css'))
print('Deployed: engine/style-new.css')

# 3. tab-controller.js
shutil.copy2(os.path.join(src_dir, 'tab-controller-new.js'), os.path.join(dst_dir, 'engine', 'tab-controller.js'))
print('Deployed: engine/tab-controller.js')

print('\n=== 部署完成 ===')
