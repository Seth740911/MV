#!/usr/bin/env python3
"""
尚唯云影 - 元数据增强脚本
使用 Cinemeta（Popcorn Time 开源API，免费无需Key）补全缺失的元数据：
- 评分 (imdbRating)
- 演员 (cast) + 演员头像
- 剧情 (description)
- 类型 (genres)
- 导演 (director)
- 海报URL (poster)
- 背景图URL (background)

输出方式：写入 scrape_overlay.json（与 auto_scan.py 对齐）
不再直接修改 JS 文件（会被 auto_scan 覆盖）

Cinemeta API:
  搜索: https://v3-cinemeta.strem.io/catalog/{type}/top/search={query}.json
  详情: https://v3-cinemeta.strem.io/meta/{type}/{imdb_id}.json
  type = movie | series
"""

import os
import re
import json
import sys
import time
import urllib.request
import urllib.error
import urllib.parse

if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')

MV_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(MV_DIR, 'data')
OVERLAY_PATH = os.path.join(DATA_DIR, 'scrape_overlay.json')

CINEMETA_SEARCH = 'https://v3-cinemeta.strem.io/catalog/{type}/top/search={query}.json'
CINEMETA_DETAIL = 'https://v3-cinemeta.strem.io/meta/{type}/{id}.json'

REQUEST_DELAY = 0.3
MAX_RETRIES = 3


