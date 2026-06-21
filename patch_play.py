import re

with open('server_new.py', 'r', encoding='utf-8') as f:
    content = f.read()

# 替换 play() 函数：跳转到 player.html
old = (
    '        # play\n'
    '        p.append(\'function play(url){\')\n'
    '        p.append(\'var pg=document.getElementById("play-page");var v=document.getElementById("tv-video");\')\n'
    '        p.append(\'v.src=url;v.load();v.volume=0.3;v.muted=false;'
    'pg.style.position="fixed";pg.style.top="0";pg.style.left="0";'
    'pg.style.width="100%";pg.style.height="100%";'
    'v.style.width="100%";v.style.height="100%";v.style.objectFit="contain";\')\n'
    '        p.append(\'pg.style.display="block";_inPlayer=true;\')\n'
    '        p.append(\'history.pushState({player:1},"");}\')\n'
)

new = (
    '        # play → 跳转到 player.html（带加速播放的专用页面）\n'
    '        p.append(\'function play(url){\')\n'
    '        p.append(\'window.location.href="/player.html?url="+encodeURIComponent(url);}\')\n'
)

if old in content:
    content = content.replace(old, new, 1)
    with open('server_new.py', 'w', encoding='utf-8') as f:
        f.write(content)
    print('Done! play() now redirects to player.html')
else:
    print('Pattern not found!')
    # 搜索 play 函数的位置
    idx = content.find('function play(url)')
    if idx >= 0:
        print('Found play() at:', idx)
        print('Context:', repr(content[idx:idx+300]))
    else:
        print('play() not found at all')
