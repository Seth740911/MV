#!/usr/bin/env python3
"""
尚唯云影 自动扫描脚本
- 扫描4大分类：电影(I:/电影/)、电视剧(H:/电视剧/)、动画片(I:/动画片/)、纪录片(I:/纪录片/)
- 从文件名提取元数据（系列名、编号、年份、中文名、英文名、主演、集数）
- 从 .nfo 文件提取详细信息（演员、导演、评分、简介、类型）
- 识别海报(.jpg/.png/.webp)和背景图(-fanart.jpg/fanart.jpg)
- 不移动不重命名任何原始文件
"""

import os
import re
import json
import sys
import xml.etree.ElementTree as ET
from datetime import datetime

# Windows 控制台编码修复
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')

MV_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(MV_DIR, 'data')

VIDEO_EXTS = {'.mp4', '.mkv', '.avi', '.rmvb', '.ts', '.wmv', '.webm'}
IMAGE_EXTS = {'.jpg', '.jpeg', '.png', '.webp'}


def load_js_var(filepath):
    """加载已有的 JS var 数据文件，返回 Python dict/list"""
    if not os.path.exists(filepath):
        return None
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
        # 去掉注释和 var 声明
        content = re.sub(r'^/\*.*?\*/', '', content, flags=re.DOTALL)
        content = re.sub(r'^//.*$', '', content, flags=re.MULTILINE)
        content = re.sub(r'^var\s+\w+\s*=\s*', '', content.strip())
        content = content.rstrip().rstrip(';')
        return json.loads(content)
    except Exception as e:
        print(f'  [NFO缓存] 加载失败 {filepath}: {e}')
        return None