def load_overlay():
    """加载已有的 scrape_overlay.json"""
    if not os.path.exists(OVERLAY_PATH):
        return {"version": 1, "generated": "", "by_imdbid": {}, "by_title_year": {}, "series_covers": {}}
    try:
        with open(OVERLAY_PATH, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        print('  [Cinemeta] 加载 overlay 失败: %s' % e)
        return {"version": 1, "generated": "", "by_imdbid": {}, "by_title_year": {}, "series_covers": {}}


def save_overlay(overlay):
    """保存 overlay 到 scrape_overlay.json"""
    overlay['generated'] = time.strftime('%Y-%m-%d %H:%M:%S')
    with open(OVERLAY_PATH, 'w', encoding='utf-8') as f:
        json.dump(overlay, f, ensure_ascii=False, indent=2)
    size = os.path.getsize(OVERLAY_PATH)
    print('  已保存 overlay: %s (%d bytes)' % (OVERLAY_PATH, size))


def load_js_var(filepath):
    """加载 JS var 文件为 Python dict"""
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
    content = re.sub(r'^/\*.*?\*/', '', content, flags=re.DOTALL)
    content = re.sub(r'^var\s+\w+\s*=\s*', '', content.strip())
    content = content.rstrip().rstrip(';')
    return json.loads(content)


def cinemeta_search(query, mediatype='movie'):
    """搜索 Cinemeta，返回匹配结果列表，带重试"""
    url = CINEMETA_SEARCH.format(type=mediatype, query=urllib.parse.quote(query))
    for attempt in range(MAX_RETRIES):
        try:
            req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
            import ssl
            ctx = ssl.create_default_context()
            ctx.check_hostname = False
            ctx.verify_mode = ssl.CERT_NONE
            with urllib.request.urlopen(req, timeout=20, context=ctx) as resp:
                data = json.loads(resp.read().decode('utf-8'))
            metas = data.get('metas', [])
            if metas:
                return metas
            return []
        except Exception as e:
            if attempt < MAX_RETRIES - 1:
                time.sleep(1)
            else:
                print('    搜索失败 [%s]: %s' % (query, str(e)[:80]))
    return []


def cinemeta_detail(imdb_id, mediatype='movie'):
    """获取 Cinemeta 详情，带重试"""
    url = CINEMETA_DETAIL.format(type=mediatype, id=imdb_id)
    for attempt in range(MAX_RETRIES):
        try:
            req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
            import ssl
            ctx = ssl.create_default_context()
            ctx.check_hostname = False
            ctx.verify_mode = ssl.CERT_NONE
            with urllib.request.urlopen(req, timeout=20, context=ctx) as resp:
                data = json.loads(resp.read().decode('utf-8'))
            meta = data.get('meta', {})
            return meta
        except Exception as e:
            if attempt < MAX_RETRIES - 1:
                time.sleep(1)
            else:
                print('    详情失败 [%s]: %s' % (imdb_id, str(e)[:80]))
    return {}


def find_best_match(query, results, expected_year=None):
    """从搜索结果中找最佳匹配"""
    if not results:
        return None

    # 优先匹配年份
    if expected_year:
        for r in results:
            name = r.get('name', '')
            year = r.get('year', '')
            if str(expected_year) == str(year) and query.lower() in name.lower():
                return r

    # 其次匹配名称包含
    for r in results:
        name = r.get('name', '')
        if query.lower() in name.lower() or name.lower() in query.lower():
            return r

    # 兜底返回第一个
    return results[0]


def extract_meta_from_cinemeta(meta):
    """从 Cinemeta 详情提取我们需要的字段"""
    if not isinstance(meta, dict):
        return {}
    result = {}

    # 评分（Cinemeta 的 rating 可能是 dict 也可能是 string）
    raw_rating = meta.get('imdbRating') or meta.get('rating')
    if isinstance(raw_rating, dict):
        rating_val = raw_rating.get('value', '')
    elif isinstance(raw_rating, (str, int, float)):
        rating_val = str(raw_rating) if raw_rating else ''
    else:
        rating_val = ''
    if rating_val and rating_val != '0' and rating_val != 'N/A':
        # Cinemeta 返回的是 0-10 或 0-100 的评分
        try:
            rv = float(rating_val)
            # 如果评分在 0-1 之间（如 0.7），可能是百分比归一化，跳过
            if rv > 0 and rv < 1:
                pass  # 太低，可能是错误数据
            elif rv > 10:
                rv = rv / 10
            if rv >= 1 and rv <= 10:
                result['rating'] = '%.1f' % rv
        except:
            pass

    # 投票数
    vote_count = meta.get('imdbVoteCount', '')
    if vote_count:
        result['vote_count'] = str(vote_count)

    # 剧情
    description = meta.get('description', '')
    if description:
        result['plot'] = description

    # 类型
    genres = meta.get('genres', [])
    if genres and isinstance(genres, list):
        result['genres'] = genres

    # 演员
    cast = meta.get('cast', [])
    if cast and isinstance(cast, list):
        actors = []
        for actor in cast[:20]:
            if isinstance(actor, str):
                actors.append({'name': actor})
            elif isinstance(actor, dict):
                a = {'name': actor.get('name', '')}
                if actor.get('role'):
                    a['role'] = actor['role']
                if actor.get('poster'):
                    a['thumb'] = actor['poster']
                actors.append(a)
        if actors:
            result['actors'] = actors

    # 导演
    director = meta.get('director', '')
    if director:
        if isinstance(director, str):
            directors = [{'name': d.strip()} for d in director.split(',') if d.strip()]
        elif isinstance(director, list):
            directors = [{'name': d.get('name', d) if isinstance(d, dict) else str(d)} for d in director]
        else:
            directors = []
        if directors:
            result['directors'] = directors

    # 年份
    year = meta.get('year', '')
    if year and str(year) != '0':
        result['year'] = str(year)

    # 海报 (仅记录URL，不下载)
    poster_url = meta.get('poster', '')
    if poster_url:
        result['poster_url'] = poster_url.replace('http://', 'https://')

    # 背景图
    bg_url = meta.get('background', '')
    if bg_url:
        result['fanart_url'] = bg_url.replace('http://', 'https://')

    # IMDB ID
    imdb_id = meta.get('imdb_id', '')
    if imdb_id:
        result['imdbid'] = imdb_id

    # 运行时长
    runtime = meta.get('runtime', '')
    if runtime:
        result['runtime'] = str(runtime)

    # 国家
    country = meta.get('country', '')
    if country:
        result['country'] = country

    return result


def build_search_query(title, title_en='', year=0):
    """构建搜索查询字符串"""
    # 如果英文名里有年份前的有效片段，优先用
    # 清理英文名中的质量标签
    clean_en = re.sub(r'\b(720p|1080p|2160p|4K|HDTV|WEB-DL|BluRay|x264|x265|H264|H265|AAC|DTS|RMVB|MKV|MP4)\b.*', '', title_en or '', flags=re.IGNORECASE)
    clean_en = clean_en.replace('.', ' ').strip()

    # 清理中文名中的质量标签
    clean_cn = re.sub(r'[\[【].*?[\]】]', '', title)
    clean_cn = re.sub(r'\d{3,}[Pp].*', '', clean_cn)
    clean_cn = clean_cn.replace('_', ' ').strip()

    # 优先用英文名
    if clean_en and len(clean_en) > 2:
        query = clean_en
    elif clean_cn and len(clean_cn) > 1:
        query = clean_cn
    else:
        return ''

    # 跳过纯数字或太短的查询
    if query.isdigit() or len(query) < 2:
        return ''

    # 如果有年份，附加到搜索词
    if year and int(year) > 1900:
        query = query + ' ' + str(year)

    return query.strip()


def should_skip(title):
    """跳过明显不可搜索的脏文件名"""
    stripped = title.strip()
    # 纯数字
    if re.match(r'^\d+$', stripped):
        return True
    # 质量标签开头
    if re.match(r'^[\d]+[Pp][.\s]', stripped):
        return True
    # 太短
    if len(stripped) < 2:
        return True
    # 纯编码标签（如 BD1080P.X264.AAC...）
    if re.match(r'^(BD|DVD|1080[Pp]|720[Pp]|2160[Pp]|4K|WEB|HDTV)[.\s]', stripped, re.IGNORECASE):
        if not re.search(r'[\u4e00-\u9fff]', stripped):
            return True
    # FC2等成人内容编号
    if re.match(r'^FC2', stripped, re.IGNORECASE):
        return True
    return False


def needs_enhancement(item):
    """判断一个条目是否需要补全元数据"""
    nfo = item.get('nfo')
    if not nfo:
        return True
    if not nfo.get('rating'):
        return True
    if not nfo.get('actors') or len(nfo.get('actors', [])) == 0:
        return True
    if not nfo.get('plot') and not nfo.get('biography'):
        return True
    if not nfo.get('genres') or len(nfo.get('genres', [])) == 0:
        return True
    return False


def enhance_item(item, cat_type='movie'):
    """在线补全单个条目的元数据，返回是否成功"""
    title = item.get('title', '')
    title_en = item.get('titleEn', '')
    year = item.get('year', 0)

    query = build_search_query(title, title_en, year)
    if not query:
        return False

    mediatype = 'series' if cat_type in ('tv', 'series') else 'movie'

    # 搜索
    results = cinemeta_search(query, mediatype)
    if not results and title and title != query.split(str(year))[0].strip() if year else True:
        # 尝试只用中文名搜索
        query2 = title
        if year and int(year) > 1900:
            query2 += ' ' + str(year)
        if query2 != query:
            results = cinemeta_search(query2, mediatype)

    if not results:
        return False

    # 找最佳匹配
    best = find_best_match(title, results, year)
    if not best:
        return False

    imdb_id = best.get('imdb_id', '')
    if not imdb_id:
        return False

    # 获取详情
    time.sleep(REQUEST_DELAY)
    detail = cinemeta_detail(imdb_id, mediatype)
    if not detail:
        return False

    meta = extract_meta_from_cinemeta(detail)
    if not meta:
        return False

    # 合并到 item 的 nfo 字段
    if 'nfo' not in item or not item.get('nfo'):
        item['nfo'] = {}
    nfo = item['nfo']

    # 只补全缺失字段，不覆盖已有数据
    if not nfo.get('rating') and meta.get('rating'):
        nfo['rating'] = meta['rating']
    if not nfo.get('vote_count') and meta.get('vote_count'):
        nfo['vote_count'] = meta['vote_count']
    if not nfo.get('plot') and not nfo.get('biography') and meta.get('plot'):
        nfo['plot'] = meta['plot']
    if not nfo.get('genres') and meta.get('genres'):
        nfo['genres'] = meta['genres']
    if not nfo.get('actors') and meta.get('actors'):
        nfo['actors'] = meta['actors']
    if not nfo.get('directors') and meta.get('directors'):
        nfo['directors'] = meta['directors']
    if not nfo.get('imdbid') and meta.get('imdbid'):
        nfo['imdbid'] = meta['imdbid']
    if not nfo.get('runtime') and meta.get('runtime'):
        nfo['runtime'] = meta['runtime']
    if not nfo.get('country') and meta.get('country'):
        nfo['country'] = meta['country']

    # 补全年份（如果原来没有）
    if not item.get('year') and meta.get('year'):
        try:
            item['year'] = int(meta['year'])
        except:
            pass

    # 记录在线海报URL（不自动下载，仅记录）
    if meta.get('poster_url') and not item.get('poster'):
        nfo['online_poster'] = meta['poster_url']
    if meta.get('fanart_url') and not item.get('fanart'):
        nfo['online_fanart'] = meta['fanart_url']

    return True


def write_overlay_entry(overlay, item, nfo_data):
    """将增强数据写入 overlay（by_imdbid 和 by_title_year），仅覆盖空值"""
    imdbid = nfo_data.get('imdbid', '')

    # 查找已有 entry
    existing_entry = None
    if imdbid and imdbid in overlay.get('by_imdbid', {}):
        existing_entry = overlay['by_imdbid'][imdbid]
    else:
        title = item.get('title', '')
        year = item.get('year', 0)
        key = '%s|%s' % (title, year)
        if key in overlay.get('by_title_year', {}):
            existing_entry = overlay['by_title_year'][key]

    if existing_entry:
        # 深度合并 nfo 字段：仅覆盖空值
        if 'nfo' not in existing_entry:
            existing_entry['nfo'] = {}
        for k, v in nfo_data.items():
            if v and not existing_entry['nfo'].get(k):
                existing_entry['nfo'][k] = v
    else:
        existing_entry = {'nfo': nfo_data}

    # 写入 by_imdbid
    if imdbid:
        overlay.setdefault('by_imdbid', {})[imdbid] = existing_entry

    # 写入 by_title_year
    title = item.get('title', '')
    year = item.get('year', 0)
    key = '%s|%s' % (title, year)
    if title:
        overlay.setdefault('by_title_year', {})[key] = existing_entry


def enhance_category(data_var_name, cat_type='movie'):
    """增强一个分类的所有数据，结果写入 scrape_overlay.json"""
    filepath = os.path.join(DATA_DIR, data_var_name.lower().replace('_', '-') + '.js')
    if not os.path.exists(filepath):
        print('  文件不存在: %s' % filepath)
        return

    print('=' * 60)
    print('  Cinemeta增强: %s (%s)' % (data_var_name, cat_type))
    print('=' * 60)

    data = load_js_var(filepath)

    # 加载已有 overlay
    overlay = load_overlay()
    print('  overlay 现有: imdbid=%d, title_year=%d' % (
        len(overlay.get('by_imdbid', {})), len(overlay.get('by_title_year', {}))))

    total_items = 0
    need_enhance = 0
    enhanced = 0
    failed = 0

    for series_name, series in data.items():
        items = series.get('movies', series.get('shows', []))
        for item in items:
            total_items += 1
            if needs_enhancement(item):
                need_enhance += 1

    print('  总条目: %d, 需补全: %d' % (total_items, need_enhance))
    print()

    if need_enhance == 0:
        print('  所有条目元数据已完整，跳过')
        return

    counter = 0
    break_all = False
    for series_name, series in data.items():
        if break_all:
            break
        items = series.get('movies', series.get('shows', []))
        for item in items:
            if not needs_enhancement(item):
                continue

            counter += 1
            title = item.get('title', series_name)
            title_en = item.get('titleEn', '')

            # 跳过明显不可搜索的脏名
            if should_skip(title):
                continue

            display = title_en if title_en else title
            display = display[:40]
            print('  [%d/%d] %s' % (counter, need_enhance, display), end='', flush=True)

            success = enhance_item(item, cat_type)
            if success:
                enhanced += 1
                rating = item.get('nfo', {}).get('rating', '')
                print(' -> OK (rating=%s)' % rating)

                # 写入 overlay
                nfo_data = item.get('nfo', {})
                write_overlay_entry(overlay, item, nfo_data)
            else:
                failed += 1
                print(' -> MISS')

            time.sleep(REQUEST_DELAY)

            # 测试模式
            if '_TEST_LIMIT' in globals() and _TEST_LIMIT > 0 and counter >= _TEST_LIMIT:
                break_all = True
                break

            # 每50个保存一次
            if counter % 50 == 0:
                save_overlay(overlay)
                print('  --- 中途保存 ---')

    # 最终保存
    save_overlay(overlay)
    print()
    print('  完成: 补全 %d / 失败 %d / 总需 %d' % (enhanced, failed, need_enhance))
    print()


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--test', type=int, default=0, help='只测试前N条')
    parser.add_argument('--cat', type=str, default='', help='只增强指定分类(tv/anime/doc/movie)')
    args = parser.parse_args()

    print()
    print('*' * 60)
    print('  尚唯云影 Cinemeta元数据增强')
    print('  使用 Cinemeta (免费开放API，无需Key)')
    print('  输出: scrape_overlay.json')
    print('*' * 60)
    print()

    cats = []
    if args.cat:
        cat_map = {'tv': ('TV_DATA', 'series'), 'anime': ('ANIME_DATA', 'series'),
                   'doc': ('DOC_DATA', 'series'), 'movie': ('MOVIE_DATA', 'movie')}
        cats = [cat_map[args.cat]]
    else:
        cats = [('MOVIE_DATA', 'movie'), ('TV_DATA', 'series'),
                ('ANIME_DATA', 'series'), ('DOC_DATA', 'series')]

    global _TEST_LIMIT
    _TEST_LIMIT = args.test

    for var_name, cat_type in cats:
        enhance_category(var_name, cat_type)
        if _TEST_LIMIT > 0:
            break

    print()
    print('全部增强完成!')
    print('数据已写入 scrape_overlay.json，下次运行 auto_scan.py 时自动合并。')


if __name__ == '__main__':
    main()
