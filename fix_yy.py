path = r'G:\AI\APK\svtv_patch\smali\com\seth\svtv\MainActivity.smali'
with open(path, 'r', encoding='utf-8') as f:
    t = f.read()

# 云音路径 / -> /tv
old = '8083,path:\\"/\\"'
new = '8083,path:\\"/tv\\"'
if old in t:
    t = t.replace(old, new)
    print('OK: yy path / -> /tv')
else:
    print('NOT FOUND')

with open(path, 'w', encoding='utf-8') as f:
    f.write(t)
