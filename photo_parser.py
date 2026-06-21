#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""尚唯云册 - 智能命名解析引擎
解析照片文件名，提取归属、日期、事件、人物、地点等信息
"""

import re
import os
from datetime import datetime
from typing import Dict, Optional, List


class PhotoNameParser:
    """照片文件名解析器"""
    
    # 归属编码映射
    OWNERSHIP_MAP = {
        'R': 'Roger',
        'S': 'Seth',
        'S&R': '夫妻共同',
        'R&S': '夫妻共同',
    }
    
    # 事件类型标准化
    EVENT_NORMALIZE = {
        '生活照': '生活照',
        '游玩': '游玩',
        '聚会': '聚会',
        '参加婚礼': '参加婚礼',
        '结婚典礼': '结婚典礼',
        '结婚照': '结婚照',
        '工作照': '工作照',
        '艺术照': '艺术照',
        '集体照': '集体照',
        '旅游结婚': '旅游结婚',
        '四毛': '四毛',
    }
    
    # 日期正则：YYYYMMDD、YYYYMM00、YYYY0000
    DATE_PATTERN = re.compile(r'^(\d{4})(\d{2})?(\d{2})?')
    
    # 文件名解析正则
    # 格式：[归属]-[日期]-[事件]-[描述]-[地点]
    FILENAME_PATTERN = re.compile(
        r'^(?P<ownership>[RS](?:&[RS])?)?'
        r'-(?P<date>\d{8})?'
        r'-(?P<event>[^-]+)?'
        r'-(?P<rest>.+)?$'
    )
    
    def __init__(self):
        self.location_cache = {}  # 地点缓存
        self.person_cache = {}    # 人物缓存
    
    def parse_filename(self, filename: str) -> Dict:
        """
        解析照片文件名
        
        示例：
            R-19940503-游玩-20岁生日-沈阳北陵公园
            S&R-19990403-结婚典礼-沈阳湘珍水鱼城
            S-19940102-聚会-105高中同学-沈阳松园酒家
        
        返回：
            {
                'ownership': 'R',
                'ownership_name': 'Roger',
                'date': '1994-05-03',
                'date_raw': '19940503',
                'year': 1994,
                'month': 5,
                'day': 3,
                'event': '游玩',
                'description': '20岁生日',
                'location': '沈阳北陵公园',
                'tags': ['游玩', '生日', '沈阳', '北陵公园']
            }
        """
        # 去除扩展名
        name = os.path.splitext(filename)[0]
        
        result = {
            'filename': filename,
            'ownership': None,
            'ownership_name': None,
            'date': None,
            'date_raw': None,
            'year': None,
            'month': None,
            'day': None,
            'event': None,
            'description': None,
            'location': None,
            'persons': [],
            'tags': [],
        }
        
        # 尝试匹配标准格式
        match = self.FILENAME_PATTERN.match(name)
        if not match:
            # 尝试其他格式
            return self._parse_legacy(name, result)
        
        # 提取归属
        ownership = match.group('ownership')
        if ownership:
            result['ownership'] = ownership
            result['ownership_name'] = self.OWNERSHIP_MAP.get(ownership, ownership)
        
        # 提取日期
        date_str = match.group('date')
        if date_str:
            result['date_raw'] = date_str
            date_info = self._parse_date(date_str)
            result.update(date_info)
        
        # 提取事件
        event = match.group('event')
        if event:
            result['event'] = self._normalize_event(event)
            result['tags'].append(result['event'])
        
        # 提取剩余部分（描述+地点）
        rest = match.group('rest')
        if rest:
            self._parse_rest(rest, result)
        
        return result
    
    def _parse_date(self, date_str: str) -> Dict:
        """解析日期字符串"""
        result = {'date': None, 'year': None, 'month': None, 'day': None}
        
        if not date_str or date_str == '00000000':
            return result
        
        match = self.DATE_PATTERN.match(date_str)
        if not match:
            return result
        
        year = int(match.group(1))
        month = int(match.group(2)) if match.group(2) else None
        day = int(match.group(3)) if match.group(3) else None
        
        # 验证日期范围
        if year < 1900 or year > 2100:
            return result
        
        result['year'] = year
        
        if month and 1 <= month <= 12:
            result['month'] = month
        
        if day and 1 <= day <= 31:
            result['day'] = day
        
        # 格式化日期
        if month and day:
            result['date'] = f"{year:04d}-{month:02d}-{day:02d}"
        elif month:
            result['date'] = f"{year:04d}-{month:02d}"
        else:
            result['date'] = f"{year:04d}"
        
        return result
    
    def _normalize_event(self, event: str) -> str:
        """标准化事件类型"""
        event = event.strip()
        
        # 直接匹配
        if event in self.EVENT_NORMALIZE:
            return self.EVENT_NORMALIZE[event]
        
        # 模糊匹配
        for key, value in self.EVENT_NORMALIZE.items():
            if key in event:
                return value
        
        return event
    
    def _parse_rest(self, rest: str, result: Dict):
        """解析剩余部分（描述+地点）"""
        parts = rest.split('-')
        
        if not parts:
            return
        
        # 尝试识别地点（通常在最后）
        location_keywords = ['沈阳', '北京', '上海', '广州', '深圳', '香港', '海南', 
                           '公园', '小区', '家', '酒店', '大厦', '广场', '山', '海']
        
        for i, part in enumerate(reversed(parts)):
            if any(kw in part for kw in location_keywords):
                result['location'] = part
                result['tags'].append(part)
                # 剩余部分作为描述
                result['description'] = '-'.join(parts[:-i-1]) if i > 0 else None
                break
        else:
            # 没有明确地点，全部作为描述
            result['description'] = rest
        
        # 提取人物（如果有 / 分隔）
        if result['description']:
            persons = re.split(r'[/、]', result['description'])
            if len(persons) > 1:
                result['persons'] = [p.strip() for p in persons if p.strip()]
                result['tags'].extend(result['persons'])
    
    def _parse_legacy(self, name: str, result: Dict) -> Dict:
        """解析旧格式文件名"""
        # 尝试提取日期
        date_match = re.search(r'(\d{8})', name)
        if date_match:
            date_info = self._parse_date(date_match.group(1))
            result.update(date_info)
        
        # 尝试提取归属
        if name.startswith('R-') or name.startswith('S&R-') or name.startswith('R&S-'):
            result['ownership'] = name.split('-')[0]
            result['ownership_name'] = self.OWNERSHIP_MAP.get(result['ownership'], result['ownership'])
        
        return result
    
    def parse_directory(self, dir_path: str) -> List[Dict]:
        """批量解析目录下的所有照片"""
        results = []
        
        for filename in os.listdir(dir_path):
            filepath = os.path.join(dir_path, filename)
            if not os.path.isfile(filepath):
                continue
            
            # 只处理图片文件
            ext = os.path.splitext(filename)[1].lower()
            if ext not in {'.jpg', '.jpeg', '.png', '.gif', '.webp', '.bmp'}:
                continue
            
            parsed = self.parse_filename(filename)
            parsed['filepath'] = filepath
            results.append(parsed)
        
        return results
    
    def generate_tags(self, parsed: Dict) -> List[str]:
        """生成标签列表"""
        tags = []
        
        # 事件标签
        if parsed.get('event'):
            tags.append(parsed['event'])
        
        # 地点标签
        if parsed.get('location'):
            tags.append(parsed['location'])
            # 提取城市
            for city in ['沈阳', '北京', '上海', '深圳', '香港', '海南']:
                if city in parsed['location']:
                    tags.append(city)
        
        # 人物标签
        if parsed.get('persons'):
            tags.extend(parsed['persons'])
        
        # 时间标签
        if parsed.get('year'):
            tags.append(f"{parsed['year']}年")
        
        # 归属标签
        if parsed.get('ownership'):
            tags.append(parsed['ownership_name'])
        
        return list(set(tags))  # 去重


# 命令行接口
if __name__ == '__main__':
    parser = PhotoNameParser()
    
    # 测试用例
    test_cases = [
        'R-19940503-游玩-20岁生日-沈阳北陵公园.jpg',
        'S&R-19990403-结婚典礼-沈阳湘珍水鱼城.jpg',
        'S-19940102-聚会-105高中同学-沈阳松园酒家.jpg',
        'R-20250128-春节联欢晚会-宋大成-北京.jpg',
    ]
    
    print("=" * 60)
    print("照片命名解析器测试")
    print("=" * 60)
    
    for filename in test_cases:
        print(f"\n文件名: {filename}")
        parsed = parser.parse_filename(filename)
        for key, value in parsed.items():
            if value and key != 'filename':
                print(f"  {key}: {value}")
    
    print("\n" + "=" * 60)
