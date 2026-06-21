import re

path = r'G:\AI\APK\svtv_patch\smali\com\seth\svtv\MainActivity.smali'
with open(path, 'r', encoding='utf-8') as f:
    t = f.read()

# 替换 LAN 探测逻辑为直接走局域网
old = r'''var _host = \"sethshi.dynv6.net\";\nvar _lan = \"\";\nvar _lanReady = false;\n\n// LAN probe\n(function(){\n  try {\n    var x = new XMLHttpRequest();\n    x.open(\"HEAD\", \"http://192.168.0.10:8082/\", true);\n    x.timeout = 2000;\n    x.onload = function() { _lan = \"192.168.0.10\"; _lanReady = true; };\n    x.onerror = function() { _lanReady = true; };\n    x.ontimeout = function() { _lanReady = true; };\n    x.send();\n  } catch(e) { _lanReady = true; }\n})();'''

new = r'''var _lan = \"192.168.0.10\";\nvar _lanReady = true;'''

if old in t:
    t = t.replace(old, new)
    print('OK: LAN probe removed, hardcoded to 192.168.0.10')
else:
    print('ERROR: pattern not found')

with open(path, 'w', encoding='utf-8') as f:
    f.write(t)
