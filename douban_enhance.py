#!/usr/bin/env python3
"""
尚唯云影 - 豆瓣元数据增强脚本
使用豆瓣搜索 + 详情API补全缺失的中文元数据：
- 豆瓣评分 (rate)
- 演员 (actors)
- 导演 (directors)
- 类型 (types)
- 剧情简介 (plot)
- 年份/地区/集数/时长

优势：中文匹配精准，无需API Key，无需注册

输出方式：写入 scrape_overlay.json（与 auto_scan.py 对齐）
不再直接修改 JS 文件（会被 auto_scan 覆盖）
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

REQUEST_DELAY = 3.0    # 豆瓣搜索间隔3秒
DETAIL_DELAY = 2.0     # 详情API间隔2秒
BACKOFF_DELAY = 30.0   # 遇到403后退避30秒
MAX_RETRIES = 3
SEARCH_HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
    'Accept': 'application/json',
    'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
    'Referer': 'https://movie.douban.com/',
}

# 豆瓣搜索分类 cat 参数（subject_suggest 不需要 cat） 


def load_overlay():
    """加载已有的 scrape_overlay.json"""
    if not os.path.exists(OVERLAY_PATH):
        return {"version": 1, "generated": "", "by_imdbid": {}, "by_title_year": {}, "series_covers": {}}
    try:
        with open(OVERLAY_PATH, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        print('  [豆瓣] 加载 overlay 失败: %s' % e)
        return {"version": 1, "generated": "", "by_imdbid": {}, "by_title_year": {}, "series_covers": {}}


def save_overlay(overlay):
    """保存 overlay 到 scrape_overlay.json"""
    overlay['generated'] = time.strftime('%Y-%m-%d %H:%M:%S')
    with open(OVERLAY_PATH, 'w', encoding='utf-8') as f:
        json.dump(overlay, f, ensure_ascii=False, indent=2)
    size = os.path.getsize(OVERLAY_PATH)
    print('  已保存 overlay: %s (%d bytes)' % (OVERLAY_PATH, size))


def douban_search(query):
    """
    使用豆瓣 subject_suggest API 搜索（直接返回JSON，无需解析HTML）
    返回 [{id, title, year, type, cover, episode}, ...]
    """
    url = 'https://movie.douban.com/j/subject_suggest?q=%s' % urllib.parse.quote(query)
    for attempt in range(MAX_RETRIES):
        try:
            req = urllib.request.Request(url, headers=SEARCH_HEADERS)
            with urllib.request.urlopen(req, timeout=15) as resp:
                raw = resp.read().decode('utf-8')
                items = json.loads(raw)

            results = []
            for item in items:
                results.append({
                    'id': item.get('id', ''),
                    'title': item.get('title', ''),
                    'year': item.get('year', ''),
                    'type': item.get('type', ''),
                    'cover': item.get('img', ''),
                    'episode': item.get('episode', ''),
                    'sub_title': item.get('sub_title', ''),
                })
            return results

        except urllib.error.HTTPError as e:
            if e.code == 403:
                wait = BACKOFF_DELAY * (attempt + 1)
                print('\n    [403] 等待%.0fs...' % wait, end='', flush=True)
                time.sleep(wait)
            else:
                if attempt < MAX_RETRIES - 1:
                    time.sleep(3)
                else:
                    print('    [搜索失败] HTTP %d' % e.code)
                    return []
        except Exception as e:
            if attempt < MAX_RETRIES - 1:
                time.sleep(2)
            else:
                print('    [搜索失败] %s' % str(e)[:80])
                return []
    return []


def douban_detail(douban_id):
    """
    获取豆瓣影片详情（subject_abstract API）
    返回 {rate, actors, directors, types, duration, region, release_year, is_tv, episodes_count, short_comment}
    """
    url = 'https://movie.douban.com/j/subject_abstract?subject_id=%s' % douban_id
    for attempt in range(MAX_RETRIES):
        try:
            req = urllib.request.Request(url, headers=SEARCH_HEADERS)
            with urllib.request.urlopen(req, timeout=15) as resp:
                data = json.loads(resp.read().decode('utf-8'))

            subject = data.get('subject', {})
            return subject

        except urllib.error.HTTPError as e:
            if e.code == 403:
                wait = BACKOFF_DELAY * (attempt + 1)
                print('\n    [详情403] 等待%.0fs...' % wait, end='', flush=True)
                time.sleep(wait)
            else:
                if attempt < MAX_RETRIES - 1:
                    time.sleep(2)
                else:
                    return None
        except Exception as e:
            if attempt < MAX_RETRIES - 1:
                time.sleep(2)
            else:
                return None


def clean_title_for_search(title):
    """
    清理标题用于豆瓣搜索：去除质量标签、年份括号、发布组等
    策略：激进清理，只保留中文核心名称
    """
    s = title

    # 第一轮：去掉【】[] 整体内容（字幕组、质量标签等）
    for _ in range(5):
        new_s = re.sub(r'[【\[][^\]】]*?[】\]]', '', s)
        if new_s == s:
            break
        s = new_s

    # 去掉圆括号内的说明词（动画版、国语、粤语、中字等）
    s = re.sub(r'[（(](?:动画版|国语|粤语|中字|中文字幕|双语|国日粤三语|简繁字幕|DVDRip|HDTV|HD|TV|OVA|SP|特别篇)[^）)]*[）)]', '', s)

    # 去掉年份括号 (1987) (2010)
    s = re.sub(r'\s*[(\uff08]\d{4}[)\uff09]\s*', ' ', s)

    # 去掉集数标记
    s = re.sub(r'\d+集全?', '', s)
    s = re.sub(r'全\d+集', '', s)
    s = re.sub(r'第[一二三四五六七八九十\d]+[季部集]', '', s)
    s = re.sub(r'全集', '', s)

    # 去掉质量/编码标签
    s = re.sub(r'(?:720[Pp]|1080[Pp]|2160[Pp]|4K|HR|Hi10p|AVC|HEVC|x264|x265|H264|H265|AC3|AAC|MP4|MKV|RMVB|DVDRip|HDTV|BluRay|WEB[-]?DL|WEB|MiniSD|SD|HR|HDTV|GB_JP|GB|JP)\b', '', s, flags=re.IGNORECASE)

    # 去掉点号分隔的英文词（如 .双语字幕.HR, .Krtek）
    s = re.sub(r'\.[A-Za-z][A-Za-z0-9.]*', '', s)
    # 去掉连字符后缀（如 -TLF, -YGSUB）
    s = re.sub(r'\s*[-–—]\s*[A-Za-z][A-Za-z0-9]*', '', s)

    # 如果是英文+中文混合，保留中文核心
    has_chinese = bool(re.search(r'[\u4e00-\u9fff]', s))
    if has_chinese:
        # 去掉独立的英文单词（保留中文部分）
        s = re.sub(r'\b[A-Za-z]+\b', '', s)

    # 去掉多余空格和残留标点
    s = re.sub(r'\s+', ' ', s).strip()
    s = re.sub(r'^[.\-–—\s\[(【]+', '', s)
    s = re.sub(r'[.\-–—\s\])】]+$', '', s)

    # 如果清理后结果太短或无意义，返回空
    if len(s.strip()) < 2:
        return ''

    return s.strip()


def match_search_result(title, year, results):
    """
    从 subject_suggest 搜索结果中找最佳匹配
    返回最佳匹配的 result dict 或 None
    """
    if not results:
        return None

    year_int = 0
    try:
        year_int = int(year) if year else 0
    except:
        pass

    # 标准化函数：去空格、去括号，用于模糊匹配
    def normalize(s):
        s = re.sub(r'\s+', '', s)
        s = re.sub(r'[\[\]【】()（）]', '', s)
        return s.lower()

    # 去掉标题中的年份和方括号用于比较
    clean_title = re.sub(r'\s*[(\uff08]\d{4}[)\uff09]', '', title).strip()
    clean_title = re.sub(r'[\[\]【】]', '', clean_title).strip()
    norm_clean = normalize(clean_title)

    best = None
    best_score = 0

    for r in results:
        r_title = r.get('title', '')
        r_year = r.get('year', '')
        norm_r_title = normalize(r_title)

        score = 0

        # 标题匹配（标准化后比较）
        if norm_clean and norm_clean in norm_r_title:
            score += 100
        elif norm_r_title and norm_r_title in norm_clean:
            score += 80
        # sub_title 匹配（英文名/别名）
        elif r.get('sub_title') and norm_clean in normalize(r['sub_title']):
            score += 60
        # 部分匹配：核心词至少3个字重叠
        elif len(norm_clean) >= 3:
            for i in range(len(norm_clean) - 2):
                if norm_clean[i:i+3] in norm_r_title:
                    score += 40
                    break

        # 年份匹配
        if year_int > 1900 and r_year:
            try:
                r_year_int = int(r_year)
                if r_year_int == year_int:
                    score += 50
                elif abs(r_year_int - year_int) <= 1 and r_year_int > 0:
                    score += 30
            except:
                pass

        if score > best_score:
            best_score = score
            best = r

    # 至少要40分
    if best_score >= 40:
        return best
    return None


def needs_enhancement(item):
    """判断条目是否需要豆瓣增强"""
    nfo = item.get('nfo')
    if not nfo or nfo is None:
        return True
    # 没有评分
    if not nfo.get('rating'):
        return True
    # 评分有但缺演员
    if not nfo.get('actors') or len(nfo.get('actors', [])) == 0:
        return True
    # 评分有但缺类型
    if not nfo.get('genres') or len(nfo.get('genres', [])) == 0:
        return True
    # 缺剧情简介
    if not nfo.get('plot'):
        return True
    return False


def should_skip(title):
    """判断是否应该跳过（不可搜索的脏名）"""
    stripped = title.strip()
    # 纯数字
    if re.match(r'^\d+$', stripped):
        return True
    # 质量标签为主（如 720p.BluRay 等）
    if re.match(r'^[\d]+[Pp]\.', stripped):
        return True
    # 太短
    if len(stripped) < 2:
        return True
    # 哆啦A梦新番的散集号（如 [Doraemon][2005]001）
    if re.match(r'^\[哆啦A梦新番\]\[Doraemon\]\[\d{4}\]\d+$', stripped):
        return True
    return False


def extract_core_name(title):
    """
    从标题中提取核心名称，分两步：
    1. 先尝试 clean_title_for_search 的全面清理
    2. 如果清理后为空，尝试从方括号中提取有意义的中文片段
    """
    cleaned = clean_title_for_search(title)
    if cleaned:
        return cleaned

    # 清理失败时的后备方案：从方括号/圆括号中找中文片段
    # 收集所有方括号和圆括号内的内容，保持顺序
    brackets = re.findall(r'[【\[]([^】\]]+)[】\]]', title)
    parens = re.findall(r'[（(]([^）)]+)[）)]', title)

    candidates = []
    for b in brackets:
        # 只取含中文的片段
        if re.search(r'[\u4e00-\u9fff]{2,}', b):
            # 跳过纯标签（年份、国语、集数等）
            if re.match(r'^\d{4}$', b.strip()):
                continue
            if re.match(r'^(国语|中字|DVD|RMVB|全\d+集|\d+集全?|720[Pp]|1080[Pp])$', b.strip(), re.IGNORECASE):
                continue
            if len(b.strip()) >= 2 and re.search(r'[\u4e00-\u9fff]', b):
                candidates.append(b.strip())

    for p in parens:
        if re.search(r'[\u4e00-\u9fff]{2,}', p):
            candidates.append(p.strip())

    # 优先选择第一个候选（方括号顺序通常是：作品名+年份+标签+...）
    # 如果第一个太长（>20字含标签杂词），尝试更短的
    if candidates:
        # 计算中文字符占比，占比高的更可能是作品名
        def chinese_ratio(s):
            cn = len(re.findall(r'[\u4e00-\u9fff]', s))
            return cn / max(len(s), 1)

        # 排除纯国家名（如"日本"、"美国"）
        country_names = {'日本', '美国', '中国', '韩国', '英国', '法国', '德国', '泰国', '印度', '意大利', '西班牙', '俄罗斯', '加拿大', '澳大利亚', '巴西'}
        filtered = [c for c in candidates if c not in country_names and len(c) > 2]

        if filtered:
            # 过滤掉中文占比过低的（<0.3通常是标签堆砌）
            good = [c for c in filtered if chinese_ratio(c) >= 0.3]
            if good:
                # 从good中选第一个（保持原始顺序）
                return good[0]
            # 如果都过低，选中文占比最高的
            filtered.sort(key=chinese_ratio, reverse=True)
            return filtered[0]
        # fallback to unfiltered
        if candidates:
            candidates.sort(key=chinese_ratio, reverse=True)
            return candidates[0]

    # 最后兜底：直接取标题中连续中文
    chinese_match = re.search(r'[\u4e00-\u9fff]{2,}', title)
    if chinese_match:
        return chinese_match.group()

    return ''


def enhance_with_douban(item, cat_type='tv'):
    """用豆瓣 subject_suggest + subject_abstract 增强单个条目"""
    title = item.get('title', '')
    year = item.get('year', 0)

    if should_skip(title):
        return False

    # 构建搜索查询（两步：先全面清理，再提取核心名）
    query = extract_core_name(title)
    if not query or len(query) < 2:
        return False

    # 最后再清理一次：去掉残留标签（双语字幕、加长版等后缀）
    query = re.sub(r'[.．]\s*双语字幕$', '', query)
    query = re.sub(r'[.．]\s*中字$', '', query)
    query = re.sub(r'\s*加长版$', '', query)
    query = re.sub(r'\s*国语$', '', query)
    query = re.sub(r'\s*TV版$', '', query)
    query = query.strip()
    if not query or len(query) < 2:
        return False

    # subject_suggest 搜索
    results = douban_search(query)
    if not results and len(query) > 4:
        # 搜索失败时，尝试缩短查询（去掉后缀如"真人版"、"TV版"等）
        short_query = re.sub(r'(真人版|TV版|剧场版|总集篇|特别篇|新番|旧版|完结篇)$', '', query).strip()
        if short_query and len(short_query) >= 2 and short_query != query:
            time.sleep(1)
            results = douban_search(short_query)
    if not results:
        return False

    # 找最佳匹配
    best = match_search_result(title, year, results)
    if not best or not best.get('id'):
        return False

    # 获取详情
    time.sleep(DETAIL_DELAY)
    detail = douban_detail(best['id'])
    if not detail:
        return False

    # 合并到 item 的 nfo 字段
    if 'nfo' not in item or not item.get('nfo'):
        item['nfo'] = {}
    nfo = item['nfo']

    # 豆瓣评分
    if not nfo.get('rating') and detail.get('rate'):
        nfo['rating'] = str(detail.get('rate'))

    # 演员
    if (not nfo.get('actors') or len(nfo.get('actors', [])) == 0) and detail.get('actors'):
        nfo['actors'] = [{'name': a} for a in detail['actors']]

    # 导演
    if (not nfo.get('directors') or len(nfo.get('directors', [])) == 0) and detail.get('directors'):
        nfo['directors'] = [{'name': d} for d in detail['directors']]

    # 类型
    if (not nfo.get('genres') or len(nfo.get('genres', [])) == 0) and detail.get('types'):
        nfo['genres'] = detail['types']

    # 剧情简介
    if not nfo.get('plot') and detail.get('short_comment', {}).get('content'):
        nfo['plot'] = detail['short_comment']['content']

    # 地区
    if not nfo.get('country') and detail.get('region'):
        nfo['country'] = detail['region']

    # 时长
    if not nfo.get('runtime') and detail.get('duration'):
        nfo['runtime'] = detail['duration']

    # 集数
    if not nfo.get('episodes') and detail.get('episodes_count'):
        nfo['episodes'] = detail['episodes_count']

    # 年份
    if (not item.get('year') or item.get('year') == 0) and detail.get('release_year'):
        try:
            item['year'] = int(detail['release_year'])
        except:
            pass

    # 豆瓣ID
    if not nfo.get('doubanid') and detail.get('id'):
        nfo['doubanid'] = str(detail['id'])

    # 在线海报（subject_suggest 返回的 img 字段是海报URL）
    if best.get('cover') and not item.get('poster'):
        nfo['online_poster'] = best['cover']

    return True


def load_js_var_for_scan(filepath):
    """加载 JS var 数据文件（仅用于扫描，不用于写入）"""
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
        print('  [豆瓣] 加载失败 %s: %s' % (filepath, e))
        return None


def write_overlay_entry(overlay, item, nfo_data):
    """将增强数据写入 overlay（by_imdbid 和 by_title_year）"""
    # 构建 overlay entry
    existing_entry = None
    imdbid = nfo_data.get('imdbid', '')
    
    # 先检查 overlay 中是否已有该条目
    if imdbid and imdbid in overlay.get('by_imdbid', {}):
        existing_entry = overlay['by_imdbid'][imdbid]
    else:
        title = item.get('title', '')
        year = item.get('year', 0)
        key = '%s|%s' % (title, year)
        if key in overlay.get('by_title_year', {}):
            existing_entry = overlay['by_title_year'][key]
    
    # 合并：已有 entry 则增量更新 nfo，否则新建
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


def enhance_category(data_var_name, cat_type='tv'):
    """增强一个分类的所有数据，结果写入 scrape_overlay.json"""
    filepath = os.path.join(DATA_DIR, data_var_name.lower().replace('_', '-') + '.js')
    if not os.path.exists(filepath):
        print('  文件不存在: %s' % filepath)
        return

    print('=' * 60)
    print('  豆瓣增强: %s (%s)' % (data_var_name, cat_type))
    print('=' * 60)

    data = load_js_var_for_scan(filepath)
    if not data:
        print('  加载数据失败')
        return

    # 加载已有 overlay
    overlay = load_overlay()

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
    print('  overlay 现有: imdbid=%d, title_year=%d' % (
        len(overlay.get('by_imdbid', {})), len(overlay.get('by_title_year', {}))))
    print()

    if need_enhance == 0:
        print('  所有条目元数据已完整，跳过')
        return

    counter = 0
    for series_name, series in data.items():
        items = series.get('movies', series.get('shows', []))
        for item in items:
            if not needs_enhancement(item):
                continue

            counter += 1
            title = item.get('title', series_name)
            display = title[:40]
            print('  [%d/%d] %s' % (counter, need_enhance, display), end='', flush=True)

            success = enhance_with_douban(item, cat_type)
            if success:
                enhanced += 1
                rating = item.get('nfo', {}).get('rating', '')
                print(' -> OK (豆瓣%s)' % rating)

                # 写入 overlay
                nfo_data = item.get('nfo', {})
                write_overlay_entry(overlay, item, nfo_data)
            else:
                failed += 1
                print(' -> MISS')

            time.sleep(REQUEST_DELAY)

            # 测试模式限制
            if '_TEST_LIMIT' in globals() and _TEST_LIMIT > 0 and counter >= _TEST_LIMIT:
                break

            # 每30个保存一次 overlay
            if counter % 30 == 0:
                save_overlay(overlay)
                print('  --- 中途保存 ---')

    # 最终保存 overlay
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
    print('  尚唯云影 豆瓣元数据增强')
    print('  数据源: 豆瓣电影 (douban.com)')
    print('  无需API Key，中文匹配精准')
    print('*' * 60)
    print()

    cats = []
    if args.cat:
        cat_map = {'tv': ('TV_DATA', 'tv'), 'anime': ('ANIME_DATA', 'tv'), 'doc': ('DOC_DATA', 'tv'), 'movie': ('MOVIE_DATA', 'movie')}
        cats = [cat_map[args.cat]]
    else:
        cats = [('TV_DATA', 'tv'), ('ANIME_DATA', 'tv'), ('DOC_DATA', 'tv'), ('MOVIE_DATA', 'movie')]

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
