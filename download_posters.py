#!/usr/bin/env python3
"""
尚唯云影 - 在线海报/fanart下载脚本
从 nfo.online_poster / nfo.online_fanart 下载图片到本地
优先下载缺少本地海报的条目
"""

import os
import re
import json
import sys
import time
import urllib.request
import urllib.error
import ssl

if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')

MV_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(MV_DIR, 'data')
POSTER_DIR = os.path.join(MV_DIR, 'posters')  # 海报下载目录（备用）
FANART_DIR = os.path.join(MV_DIR, 'fanart')    # 背景图下载目录（备用）

REQUEST_DELAY = 0.3  # 图片下载间隔
MAX_RETRIES = 3

# SSL上下文
SSL_CTX = ssl.create_default_context()
SSL_CTX.check_hostname = False
SSL_CTX.verify_mode = ssl.CERT_NONE

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
    'Accept': 'image/webp,image/apng,image/*,*/*;q=0.8',
}


def load_js_var(filepath):
    if not os.path.exists(filepath):
        return None
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
    content = re.sub(r'^/\*.*?\*/', '', content, flags=re.DOTALL)
    content = re.sub(r'^var\s+\w+\s*=\s*', '', content.strip())
    content = content.rstrip().rstrip(';')
    return json.loads(content)


def save_js_data(data, var_name, filepath):
    json_str = json.dumps(data, ensure_ascii=False, indent=2)
    ts = time.strftime('%Y-%m-%d %H:%M:%S')
    header = '/**\n * 尚唯云影 - %s\n * 海报下载更新于 %s\n */\n\n' % (var_name, ts)
    content = header + 'var %s = %s;\n' % (var_name, json_str)
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(content)


def download_image(url, save_path):
    """下载图片，返回是否成功"""
    for attempt in range(MAX_RETRIES):
        try:
            req = urllib.request.Request(url, headers=HEADERS)
            with urllib.request.urlopen(req, timeout=30, context=SSL_CTX) as resp:
                data = resp.read()
                if len(data) < 500:  # 太小，可能是占位图
                    return False
                with open(save_path, 'wb') as f:
                    f.write(data)
                return True
        except Exception as e:
            if attempt < MAX_RETRIES - 1:
                time.sleep(1)
            else:
                return False
    return False


def make_safe_filename(title, suffix='jpg'):
    """从标题生成安全的文件名"""
    s = re.sub(r'[\\/:*?"<>|]', '', title)
    s = re.sub(r'\s+', '_', s.strip())
    s = s[:80]  # 限制长度
    return '%s.%s' % (s, suffix)


def download_category(data_var_name, cat_type='movie'):
    """下载一个分类的海报和fanart"""
    filepath = os.path.join(DATA_DIR, data_var_name.lower().replace('_', '-') + '.js')
    if not os.path.exists(filepath):
        print('  文件不存在: %s' % filepath)
        return

    print('=' * 60)
    print('  下载海报: %s' % data_var_name)
    print('=' * 60)

    data = load_js_var(filepath)

    # 海报保存到项目的posters/fanart目录
    cat_poster_dir = os.path.join(POSTER_DIR, cat_type)
    cat_fanart_dir = os.path.join(FANART_DIR, cat_type)
    os.makedirs(cat_poster_dir, exist_ok=True)
    os.makedirs(cat_fanart_dir, exist_ok=True)

    # 收集需要下载的条目
    tasks = []

    for series_name, series in data.items():
        items_key = 'movies' if 'movies' in series else 'shows'
        items = series.get(items_key, [])
        series_dir = series.get('dir', '')

        for item in items:
            nfo = item.get('nfo')
            if not nfo or nfo is None:
                continue

            online_poster = nfo.get('online_poster', '')
            online_fanart = nfo.get('online_fanart', '')

            need_poster = online_poster and not item.get('poster')
            need_fanart = online_fanart and not item.get('fanart')

            if need_poster or need_fanart:
                tasks.append((item, series_name, need_poster, need_fanart, online_poster, online_fanart))

    print('  需下载: %d 个条目' % len(tasks))

    if not tasks:
        print('  无需下载')
        return

    poster_ok = 0
    poster_fail = 0
    fanart_ok = 0
    fanart_fail = 0

    for idx, (item, series_name, need_poster, need_fanart, online_poster, online_fanart) in enumerate(tasks):
        title = item.get('title', series_name)
        display = title[:40]

        # 下载海报 → 保存到 posters/cat_type/filename
        if need_poster and online_poster:
            fname = make_safe_filename(title, 'jpg')
            save_path = os.path.join(cat_poster_dir, fname)

            if os.path.exists(save_path):
                # 文件已存在，直接引用
                item['poster'] = 'posters/' + cat_type + '/' + fname
                poster_ok += 1
            else:
                print('  [%d/%d] 海报: %s' % (idx + 1, len(tasks), display), end='', flush=True)
                if download_image(online_poster, save_path):
                    item['poster'] = 'posters/' + cat_type + '/' + fname
                    poster_ok += 1
                    print(' -> OK')
                else:
                    poster_fail += 1
                    print(' -> FAIL')
                time.sleep(REQUEST_DELAY)

        # 下载fanart/背景图 → 保存到 fanart/cat_type/filename
        if need_fanart and online_fanart:
            fname = make_safe_filename(title + '_fanart', 'jpg')
            save_path = os.path.join(cat_fanart_dir, fname)

            if os.path.exists(save_path):
                item['fanart'] = 'fanart/' + cat_type + '/' + fname
                fanart_ok += 1
            else:
                if not need_poster:
                    print('  [%d/%d] 背景: %s' % (idx + 1, len(tasks), display), end='', flush=True)
                else:
                    print('    背景: ', end='', flush=True)
                if download_image(online_fanart, save_path):
                    item['fanart'] = 'fanart/' + cat_type + '/' + fname
                    fanart_ok += 1
                    print(' -> OK')
                else:
                    fanart_fail += 1
                    print(' -> FAIL')
                time.sleep(REQUEST_DELAY)

        # 每100个保存一次
        if (idx + 1) % 100 == 0:
            save_js_data(data, data_var_name, filepath)
            print('  --- 中途保存 ---')

    # 最终保存
    save_js_data(data, data_var_name, filepath)
    print()
    print('  海报: 成功 %d / 失败 %d' % (poster_ok, poster_fail))
    print('  背景: 成功 %d / 失败 %d' % (fanart_ok, fanart_fail))
    print()


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--cat', type=str, default='', help='只下载指定分类(tv/anime/doc/movie)')
    args = parser.parse_args()

    print()
    print('*' * 60)
    print('  尚唯云影 在线海报/fanart下载')
    print('*' * 60)
    print()

    cats = []
    if args.cat:
        cat_map = {
            'tv': ('TV_DATA', 'tv'),
            'anime': ('ANIME_DATA', 'anime'),
            'doc': ('DOC_DATA', 'doc'),
            'movie': ('MOVIE_DATA', 'movie')
        }
        cats = [cat_map[args.cat]]
    else:
        # 优先下载缺海报最多的
        cats = [('TV_DATA', 'tv'), ('DOC_DATA', 'doc'), ('ANIME_DATA', 'anime'), ('MOVIE_DATA', 'movie')]

    for var_name, cat_type in cats:
        download_category(var_name, cat_type)

    print('全部下载完成!')
    print('请重新运行 auto_scan.py 或修改 server.py 确保海报目录可访问')


if __name__ == '__main__':
    main()
