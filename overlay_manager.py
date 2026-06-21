#!/usr/bin/env python3
"""
尚唯云影 - 刮削覆盖数据管理模块
- extract_overlay(): 从 *-data.js 和 *-index.js 提取覆盖数据到 scrape_overlay.json
- load_overlay(): 加载已有的 overlay 文件
- update_overlay_after_apply(): apply_scrape.py 注入后自动调用

使用方式:
  python overlay_manager.py          # 独立运行，提取并保存 overlay
  from overlay_manager import ...    # 模块化调用
"""

import os
import re
import json
import sys

if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')

# 路径设置：以脚本所在目录的父目录为 MV_DIR
_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
if os.path.basename(_SCRIPT_DIR) == '.temp':
    MV_DIR = os.path.dirname(_SCRIPT_DIR)
else:
    MV_DIR = _SCRIPT_DIR

DATA_DIR = os.path.join(MV_DIR, 'data')


def load_js_var(filepath):
    """加载 JS var 数据文件，返回 Python dict/list"""
    if not os.path.exists(filepath):
        return None
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
        content = re.sub(r'^/\*.*?\*/', '', content, flags=re.DOTALL)
        content = re.sub(r'^//.*$', '', content, flags=re.MULTILINE)
        content = re.sub(r'^var\s+\w+\s*=\s*', '', content.strip())
        content = content.rstrip().rstrip(';')
        return json.loads(content)
    except Exception as e:
        print(f'  [overlay] 加载失败 {filepath}: {e}')
        return None


def load_overlay():
    """加载已有的 scrape_overlay.json"""
    overlay_path = os.path.join(DATA_DIR, 'scrape_overlay.json')
    if not os.path.exists(overlay_path):
        return None
    try:
        with open(overlay_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        print(f'  [overlay] 加载失败: {e}')
        return None


def extract_overlay(save=True):
    """
    从当前 *-data.js 和 *-index.js 提取所有刮削覆盖数据
    返回 overlay dict；如果 save=True 则写入 scrape_overlay.json
    """
    from datetime import datetime

    overlay = {
        "version": 1,
        "generated": datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        "by_imdbid": {},
        "by_title_year": {},
        "series_covers": {}
    }

    # 数据文件列表
    data_files = [
        ('movie-data.js', 'movie-index.js'),
        ('tv-data.js', 'tv-index.js'),
        ('anime-data.js', 'anime-index.js'),
        ('doc-data.js', 'doc-index.js'),
    ]

    stats = {'items': 0, 'nfo': 0, 'poster': 0, 'fanart': 0, 'by_imdb': 0, 'by_title': 0}

    for data_file, idx_file in data_files:
        data = load_js_var(os.path.join(DATA_DIR, data_file))
        if not data:
            continue

        for series_name, series in data.items():
            items = series.get('movies', series.get('shows', []))
            for item in items:
                has_overlay = False
                entry = {}

                # 提取 nfo
                nfo = item.get('nfo')
                if nfo:
                    entry['nfo'] = nfo
                    stats['nfo'] += 1
                    has_overlay = True

                # 提取 posters/ 前缀的海报
                poster = item.get('poster', '')
                if poster and poster.startswith('posters/'):
                    entry['poster'] = poster
                    stats['poster'] += 1
                    has_overlay = True

                # 提取 fanart/ 前缀的背景
                fanart = item.get('fanart', '')
                if fanart and fanart.startswith('fanart/'):
                    entry['fanart'] = fanart
                    stats['fanart'] += 1
                    has_overlay = True

                if not has_overlay:
                    continue

                stats['items'] += 1

                # 主键：imdbid
                imdbid = ''
                if nfo and nfo.get('imdbid'):
                    imdbid = nfo['imdbid']

                if imdbid:
                    # 同一 imdbid 可能有多条记录（电影+TV），保留更完整的
                    if imdbid not in overlay['by_imdbid'] or len(json.dumps(entry)) > len(json.dumps(overlay['by_imdbid'][imdbid])):
                        overlay['by_imdbid'][imdbid] = entry
                    stats['by_imdb'] += 1

                # 副键：title|year
                title = item.get('title', '')
                year = item.get('year', 0)
                key = f"{title}|{year}"
                if title:
                    overlay['by_title_year'][key] = entry
                    stats['by_title'] += 1

        # 系列封面
        idx_data = load_js_var(os.path.join(DATA_DIR, idx_file))
        if idx_data:
            for series_name, entry in idx_data.items():
                spf = entry.get('samplePosterFile', '')
                if spf.startswith('posters/'):
                    overlay['series_covers'][series_name] = spf

    if save:
        out_path = os.path.join(DATA_DIR, 'scrape_overlay.json')
        with open(out_path, 'w', encoding='utf-8') as f:
            json.dump(overlay, f, ensure_ascii=False, indent=2)
        size = os.path.getsize(out_path)
        print(f'[overlay] 已保存: {out_path} ({size:,} bytes)')

    print(f'[overlay] 提取: {stats["items"]} 条, NFO {stats["nfo"]}, 海报 {stats["poster"]}, '
          f'背景 {stats["fanart"]}, imdbid {stats["by_imdb"]}, title|year {stats["by_title"]}, '
          f'系列封面 {len(overlay["series_covers"])}')

    return overlay


if __name__ == '__main__':
    print('=' * 40)
    print('  刮削覆盖数据管理')
    print('=' * 40)
    overlay = extract_overlay(save=True)