def load_overlay():
    """加载刮削覆盖数据（scrape_overlay.json），返回 dict 或 None"""
    overlay_path = os.path.join(DATA_DIR, 'scrape_overlay.json')
    if not os.path.exists(overlay_path):
        return None
    try:
        with open(overlay_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        print(f'  覆盖数据版本: v{data.get("version", "?")} 生成于 {data.get("generated", "?")}')
        return data
    except Exception as e:
        print(f'  [覆盖数据] 加载失败: {e}')
        return None


def apply_overlay(data, overlay, is_movie=False):
    """
    应用刮削覆盖数据到新扫描结果。
    优先级：overlay（手动注入的 IMDB/豆瓣/1905 刮削数据）> 本地文件

    策略：
    1. 用 imdbid 精确匹配 → 用 title|year 匹配
    2. NFO：overlay 有则覆盖（无论本地有无 .nfo 文件）
    3. Poster：posters/ 前缀总是优先于本地 .jpg 文件
    4. Fanart：fanart/ 前缀总是优先
    """
    if not overlay:
        return 0

    by_imdbid = overlay.get('by_imdbid', {})
    by_title_year = overlay.get('by_title_year', {})

    # 构建 imdbid → overlay entry 索引（已直接可用）
    merged = 0

    items_key = 'movies'  # 电影用 movies
    if 'shows' in next(iter(data.values()), {}):
        items_key = 'shows'

    for series_name, series in data.items():
        items = series.get('movies', series.get('shows', []))

        for ni in items:
            overlay_entry = None

            # 1. 先用 imdbid 匹配（从已有的 nfo 中取 imdbid，或从本地 .nfo 解析的）
            existing_nfo = ni.get('nfo')
            if existing_nfo and existing_nfo.get('imdbid'):
                imdbid = existing_nfo['imdbid']
                overlay_entry = by_imdbid.get(imdbid)

            # 2. 再用 title|year 匹配
            if not overlay_entry:
                title = ni.get('title', '')
                year = ni.get('year', 0)
                key = f"{title}|{year}"
                overlay_entry = by_title_year.get(key)

            if not overlay_entry:
                continue

            # 应用 NFO 覆盖（overlay 的 NFO 总是优先——它是我们精心刮削的）
            if overlay_entry.get('nfo'):
                ni['nfo'] = overlay_entry['nfo']
                merged += 1
                # 也恢复增强的年份
                if not ni.get('year') and overlay_entry['nfo'].get('year'):
                    ni['year'] = overlay_entry['nfo']['year']

            # 应用海报覆盖（posters/ 前缀总是优先于本地 .jpg）
            ov_poster = overlay_entry.get('poster', '')
            if ov_poster and ov_poster.startswith('posters/'):
                ni['poster'] = ov_poster
            # 如果 overlay 没有 posters/ 但当前也没有海报，保留 overlay 的非 posters/ 海报
            elif ov_poster and not ni.get('poster'):
                ni['poster'] = ov_poster

            # 应用背景覆盖（fanart/ 前缀总是优先）
            ov_fanart = overlay_entry.get('fanart', '')
            if ov_fanart and ov_fanart.startswith('fanart/'):
                ni['fanart'] = ov_fanart
            elif ov_fanart and not ni.get('fanart'):
                ni['fanart'] = ov_fanart

    return merged


def merge_nfo_cache(new_data, old_data):
    """
    将旧数据中由元数据增强(metadata_enhance.py)补全的NFO信息合并到新扫描数据中。
    策略：仅在新数据中 item.nfo 为 None 时，才从旧数据复制 nfo。
    同时合并旧数据中的 online_poster / online_fanart 字段。
    同时保留旧数据中下载的海报/背景图（posters/xxx 或 fanart/xxx 格式）。

    注意：此函数已被 apply_overlay() 替代主要功能，保留用于向后兼容。
    """
    if not old_data:
        return 0
    merged = 0
    items_key = 'movies'  # 电影用 movies
    if 'shows' in next(iter(old_data.values()), {}):
        items_key = 'shows'

    for series_name, series in new_data.items():
        old_series = old_data.get(series_name)
        if not old_series:
            continue
        old_items = old_series.get('movies', old_series.get('shows', []))
        new_items = series.get('movies', series.get('shows', []))

        # 建立 title → old item 的映射
        old_by_title = {}
        for oi in old_items:
            t = oi.get('title', '')
            if t:
                old_by_title[t] = oi

        for ni in new_items:
            old_item = old_by_title.get(ni.get('title', ''))

            # 合并NFO
            if (not ni.get('nfo') or ni.get('nfo') is None) and old_item and old_item.get('nfo'):
                ni['nfo'] = old_item['nfo']
                merged += 1
                # 也合并增强的年份
                if not ni.get('year') and old_item.get('year'):
                    ni['year'] = old_item['year']

            # 保留下载的海报（posters/xxx 或 fanart/xxx 格式）
            if old_item:
                old_poster = old_item.get('poster', '')
                if old_poster.startswith('posters/') and not ni.get('poster'):
                    ni['poster'] = old_poster
                old_fanart = old_item.get('fanart', '')
                if old_fanart.startswith('fanart/') and not ni.get('fanart'):
                    ni['fanart'] = old_fanart

    return merged

# ========= 系列名清洗 =========
def clean_series_name(name):
    """从脏目录名中提取可读的系列名称，用于 displayName 和 series key"""
    s = name

    # Phase 1: 去掉明确的前缀垃圾

    # 去掉带网站域名的方括号/书名号前缀（必须先于一般方括号清理）
    # 【更多高清电影访问 www.BBSDDS.com】 / 【高清剧集网 www.BTHDTV.com】
    s = re.sub(r'[【\[]\s*(?:www\.)?[^】\]]*?(?:\.com|\.cn|\.tv|\.me|\.mx|\.org|\.net)[^】\]]*?[】\]]\s*', '', s, flags=re.IGNORECASE)
    s = re.sub(r'\[\s*[^]]*?(?:高清电影之家|mkvhome|gaoqing\.tv)[^]]*?\]\s*', '', s, flags=re.IGNORECASE)

    # 去掉分类方括号标记（保留内容）：[09澳大利亚动画片] / [07英国纪录片] / [中国剧情] / [TV] / [道兰]
    # 注意：只删除方括号本身和分类关键词，保留方括号内的其他内容
    for _ in range(5):
        new_s = re.sub(r'[\u3010\[][\d]*(?:动画片|纪录片|电视剧|电影|剧情|纪录|TV|道兰)\s*', '', s)
        new_s = re.sub(r'[\]\u3011]\s*', '', new_s)
        if new_s == s:
            break
        s = new_s

    # 去掉质量/发布标签方括号（空标签，不保留内容）：
    # [720P] [HR-HDTV] [x264] [双语字幕] [DVDRip] [Hi10p] [MKV] [全44集] [国日粤三语] [简繁字幕] [YTS.MX] [YYeTs人人影视] [BD-RMVB] [中文字幕] [国语无字] [DVD-R573MB]
    for _ in range(5):
        new_s = re.sub(r'[\u3010\[][\d]*(?:全\d+集|\d+集全|\d+集|720[Pp]|1080[Pp]|2160[Pp]|4K|UHD|HDTV|WEB[\s-]*DL|BluRay|BDRip|DVDRip|dvdrip|Hi10p|x264|x265|H264|H265|AAC|DTS|RMVB|MKV|MP4|AVI|HR[\s-]*HDTV|SDR|HDR|BD[\s-]*RMVB|YTS|YYeTs|\u4eba\u4eba\u5f71\u89c6|\u53cc\u8bed\u5b57\u5e55|\u4e2d\u6587\u5b57\u5e55|\u7b80\u7e41\u5b57\u5e55|\u56fd\u8bed\u65e0\u5b57|\u56fd\u8bed\u914d\u97f3|\u56fd\u65e5\u7ca4\u4e09\u8bed|DVD[\s-]*R?\d*MB|3\u5929\u79cd)[^\]\u3011]*?[\u3011\]]\s*', '', s, flags=re.IGNORECASE)
        if new_s == s:
            break
        s = new_s

    # 去掉书名号前缀《》(保留内容)
    s = re.sub(r'[《<]', '', s)
    s = re.sub(r'[》>]', '', s)

    # Phase 2: 尝试提取核心名称

    # 如果有【中文】书名号，提取内容（可能已被上面去掉了前缀）
    m = re.search(r'【([^】]+)】', s)
    if m:
        s = m.group(1)

    # 去掉所有剩余方括号（保留内容），如 [BBC.印度的故事] → BBC.印度的故事
    for _ in range(5):
        new_s = re.sub(r'[\u3010\[]', '', s)
        new_s = re.sub(r'[\u3011\]]', '', new_s)
        if new_s == s:
            break
        s = new_s

    # Phase 3: 清理尾缀

    # 去掉方括号但保留内容（二次清理，确保之前没清干净的都处理）
    for _ in range(3):
        new_s = s.replace('[', '').replace(']', '')
        new_s = new_s.replace('\u3010', '').replace('\u3011', '')
        if new_s == s:
            break
        s = new_s

    # 去掉 "纪录片 " 前缀（方括号清理后可能暴露）
    s = re.sub(r'^纪录片\s+', '', s)
    s = re.sub(r'^纪录片_', '', s)

    # 去掉点号分隔的英文+质量串：名.Chuan.Qi.2015.1080p.WEB-DL → 名
    m2 = re.match(r'^([\u4e00-\u9fff\u3000-\u303f\uff00-\uffef\w\s]+?)(?:\.[A-Za-z].*)?$', s)
    if m2 and len(m2.group(1).strip()) >= 2:
        s = m2.group(1).strip()

    # 去掉发布组尾缀 -NGB -TAG -Xiaomi 等
    s = re.sub(r'\s*[-–—]\s*[A-Z][A-Za-z0-9()（）]*$', '', s)

    # 去掉 S01 季号
    s = re.sub(r'\.\s*S\d+.*$', '', s, flags=re.IGNORECASE)

    # 前导序号 "1. " "2. " "07.03" "06.28" "07.05" "09" "A025"
    s = re.sub(r'^\d{2}\.\d{2}\s*', '', s)          # "07.03古格..." → "古格..."
    s = re.sub(r'^\d{2}\.\d{2}\s*', '', s)          # 确保二次匹配也处理
    s = re.sub(r'^A\d{3}\s*', '', s)                # "A025手冢治虫..." → "手冢治虫..."
    s = re.sub(r'^\d+\.\s*', '', s)                  # "1. 奥斯卡..." → "奥斯卡..."

    # 去掉特殊前缀 "! HD纪录片：" 
    s = re.sub(r'^!\s*HD纪录片[：:]\s*', '', s)

    # 去掉CCTV/频道前缀 "CCTV高清－" "CCTV6." "CCTV."
    s = re.sub(r'^CCTV\d*[.．\-－]+', '', s)

    # 去掉"补全完整版"等前缀
    s = re.sub(r'^补全完整版', '', s)

    # 去掉文档描述性尾缀：大小(348MB/3.97G)、语言、字幕组、来源、天数等
    s = re.sub(r'\s*\d+[\.\d]*\s*(MB|GB|G|TB|T)\b.*$', '', s, flags=re.IGNORECASE)  # "348MB英语中字3天种" → ""
    s = re.sub(r'\s*[\(（].*?[\)）]\s*$', '', s)    # 末尾括号内容

    # 去掉@用户名 "育净园@阳光宝贝"
    s = re.sub(r'@\S+', '', s)

    # 去掉"宽屏亮丽版"/"慈悲得道篇"/"国语"等特定描述词
    s = re.sub(r'(宽屏亮丽版|慈悲得道篇|最新高清晰|破.*?纪录.*?元|简繁英字幕|中日双语字幕|英语中字)', '', s)

    # 去掉年份+类型描述 "1995-电视剧" "1984年日本动画剧情" "2006年美国纪录片" "2010年中国剧情"
    s = re.sub(r'\d{4}年?.*?(电影|电视剧|动画|纪录片|剧情).*$', '', s)

    # 去掉下划线+描述 "世界历史_CCTV纪录片100集"
    s = re.sub(r'[_\s]+CCTV.*$', '', s)
    s = re.sub(r'[_\s]+纪录片.*$', '', s, count=1)

    # 去掉点号+字幕组/来源
    s = re.sub(r'\.\d{4}.*$', '', s)                 # ".2013" → ""

    # 去掉"dvdrip" "DVDRip"等
    s = re.sub(r'\.DVDRip$', '', s, flags=re.IGNORECASE)

    # 末尾括号内容（年份、集数等）
    s = re.sub(r'\s*[\(（][^)）]*[\)）]\s*$', '', s)

    # 特殊替换
    s = re.sub(r'^LS$', '连载动画', s)
    s = re.sub(r'^20240531$', '哆啦A梦', s)
    # 英文特殊映射
    s = re.sub(r'^Teenage Mutant Ninja Turtles$', '忍者神龟', s)
    s = re.sub(r'^The Smurfs Complete Seasons 1-9 dvdrip$', '蓝精灵', s)
    s = re.sub(r'^Triumph\s+(Of|of)\s+the\s+Will\.?\d*\.?$', '意志的胜利', s)

    # 长描述名简化
    s = re.sub(r'^海洋\s+空前绝后.*$', '海洋', s)
    s = re.sub(r'^圆明园.*$', '圆明园', s)
    s = re.sub(r'^纪录片\s+光阴.*$', '光阴', s)
    s = re.sub(r'^诸神字幕组\s*', '', s)
    s = re.sub(r'^国家地理[.．：:]', '国家地理:', s)
    s = re.sub(r'[：:]\s*旅行到宇宙边缘.*$', '：旅行到宇宙边缘', s)
    # 去掉点号分隔的英文质量串（二次确保）
    s = re.sub(r'\.\s*[A-Z][A-Za-z]+\.\d{4}.*$', '', s)       # .National.Geographic.2017...
    s = re.sub(r'\.\s*\d{3,}[pP].*$', '', s)                    # .720p...
    s = re.sub(r'-\s*Taipei\.Palace.*$', '', s, flags=re.IGNORECASE)
    s = re.sub(r'\.National\.Geographic.*$', '', s, flags=re.IGNORECASE)
    s = re.sub(r'\.India\.From\.Above.*$', '', s, flags=re.IGNORECASE)
    s = re.sub(r'\s+Guang\.Yin.*$', '', s)
    s = re.sub(r'-\d{8}$', '', s)                    # "20180225" 尾缀日期
    s = re.sub(r'\s*Мао Цзэдун\s*_\s*', '', s)      # 俄语前缀
    # 去掉纯中文后辍的序号 "-169"
    s = re.sub(r'-\d+$', '', s)
    # 去掉冒号后的长描述
    s = re.sub(r'[：:][^：:]*[\d]{4}.*$', '', s)
    # 去掉纪年尾缀 "逝世21周年"
    s = re.sub(r'纪念.*$', '', s)

    # 清理残留
    s = re.sub(r'\s*[.．,，、\-–—:：]\s*$', '', s)
    s = re.sub(r'\s{2,}', ' ', s).strip()

    return s if s else name


# 4大分类配置
CATEGORIES = {
    'movie': {
        'name': '电影',
        'bases': ['I:/电影/'],
        'type': 'movie',  # movie=flat video files, tv=show dirs with episodes
    },
    'tv': {
        'name': '电视剧',
        'bases': ['H:/电视剧/'],
        'type': 'tv',
    },
    'anime': {
        'name': '动画片',
        'bases': ['I:/动画片/'],
        'type': 'mixed',  # 既有单文件动画电影，也有多集系列
    },
    'doc': {
        'name': '纪录片',
        'bases': ['I:/纪录片/'],
        'type': 'mixed',  # 既有单文件，也有多集系列
    }
}


# ========== 文件名解析 ==========

def parse_movie_filename(filename):
    """
    解析电影文件名，提取元数据
    格式：系列.编号.年份-片名(英文名)语轨-主演.扩展名
    """
    name, ext = os.path.splitext(filename)
    if ext.lower() not in VIDEO_EXTS:
        return None

    info = {
        'file': filename,
        'ext': ext.lower(),
        'series': '',
        'index': 0,
        'year': 0,
        'title': '',
        'titleEn': '',
        'actor': '',
        'audio': ''
    }

    # 提取系列名和编号
    m = re.match(r'^(.+?)[\.\-](\d+)(?:[\.\-]|[：:])', name)
    if m:
        info['series'] = m.group(1)
        info['index'] = int(m.group(2))
        rest = name[m.end():]
    else:
        rest = name

    # 提取年份
    m_year = re.match(r'^(\d{4})[\.\-]', rest)
    if m_year:
        info['year'] = int(m_year.group(1))
        rest = rest[m_year.end():]

    # 提取片名（括号或破折号之前）
    m_paren = re.match(r'^([^(（]+?)\(([^)）]+)\)', rest)
    if m_paren:
        info['title'] = m_paren.group(1).rstrip('.')
        info['titleEn'] = m_paren.group(2)
        after_paren = rest[m_paren.end():]
    else:
        m_paren2 = re.match(r'^([^（]+?)（([^）]+)）', rest)
        if m_paren2:
            info['title'] = m_paren2.group(1).rstrip('.')
            info['titleEn'] = m_paren2.group(2)
            after_paren = rest[m_paren2.end():]
        else:
            m_dash = re.match(r'^([^\-]+)', rest)
            if m_dash:
                info['title'] = m_dash.group(1).rstrip('.')
            after_paren = rest

    # 提取主演
    m_actor = re.search(r'\-([^\-]+)$', rest)
    if m_actor:
        actor = m_actor.group(1).strip()
        if actor and not re.match(r'^\d+$', actor) and '国英' not in actor and '简英' not in actor:
            info['actor'] = actor

    # 提取语轨
    m_audio = re.search(r'(国英&简英|国英|英&简英|国&简英|国语|国粤英|国粤日|国粤|中英|双语)', rest)
    if m_audio:
        info['audio'] = m_audio.group(1)

    info['title'] = info['title'].rstrip('.').strip().replace('：', ':')
    return info


def parse_tv_dirname(dirname):
    """
    解析电视剧/动画片/纪录片目录名
    格式：剧名-集数.年份.主演(英文名)
    如：天龙八部-45.1997.黄日华(EightfoldPath.of.the.Heavenly.Dragon)
    """
    info = {
        'title': '',
        'titleEn': '',
        'year': 0,
        'episodeCount': 0,
        'actor': '',
        'dir': dirname
    }

    m_ep = re.match(r'^(.+?)[\.\-](\d+)', dirname)
    if m_ep:
        info['title'] = m_ep.group(1)
        info['episodeCount'] = int(m_ep.group(2))
        rest = dirname[m_ep.end():]
        if rest.startswith('.'):
            rest = rest[1:]
    else:
        info['title'] = dirname
        rest = ''

    # 提取年份
    m_year = re.match(r'^(\d{4})', rest)
    if m_year:
        info['year'] = int(m_year.group(1))
        rest = rest[m_year.end():]
        if rest.startswith('.'):
            rest = rest[1:]

    # 提取主演
    m_actor = re.match(r'^([^.()（)]+)', rest)
    if m_actor:
        actor = m_actor.group(1)
        if actor and not actor.isdigit():
            info['actor'] = actor

    # 提取英文名
    m_en = re.search(r'\(([^)]+)\)', dirname) or re.search(r'（([^）]+)）', dirname)
    if m_en:
        info['titleEn'] = m_en.group(1)

    return info


def parse_tv_episode(filename, ext):
    """解析单集文件名"""
    name = os.path.splitext(filename)[0]
    info = {'file': filename, 'ext': ext.lower(), 'episode': 0, 'year': 0, 'name': name}

    # 多种集号匹配模式
    # 模式1: 第12集 / 第1集
    m = re.search(r'第(\d{1,4})集', name)
    if m:
        info['episode'] = int(m.group(1))
        return info
    # 模式2: 第一季01 / S01E01
    m = re.search(r'(?:第[一二三四五六七八九十]+季|S\d{1,2})E?(\d{1,4})', name, re.IGNORECASE)
    if m:
        info['episode'] = int(m.group(1))
        return info
    # 模式3: .01- 或 .01.  (点分隔)
    m = re.search(r'[\.\-](\d{1,4})(?:[\.\-]|$)', name)
    if m:
        info['episode'] = int(m.group(1))
    # 模式4: 纯数字开头
    if info['episode'] == 0:
        m = re.match(r'(\d{1,4})', name)
        if m and int(m.group(1)) <= 9999:
            info['episode'] = int(m.group(1))

    # 提取年份
    m_year = re.search(r'[\.\-](\d{4})[\.\-]', name)
    if m_year:
        info['year'] = int(m_year.group(1))

    return info


# ========== NFO解析 ==========

def parse_nfo(nfo_path):
    """解析 NFO 元数据文件，支持 episodedetails 和 movie 根元素"""
    try:
        with open(nfo_path, 'r', encoding='utf-8', errors='replace') as f:
            content = f.read()
        root = ET.fromstring(content)
        result = {}

        # 基本信息
        for field in ['title', 'name', 'year', 'country', 'rating', 'vote_count',
                      'tmdbid', 'imdbid', 'plot', 'outline', 'premiered', 'studio',
                      'mpaa', 'runtime', 'status', 'tvdbid']:
            el = root.find(field)
            if el is not None and el.text:
                result[field] = el.text.strip()

        # 简介（优先 plot，其次 biography/outline）
        for tag in ['plot', 'biography', 'outline']:
            el = root.find(tag)
            if el is not None and el.text:
                result.setdefault('biography', el.text.strip())

        # 类型
        genres = [g.text.strip() for g in root.findall('genre') if g.text]
        if genres:
            result['genres'] = genres

        # 标签
        tags = [t.text.strip() for t in root.findall('tag') if t.text]
        if tags:
            result['tags'] = tags

        # 演员
        actors = []
        for actor in root.findall('actor'):
            name_el = actor.find('name')
            if name_el is not None and name_el.text:
                actor_info = {'name': name_el.text.strip()}
                role_el = actor.find('role')
                if role_el is not None and role_el.text:
                    actor_info['role'] = role_el.text.strip()
                thumb_el = actor.find('thumb')
                if thumb_el is not None and thumb_el.text:
                    actor_info['thumb'] = thumb_el.text.strip()
                actors.append(actor_info)
        if actors:
            result['actors'] = actors

        # 导演
        directors = []
        for d in root.findall('director'):
            if d.text:
                directors.append({'name': d.text.strip()})
        if directors:
            result['directors'] = directors

        # 海报URL
        thumb = root.find('thumb')
        if thumb is not None and thumb.text:
            result['poster_url'] = thumb.text.strip()

        # 季信息（TV show NFO）
        seasons = []
        for season_el in root.findall('.//season'):
            snum = season_el.get('number')
            sname = season_el.find('name')
            if snum:
                si = {'number': int(snum)}
                if sname is not None and sname.text:
                    si['name'] = sname.text.strip()
                seasons.append(si)
        if seasons:
            result['seasons'] = seasons

        return result
    except Exception as e:
        return {'error': str(e)}


# ========== 扫描：电影系列 ==========

def scan_movie_series(series_dir, series_name):
    """扫描一个电影/动画片电影目录，返回视频列表
    支持：视频平铺在根目录 + 视频在子文件夹中（一级递归）
    - 子文件夹只含一个视频 → 视频归属该系列，subdir记录路径
    - 子文件夹含多个视频 → 作为独立子系列返回（由调用方处理）
    返回: (movies, series_poster, series_nfo, sub_series_list)
      sub_series_list: [{'dir':..., 'path':..., 'name':..., 'movies':...}, ...]
    """
    movies = []
    sub_series_list = []
    if not os.path.isdir(series_dir):
        return movies, '', None, sub_series_list

    # 先扫描所有子文件夹，区分单视频和多视频
    single_video_subdirs = []  # [(subdir_name, filename), ...]
    multi_video_subdirs = []   # [{'dir':..., 'path':..., 'name':..., 'movies':...}, ...]

    for f in os.listdir(series_dir):
        full = os.path.join(series_dir, f)
        if not os.path.isdir(full):
            continue
        # 统计子文件夹中的视频
        subdir_videos = []
        for sf in os.listdir(full):
            sfull = os.path.join(full, sf)
            if os.path.isfile(sfull) and os.path.splitext(sf)[1].lower() in VIDEO_EXTS:
                subdir_videos.append(sf)

        if len(subdir_videos) > 1:
            # 多视频子文件夹 → 独立子系列
            sub_name = f
            # 尝试从子文件夹名提取系列名（去掉编号后缀）
            m = re.match(r'^(.+?)[\.\-]\d+', f)
            if m:
                sub_name = m.group(1)

            sub_movies = []
            for vf in subdir_videos:
                movie = parse_movie_filename(vf)
                if not movie:
                    movie = {
                        'file': vf,
                        'ext': os.path.splitext(vf)[1].lower(),
                        'series': sub_name,
                        'index': 0,
                        'year': 0,
                        'title': os.path.splitext(vf)[0][:50],
                        'titleEn': '',
                        'actor': '',
                        'audio': ''
                    }
                movie['series'] = sub_name
                full_path = os.path.join(full, vf)
                try:
                    movie['size'] = os.path.getsize(full_path)
                except:
                    movie['size'] = 0
                sub_movies.append(movie)

            sub_movies.sort(key=lambda x: (x.get('index', 0), x.get('year', 0)))

            # 查找子文件夹的海报
            sub_poster = ''
            for sf in os.listdir(full):
                if os.path.isfile(os.path.join(full, sf)) and os.path.splitext(sf)[1].lower() in IMAGE_EXTS:
                    if 'fanart' not in sf.lower():
                        sub_poster = sf
                        break

            multi_video_subdirs.append({
                'dir': f,
                'path': full,
                'name': sub_name,
                'movies': sub_movies,
                'poster': sub_poster,
            })
        elif len(subdir_videos) == 1:
            # 单视频子文件夹 → 归入父系列
            single_video_subdirs.append((f, subdir_videos[0]))
        # 0个视频的子文件夹 → 忽略

    # 根目录的视频文件
    root_videos = []
    for f in os.listdir(series_dir):
        full = os.path.join(series_dir, f)
        if os.path.isfile(full) and os.path.splitext(f)[1].lower() in VIDEO_EXTS:
            root_videos.append(f)

    # 合并根目录视频 + 单视频子文件夹视频
    all_video_entries = []
    for vf in root_videos:
        all_video_entries.append(('', vf))
    for subdir_name, vf in single_video_subdirs:
        all_video_entries.append((subdir_name, vf))

    # 按文件名（不含子文件夹）分组，匹配海报和NFO
    video_files = {}
    for subdir, vf in all_video_entries:
        name, ext = os.path.splitext(vf)
        video_files.setdefault(name, {'video': None, 'poster': None, 'fanart': None, 'nfo': None, 'subdir': subdir})
        video_files[name]['video'] = vf
        video_files[name]['subdir'] = subdir

    # 匹配海报和NFO（根目录 + 单视频子文件夹）
    poster_map = {}
    fanart_map = {}
    nfo_map = {}

    # 扫描根目录的图片和NFO
    for f in os.listdir(series_dir):
        full = os.path.join(series_dir, f)
        if not os.path.isfile(full):
            continue
        name, ext = os.path.splitext(f)
        ext_lower = ext.lower()
        if ext_lower not in IMAGE_EXTS and ext_lower != '.nfo':
            continue
        if name.endswith('-fanart'):
            base = name[:-7]
            if base in video_files:
                video_files[base]['fanart'] = f
            fanart_map[name[:-7]] = f
        elif ext_lower == '.nfo':
            base = name
            if base in video_files:
                video_files[base]['nfo'] = f
            nfo_map[name] = f
        elif ext_lower in IMAGE_EXTS:
            base = name
            if base in video_files:
                video_files[base]['poster'] = f
            poster_map[name] = f

    # 扫描单视频子文件夹的图片和NFO
    for subdir_name, _ in single_video_subdirs:
        subdir_path = os.path.join(series_dir, subdir_name)
        for sf in os.listdir(subdir_path):
            sfull = os.path.join(subdir_path, sf)
            if not os.path.isfile(sfull):
                continue
            sname, sext = os.path.splitext(sf)
            sext_lower = sext.lower()
            if sext_lower not in IMAGE_EXTS and sext_lower != '.nfo':
                continue
            if sname.endswith('-fanart'):
                base = sname[:-7]
                if base in video_files:
                    video_files[base]['fanart'] = subdir_name + '/' + sf
                fanart_map[sname[:-7]] = subdir_name + '/' + sf
            elif sext_lower == '.nfo':
                base = sname
                if base in video_files:
                    video_files[base]['nfo'] = subdir_name + '/' + sf
                nfo_map[sname] = subdir_name + '/' + sf
            elif sext_lower in IMAGE_EXTS:
                base = sname
                if base in video_files:
                    video_files[base]['poster'] = subdir_name + '/' + sf
                poster_map[sname] = subdir_name + '/' + sf

    # 按编号索引的模糊匹配
    _idx_re = re.compile(r'(?:^|[.\-])(\d{1,3})(?:[.\-：:]|$)')
    poster_by_index = {}
    fanart_by_index = {}
    nfo_by_index = {}

    for pname, pfile in poster_map.items():
        m = _idx_re.search(pname)
        if m:
            idx = int(m.group(1))
            if idx not in poster_by_index:
                poster_by_index[idx] = pfile

    for pname, ffile in fanart_map.items():
        m = _idx_re.search(pname)
        if m:
            idx = int(m.group(1))
            if idx not in fanart_by_index:
                fanart_by_index[idx] = ffile

    for nname, nfile in nfo_map.items():
        m = _idx_re.search(nname)
        if m:
            idx = int(m.group(1))
            if idx not in nfo_by_index:
                nfo_by_index[idx] = nfile

    # TV show NFO (tvshow.nfo)
    tvshow_nfo_path = os.path.join(series_dir, 'tvshow.nfo')
    series_nfo = None
    if os.path.exists(tvshow_nfo_path):
        series_nfo = parse_nfo(tvshow_nfo_path)

    # cover*.jpg 作为系列封面（根目录 + 单视频子文件夹）
    cover_images = []
    for f in os.listdir(series_dir):
        if os.path.isfile(os.path.join(series_dir, f)) and re.match(r'^cover\d*\.(jpg|jpeg|png|webp)$', f, re.IGNORECASE):
            cover_images.append(f)
    for subdir_name, _ in single_video_subdirs:
        subdir_path = os.path.join(series_dir, subdir_name)
        if os.path.isdir(subdir_path):
            for sf in os.listdir(subdir_path):
                if re.match(r'^cover\d*\.(jpg|jpeg|png|webp)$', sf, re.IGNORECASE):
                    cover_images.append(sf)
    # 任何 .jpg/.png 不含 -fanart 的，首个作为 sample poster
    series_poster = ''
    if cover_images:
        series_poster = cover_images[0]
    elif poster_map:
        # 取第一个非fanart图片
        for pname, pfile in poster_map.items():
            series_poster = pfile
            break

    for base, info in video_files.items():
        vf = info['video']
        if not vf:
            continue

        subdir = info.get('subdir', '')

        movie = parse_movie_filename(vf)
        if subdir and movie:
            # 单视频子文件夹：子文件夹名比文件名解析更可靠，用子文件夹名作为标题
            # 从子文件夹名提取年份和标题
            m_year = re.match(r'^(.+?)[\.\-](\d{4})', subdir)
            if m_year:
                movie['title'] = m_year.group(1).rstrip('.')
                movie['year'] = int(m_year.group(2))
            else:
                movie['title'] = subdir.rstrip('.')
            # 清理标题中的网站/质量标签
            movie['title'] = re.sub(r'\[.*?\]', '', movie['title']).rstrip('.')
            movie['index'] = 0
        elif not movie:
            # 根目录非标准命名文件
            title = os.path.splitext(vf)[0][:50]
            if subdir:
                title = subdir
            movie = {
                'file': vf,
                'ext': os.path.splitext(vf)[1].lower(),
                'series': series_name,
                'index': 0,
                'year': 0,
                'title': title,
                'titleEn': '',
                'actor': '',
                'audio': ''
            }

        movie['series'] = series_name
        # 如果在子文件夹中，记录子目录
        if subdir:
            movie['subdir'] = subdir

        # 补充海报
        if info['poster']:
            movie['poster'] = info['poster']
        elif base in poster_map:
            movie['poster'] = poster_map[base]
        elif movie.get('index') and movie['index'] in poster_by_index:
            movie['poster'] = poster_by_index[movie['index']]

        # 补充背景图
        if info['fanart']:
            movie['fanart'] = info['fanart']
        elif base in fanart_map:
            movie['fanart'] = fanart_map[base]
        elif movie.get('index') and movie['index'] in fanart_by_index:
            movie['fanart'] = fanart_by_index[movie['index']]

        # 补充NFO数据
        nfo_file = info['nfo'] or nfo_map.get(base)
        if not nfo_file and movie.get('index') and movie['index'] in nfo_by_index:
            nfo_file = nfo_by_index[movie['index']]
        if nfo_file:
            if '/' in nfo_file:
                nfo_path = os.path.join(series_dir, nfo_file.replace('/', os.sep))
            else:
                nfo_path = os.path.join(series_dir, nfo_file)
            nfo_data = parse_nfo(nfo_path)
            if nfo_data and 'error' not in nfo_data:
                movie['nfo'] = nfo_data

        # 文件大小
        if subdir:
            full_path = os.path.join(series_dir, subdir, vf)
        else:
            full_path = os.path.join(series_dir, vf)
        try:
            movie['size'] = os.path.getsize(full_path)
        except:
            movie['size'] = 0

        movies.append(movie)

    movies.sort(key=lambda x: (x.get('index', 0), x.get('year', 0)))
    sub_series_list = multi_video_subdirs
    return movies, series_poster, series_nfo, sub_series_list


# ========== 扫描：剧集系列（电视剧/动画片/纪录片） ==========

def scan_show_dir(show_dir, show_name_hint=''):
    """
    扫描一个剧集目录，返回剧集信息
    支持多种目录结构：
    1. 平铺：show/ep01.mkv, ep02.mkv, ... (常见于国外剧)
    2. 季子目录：show/Season 1/ep01.mkv, Season 2/...
    3. 混合：有子目录也有直接文件
    """
    show = parse_tv_dirname(os.path.basename(show_dir))
    if show_name_hint:
        show['title'] = show_name_hint

    show['path'] = show_dir.replace('/', '\\') if os.name == 'nt' else show_dir

    episodes = []
    nfo_data = None
    poster = ''
    fanart = ''

    # 查找 tvshow.nfo
    tvshow_nfo = os.path.join(show_dir, 'tvshow.nfo')
    if os.path.exists(tvshow_nfo):
        nfo_result = parse_nfo(tvshow_nfo)
        if nfo_result and 'error' not in nfo_result:
            nfo_data = nfo_result

    # 遍历所有文件（含子目录）
    all_files = []  # (relative_path, filename)
    for root, dirs, files in os.walk(show_dir):
        rel = os.path.relpath(root, show_dir)
        for f in files:
            all_files.append((rel, f))

    # 提取剧集文件和资源文件
    for rel, f in all_files:
        name, ext = os.path.splitext(f)
        ext_lower = ext.lower()

        if ext_lower in VIDEO_EXTS:
            ep_info = parse_tv_episode(f, ext)
            if rel != '.':
                ep_info['subdir'] = rel
            episodes.append(ep_info)
        elif ext_lower in IMAGE_EXTS:
            full_path = os.path.join(show_dir, rel, f)
            if name.endswith('-fanart') or 'fanart' in name.lower():
                if not fanart:
                    fanart = os.path.join(rel, f) if rel != '.' else f
            elif name == 'poster' or name == 'folder' or name == 'cover':
                if not poster:
                    poster = os.path.join(rel, f) if rel != '.' else f
            elif not poster:
                # 第一个图片作为海报候选
                poster = os.path.join(rel, f) if rel != '.' else f

        elif ext_lower == '.nfo' and name != 'tvshow':
            # 单集NFO
            nfo_path = os.path.join(show_dir, rel, f)
            ep_nfo = parse_nfo(nfo_path)
            if ep_nfo and 'error' not in ep_nfo:
                # 尝试匹配到对应剧集
                for ep in episodes:
                    base_match = os.path.splitext(ep['file'])[0] == name
                    if base_match:
                        ep['nfo'] = ep_nfo
                        break

    episodes.sort(key=lambda x: x.get('episode', 0))
    show['episodeCount'] = len(episodes)
    show['episodes'] = episodes
    if poster:
        show['poster'] = poster
    if fanart:
        show['fanart'] = fanart
    if nfo_data:
        show['nfo'] = nfo_data
        # 从NFO补充字段
        if nfo_data.get('rating'):
            show['rating'] = nfo_data['rating']
        if nfo_data.get('genres'):
            show['genres'] = nfo_data['genres']
        if nfo_data.get('plot') or nfo_data.get('biography'):
            show['plot'] = nfo_data.get('plot') or nfo_data.get('biography')
        if nfo_data.get('actors'):
            show['actors'] = nfo_data['actors']
    if episodes:
        # 从文件名推断年份
        if not show.get('year'):
            for ep in episodes:
                if ep.get('year'):
                    show['year'] = ep['year']
                    break

    # 总大小
    total_size = 0
    for ep in episodes:
        try:
            total_size += os.path.getsize(os.path.join(show_dir, ep.get('subdir', ''), ep['file']))
        except:
            pass
    show['size'] = total_size

    return show


def scan_series_group(series_dir, series_name, group_type='tv'):
    """
    扫描一个系列目录（如 古龙-系列/），里面每个子目录是一部剧
    也处理平铺式（如封神榜目录直接放视频文件）
    """
    shows = []
    if not os.path.isdir(series_dir):
        return shows

    series_poster = ''
    series_nfo = None

    # 查找系列级文件
    files_in_root = os.listdir(series_dir)
    for f in files_in_root:
        if os.path.isfile(os.path.join(series_dir, f)):
            name, ext = os.path.splitext(f)
            ext_lower = ext.lower()
            if ext_lower in IMAGE_EXTS and not series_poster:
                if 'fanart' not in name.lower():
                    series_poster = f
            if f == 'tvshow.nfo':
                series_nfo = parse_nfo(os.path.join(series_dir, f))

    for entry in sorted(os.listdir(series_dir)):
        entry_path = os.path.join(series_dir, entry)
        if not os.path.isdir(entry_path):
            continue

        # 检查该子目录是否包含视频文件（直接或嵌套）
        has_videos = False
        for root, dirs, files in os.walk(entry_path):
            for f in files:
                if os.path.splitext(f)[1].lower() in VIDEO_EXTS:
                    has_videos = True
                    break
            if has_videos:
                break

        if has_videos:
            show = scan_show_dir(entry_path)
            show['series'] = series_name
            shows.append(show)

    shows.sort(key=lambda x: (x.get('year', 0), x.get('title', '')))
    return shows, series_poster, series_nfo


# ========== 主扫描逻辑 ==========

def scan_all_movies():
    """扫描所有电影系列"""
    movie_base = 'I:/电影/'
    if not os.path.isdir(movie_base):
        print(f'  警告: {movie_base} 不存在，跳过')
        return {}

    all_series = {}
    for entry in os.listdir(movie_base):
        entry_path = os.path.join(movie_base, entry)
        if not os.path.isdir(entry_path):
            continue

        m = re.match(r'^(.+?)[\.\-]\d+', entry)
        series_name = m.group(1) if m else entry

        print(f'  电影系列: {series_name} ({entry})')
        result = scan_movie_series(entry_path, series_name)
        if isinstance(result, tuple) and len(result) == 4:
            movies, series_poster, series_nfo, sub_series_list = result
        elif isinstance(result, tuple):
            movies, series_poster, series_nfo = result[:3]
            sub_series_list = []
        else:
            movies = result
            series_poster, series_nfo, sub_series_list = '', None, []

        if movies:
            series_data = {
                'dir': entry,
                'path': entry_path,
                'count': len(movies),
                'movies': movies
            }
            if series_poster:
                series_data['poster'] = series_poster
            if series_nfo:
                series_data['nfo'] = series_nfo
            all_series[series_name] = series_data

        # 多视频子文件夹作为独立系列
        for sub in sub_series_list:
            sub_name = sub['name']
            # 避免系列名冲突：加后缀
            if sub_name in all_series:
                sub_name = sub_name + '—' + entry
            print(f'    子系列: {sub_name} ({sub["dir"]}, {len(sub["movies"])}部)')
            sub_data = {
                'dir': sub['dir'],
                'path': sub['path'],
                'count': len(sub['movies']),
                'movies': sub['movies'],
            }
            if sub.get('poster'):
                sub_data['poster'] = sub['poster']
            all_series[sub_name] = sub_data

    return all_series


def scan_all_tv():
    """扫描所有电视剧系列"""
    tv_base = 'H:/电视剧/'
    if not os.path.isdir(tv_base):
        print(f'  警告: {tv_base} 不存在，跳过')
        return {}

    all_series = {}
    for entry in os.listdir(tv_base):
        entry_path = os.path.join(tv_base, entry)
        if not os.path.isdir(entry_path):
            continue

        # 判断是系列目录还是独立剧
        has_subdirs = any(os.path.isdir(os.path.join(entry_path, d)) for d in os.listdir(entry_path))
        has_videos = any(os.path.splitext(f)[1].lower() in VIDEO_EXTS for f in os.listdir(entry_path))

        if has_subdirs and entry.endswith('-系列'):
            # 系列目录（金庸-系列等）
            series_name = entry.replace('-系列', '')
            print(f'  电视剧系列: {series_name} ({entry})')
            result = scan_series_group(entry_path, series_name)
            if isinstance(result, tuple):
                shows, sp, snfo = result
            else:
                shows, sp, snfo = result, '', None
            if shows:
                series_data = {
                    'dir': entry,
                    'path': entry_path,
                    'count': len(shows),
                    'shows': shows,
                }
                if sp: series_data['poster'] = sp
                if snfo: series_data['nfo'] = snfo
                all_series[series_name] = series_data
        elif has_videos or has_subdirs:
            # 独立剧/散装目录 — 用 clean_series_name 提取可读性名称
            series_name = clean_series_name(entry)
            if not series_name:
                series_name = entry[:20]
            print(f'  独立电视剧: {series_name[:30]}')
            show = scan_show_dir(entry_path, series_name)
            show['series'] = series_name
            all_series[series_name] = {
                'dir': entry,
                'path': entry_path,
                'count': 1,
                'shows': [show],
                'poster': show.get('poster', ''),
                'nfo': show.get('nfo'),
            }

    return all_series


def scan_all_anime():
    """扫描所有动画片"""
    anime_base = 'I:/动画片/'
    if not os.path.isdir(anime_base):
        print(f'  警告: {anime_base} 不存在，跳过')
        return {}

    all_series = {}
    for entry in os.listdir(anime_base):
        entry_path = os.path.join(anime_base, entry)
        if not os.path.isdir(entry_path):
            continue

        # 检查目录结构
        subdirs = [d for d in os.listdir(entry_path) if os.path.isdir(os.path.join(entry_path, d))]
        vid_count = sum(1 for r, d2, fs in os.walk(entry_path)
                        for f in fs if os.path.splitext(f)[1].lower() in VIDEO_EXTS)

        if vid_count == 0:
            continue

        # 清理名称
        clean_name = clean_series_name(entry)
        if not clean_name:
            clean_name = entry[:30]

        if subdirs and vid_count > 3:
            # 多集系列
            print(f'  动画系列: {clean_name} ({entry})')
            result = scan_series_group(entry_path, clean_name)
            if isinstance(result, tuple):
                shows, sp, snfo = result
            else:
                shows, sp, snfo = result, '', None
            if shows:
                series_data = {
                    'dir': entry,
                    'path': entry_path,
                    'count': len(shows),
                    'shows': shows,
                }
                if sp: series_data['poster'] = sp
                if snfo: series_data['nfo'] = snfo
                all_series[clean_name] = series_data
        else:
            # 单部动画（电影式）
            print(f'  动画: {clean_name} ({entry})')
            result = scan_movie_series(entry_path, clean_name)
            if isinstance(result, tuple) and len(result) == 4:
                movies, sp, snfo, sub_series_list = result
            elif isinstance(result, tuple):
                movies, sp, snfo = result[:3]
                sub_series_list = []
            else:
                movies, sp, snfo, sub_series_list = result, '', None, []
            if movies:
                series_data = {
                    'dir': entry,
                    'path': entry_path,
                    'count': len(movies),
                    'movies': movies,
                }
                if sp: series_data['poster'] = sp
                if snfo: series_data['nfo'] = snfo
                all_series[clean_name] = series_data
            for sub in sub_series_list:
                sub_name = sub['name']
                if sub_name in all_series: sub_name = sub_name + '—' + entry
                print(f'    子系列: {sub_name} ({sub["dir"]}, {len(sub["movies"])}部)')
                all_series[sub_name] = {
                    'dir': sub['dir'], 'path': sub['path'],
                    'count': len(sub['movies']), 'movies': sub['movies'],
                    'poster': sub.get('poster', ''),
                }

    return all_series


def scan_all_docs():
    """扫描所有纪录片"""
    doc_base = 'I:/纪录片/'
    if not os.path.isdir(doc_base):
        print(f'  警告: {doc_base} 不存在，跳过')
        return {}

    all_series = {}
    # 先处理顶级目录
    for entry in sorted(os.listdir(doc_base)):
        entry_path = os.path.join(doc_base, entry)
        if os.path.isdir(entry_path):
            # 检查是否有多集
            vid_count = sum(1 for r, d2, fs in os.walk(entry_path)
                            for f in fs if os.path.splitext(f)[1].lower() in VIDEO_EXTS)
            if vid_count == 0:
                continue

            # 清理名称
            clean_name = clean_series_name(entry)
            clean_name = re.sub(r'^!\s*HD纪录片[：:]\s*', '', clean_name)
            clean_name = clean_name.strip()
            if not clean_name:
                clean_name = entry[:30]

            has_subdirs = any(os.path.isdir(os.path.join(entry_path, d)) for d in os.listdir(entry_path))

            if has_subdirs and vid_count > 5:
                # 有子目录的多集系列（如 BBC纪录片合集）
                print(f'  纪录片系列: {clean_name} ({entry})')
                result = scan_series_group(entry_path, clean_name)
                if isinstance(result, tuple):
                    shows, sp, snfo = result
                else:
                    shows, sp, snfo = result, '', None
                if shows:
                    series_data = {
                        'dir': entry,
                        'path': entry_path,
                        'count': len(shows),
                        'shows': shows,
                    }
                    if sp: series_data['poster'] = sp
                    if snfo: series_data['nfo'] = snfo
                    all_series[clean_name] = series_data
            elif vid_count > 1:
                # 同一目录下的多集纪录片
                print(f'  纪录片: {clean_name} ({entry}, {vid_count}集)')
                show = scan_show_dir(entry_path, clean_name)
                show['series'] = clean_name
                all_series[clean_name] = {
                    'dir': entry,
                    'path': entry_path,
                    'count': 1,
                    'shows': [show],
                    'poster': show.get('poster', ''),
                }
            else:
                # 单文件纪录片 -> 按电影处理
                print(f'  纪录片(单): {clean_name}')
                result = scan_movie_series(entry_path, clean_name)
                if isinstance(result, tuple) and len(result) == 4:
                    movies, sp, snfo, sub_series_list = result
                elif isinstance(result, tuple):
                    movies, sp, snfo = result[:3]
                    sub_series_list = []
                else:
                    movies, sp, snfo, sub_series_list = result, '', None, []
                if movies:
                    all_series[clean_name] = {
                        'dir': entry,
                        'path': entry_path,
                        'count': len(movies),
                        'movies': movies,
                        'poster': sp,
                    }
                for sub in sub_series_list:
                    sub_name = sub['name']
                    if sub_name in all_series: sub_name = sub_name + '—' + entry
                    print(f'    子系列: {sub_name} ({sub["dir"]}, {len(sub["movies"])}部)')
                    all_series[sub_name] = {
                        'dir': sub['dir'], 'path': sub['path'],
                        'count': len(sub['movies']), 'movies': sub['movies'],
                        'poster': sub.get('poster', ''),
                    }

        elif os.path.isfile(entry_path):
            # 顶级散装视频文件
            ext = os.path.splitext(entry)[1].lower()
            if ext in VIDEO_EXTS:
                clean_name = clean_series_name(os.path.splitext(entry)[0])
                if not clean_name:
                    continue
                print(f'  纪录片(文件): {clean_name}')
                all_series[clean_name] = {
                    'dir': '',
                    'path': doc_base,
                    'count': 1,
                    'movies': [{
                        'file': entry,
                        'ext': ext,
                        'series': clean_name,
                        'index': 0,
                        'year': 0,
                        'title': clean_name,
                        'titleEn': '',
                        'actor': '',
                        'audio': '',
                        'size': os.path.getsize(entry_path) if os.path.exists(entry_path) else 0
                    }]
                }

    return all_series


# ========== 数据清理和生成 ==========

def sanitize_str(s):
    """清理字符串中的特殊Unicode控制字符"""
    if not s:
        return s
    return re.sub(r'[\u200b-\u200f\u2028-\u202f\ufeff]', '', str(s))

_PATH_KEYS = {'dir', 'path', 'file', 'poster', 'fanart', 'nfo', 'ext', 'samplePosterFile', 'subdir'}

def sanitize_data(obj, parent_key=''):
    """递归清理数据中的特殊字符，路径字段保留原始值"""
    if isinstance(obj, str):
        if parent_key in _PATH_KEYS:
            return obj
        return sanitize_str(obj)
    elif isinstance(obj, dict):
        return {sanitize_str(str(k)): sanitize_data(v, parent_key=k) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [sanitize_data(item, parent_key=parent_key) for item in obj]
    return obj


def generate_js(data, var_name, filepath):
    """生成 JS 数据文件"""
    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    data = sanitize_data(data)
    json_str = json.dumps(data, ensure_ascii=False, indent=2)
    content = f"""/**
 * 尚唯云影 - {var_name}
 * 自动生成于 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
 * 请勿手动修改，由 auto_scan.py 生成
 */

var {var_name} = {json_str};
"""
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(content)
    print(f'  生成: {filepath} ({len(json_str)} bytes)')


def generate_index(all_series, is_movie=False, overlay=None):
    """生成总索引，保留 overlay 中的系列封面覆盖"""
    series_covers = {}
    if overlay:
        series_covers = overlay.get('series_covers', {})

    index = {}
    for series_name, data in all_series.items():
        entry = {
            'dir': data.get('dir', ''),
            'count': data.get('count', 0),
            'yearRange': '',
            'displayName': clean_series_name(series_name),
        }

        # 优先使用 overlay 中的系列封面（posters/ 格式的手动封面）
        # 但仍需计算 yearRange 等字段
        if is_movie:
            movies = data.get('movies', [])
            years = [int(m['year']) for m in movies if m.get('year') and str(m.get('year','')).isdigit()]
            if years:
                entry['yearRange'] = f'{min(years)}-{max(years)}'
            # 示例海报
            if series_name in series_covers:
                entry['samplePosterFile'] = series_covers[series_name]
            else:
                poster = data.get('poster', '')
                if not poster:
                    for m in movies:
                        mp = m.get('poster', '')
                        if mp:
                            poster = mp
                            break
                if poster:
                    entry['samplePosterFile'] = poster
        else:
            shows = data.get('shows', [])
            total_ep = sum(s.get('episodeCount', 0) for s in shows)
            entry['totalEpisodes'] = total_ep
            years = [int(s['year']) for s in shows if s.get('year') and str(s.get('year','')).isdigit()]
            if years:
                entry['yearRange'] = f'{min(years)}-{max(years)}'
            # 示例海报（overlay 优先）
            if series_name in series_covers:
                entry['samplePosterFile'] = series_covers[series_name]
            else:
                poster = data.get('poster', '')
                if not poster:
                    for s in shows:
                        sp = s.get('poster', '')
                        if sp:
                            # 下载的海报格式：posters/tv/xxx.jpg，直接使用
                            if sp.startswith('posters/') or sp.startswith('fanart/'):
                                poster = sp
                            else:
                                poster = os.path.join(s.get('dir', ''), sp)
                            break
                if poster:
                    entry['samplePosterFile'] = poster

        index[series_name] = entry
    return index


def main():
    print('=' * 50)
    print('  尚唯云影 自动扫描')
    print('=' * 50)
    print()

    stats = {}

    # 1. 扫描电影
    print('[1/4] 扫描电影系列...')
    movie_data = scan_all_movies()
    movie_count = sum(d.get('count', 0) for d in movie_data.values())
    movie_series = len(movie_data)
    print(f'  电影: {movie_series} 个系列, {movie_count} 部电影')
    print()
    stats['movieSeries'] = movie_series
    stats['movieCount'] = movie_count

    # 2. 扫描电视剧
    print('[2/4] 扫描电视剧系列...')
    tv_data = scan_all_tv()
    tv_count = sum(d.get('count', 0) for d in tv_data.values())
    tv_series = len(tv_data)
    print(f'  电视剧: {tv_series} 个系列, {tv_count} 部剧集')
    print()
    stats['tvSeries'] = tv_series
    stats['tvShowCount'] = tv_count

    # 3. 扫描动画片
    print('[3/4] 扫描动画片系列...')
    anime_data = scan_all_anime()
    anime_count = sum(d.get('count', 0) for d in anime_data.values())
    anime_series = len(anime_data)
    print(f'  动画片: {anime_series} 个系列, {anime_count} 部')
    print()
    stats['animeSeries'] = anime_series
    stats['animeCount'] = anime_count

    # 4. 扫描纪录片
    print('[4/4] 扫描纪录片系列...')
    doc_data = scan_all_docs()
    doc_count = sum(d.get('count', 0) for d in doc_data.values())
    doc_series = len(doc_data)
    print(f'  纪录片: {doc_series} 个系列, {doc_count} 部')
    print()
    stats['docSeries'] = doc_series
    stats['docCount'] = doc_count

    stats['scanTime'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    stats['totalSeries'] = movie_series + tv_series + anime_series + doc_series
    stats['totalItems'] = movie_count + tv_count + anime_count + doc_count

    # 加载刮削覆盖数据
    print()
    print('加载刮削覆盖数据（scrape_overlay.json）...')
    overlay = load_overlay()
    if overlay:
        by_imdb = len(overlay.get('by_imdbid', {}))
        by_title = len(overlay.get('by_title_year', {}))
        covers = len(overlay.get('series_covers', {}))
        print(f'  覆盖数据: {by_imdb} 条(imdbid), {by_title} 条(title|year), {covers} 条(系列封面)')
    else:
        print('  无覆盖数据文件，跳过')

    # 应用刮削覆盖数据到扫描结果（优先级高于 merge_nfo_cache）
    if overlay:
        print()
        print('应用刮削覆盖数据...')
        for data, var_name in [
            (movie_data, 'MOVIE_DATA'),
            (tv_data, 'TV_DATA'),
            (anime_data, 'ANIME_DATA'),
            (doc_data, 'DOC_DATA'),
        ]:
            count = apply_overlay(data, overlay)
            print(f'  {var_name}: 应用 {count} 条覆盖')

    # 合并已有NFO缓存（保留 metadata_enhance.py 增强的元数据，作为补充）
    print()
    print('合并NFO缓存（补充遗留元数据）...')
    for data, var_name, filename in [
        (movie_data, 'MOVIE_DATA', 'movie-data.js'),
        (tv_data, 'TV_DATA', 'tv-data.js'),
        (anime_data, 'ANIME_DATA', 'anime-data.js'),
        (doc_data, 'DOC_DATA', 'doc-data.js'),
    ]:
        filepath = os.path.join(DATA_DIR, filename)
        old = load_js_var(filepath)
        if old:
            count = merge_nfo_cache(data, old)
            print(f'  {var_name}: 补充 {count} 条NFO')

    # 生成数据文件
    print()
    generate_js(movie_data, 'MOVIE_DATA', os.path.join(DATA_DIR, 'movie-data.js'))
    generate_js(tv_data, 'TV_DATA', os.path.join(DATA_DIR, 'tv-data.js'))
    generate_js(anime_data, 'ANIME_DATA', os.path.join(DATA_DIR, 'anime-data.js'))
    generate_js(doc_data, 'DOC_DATA', os.path.join(DATA_DIR, 'doc-data.js'))

    generate_js(generate_index(movie_data, is_movie=True, overlay=overlay), 'MOVIE_INDEX', os.path.join(DATA_DIR, 'movie-index.js'))
    generate_js(generate_index(tv_data, overlay=overlay), 'TV_INDEX', os.path.join(DATA_DIR, 'tv-index.js'))
    generate_js(generate_index(anime_data, overlay=overlay), 'ANIME_INDEX', os.path.join(DATA_DIR, 'anime-index.js'))
    generate_js(generate_index(doc_data, overlay=overlay), 'DOC_INDEX', os.path.join(DATA_DIR, 'doc-index.js'))

    generate_js(stats, 'LIBRARY_STATS', os.path.join(DATA_DIR, 'stats.js'))

    print()
    print('完成!')
    print(f'  电影: {movie_series}系列 {movie_count}部')
    print(f'  电视剧: {tv_series}系列 {tv_count}部')
    print(f'  动画片: {anime_series}系列 {anime_count}部')
    print(f'  纪录片: {doc_series}系列 {doc_count}部')
    print(f'  总计: {stats["totalSeries"]}系列 {stats["totalItems"]}部')
    print(f'  数据目录: {DATA_DIR}')


if __name__ == '__main__':
    main()
