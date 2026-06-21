#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""尚唯云册 - 搜索引擎
支持按日期、人物、事件、地点等多维度搜索
"""

import os
import re
import json
from datetime import datetime
from typing import List, Dict, Optional
from pathlib import Path

# 导入智能解析器
try:
    from photo_parser import PhotoNameParser
except ImportError:
    PhotoNameParser = None


class SearchEngine:
    """搜索引擎"""
    
    def __init__(self, data_dir: str = None):
        self.data_dir = data_dir or os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data')
        self.parser = PhotoNameParser() if PhotoNameParser else None
        self.index = []
        self.filters = {
            'date': None,
            'year': None,
            'month': None,
            'person': None,
            'event': None,
            'location': None,
            'ownership': None,
            'keyword': None
        }
    
    def build_index(self) -> int:
        """
        构建搜索索引
        
        返回：索引文件数量
        """
        if not self.parser:
            print("错误: 解析器不可用")
            return 0
        
        print("构建搜索索引...")
        
        # 扫描照片目录
        photo_root = r'G:\照片'
        if not os.path.exists(photo_root):
            print(f"警告: 照片目录不存在 {photo_root}")
            return 0
        
        indexed = 0
        
        for root, dirs, files in os.walk(photo_root):
            for filename in files:
                filepath = os.path.join(root, filename)
                
                # 只处理图片
                ext = os.path.splitext(filename)[1].lower()
                if ext not in {'.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp'}:
                    continue
                
                # 解析文件名
                parsed = self.parser.parse_filename(filename)
                
                # 添加额外信息
                parsed['filepath'] = filepath
                parsed['relative_path'] = os.path.relpath(filepath, photo_root)
                parsed['size'] = os.path.getsize(filepath)
                
                # 从目录名提取额外信息
                dir_name = os.path.basename(root)
                parsed['directory'] = dir_name
                
                # 添加到索引
                self.index.append(parsed)
                indexed += 1
        
        print(f"✓ 索引完成: {indexed} 个文件")
        
        # 保存索引
        self._save_index()
        
        return indexed
    
    def _save_index(self):
        """保存索引到文件"""
        index_file = os.path.join(self.data_dir, 'search_index.json')
        
        try:
            os.makedirs(self.data_dir, exist_ok=True)
            
            with open(index_file, 'w', encoding='utf-8') as f:
                json.dump({
                    'build_time': datetime.now().isoformat(),
                    'count': len(self.index),
                    'index': self.index
                }, f, ensure_ascii=False, indent=2)
            
            print(f"✓ 索引已保存: {index_file}")
        except Exception as e:
            print(f"保存索引失败: {e}")
    
    def load_index(self) -> bool:
        """加载索引"""
        index_file = os.path.join(self.data_dir, 'search_index.json')
        
        if not os.path.exists(index_file):
            return False
        
        try:
            with open(index_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                self.index = data.get('index', [])
                print(f"✓ 加载索引: {len(self.index)} 个文件")
                return True
        except Exception as e:
            print(f"加载索引失败: {e}")
            return False
    
    def search(self, **filters) -> List[Dict]:
        """
        执行搜索
        
        支持的过滤条件：
            - date: 日期范围 (start, end)
            - year: 年份
            - month: 月份
            - person: 人物
            - event: 事件类型
            - location: 地点
            - ownership: 归属 (R/S/S&R)
            - keyword: 关键词
        
        返回：匹配的文件列表
        """
        if not self.index:
            if not self.load_index():
                self.build_index()
        
        results = []
        
        for item in self.index:
            if self._match_filters(item, filters):
                results.append(item)
        
        return results
    
    def _match_filters(self, item: Dict, filters: Dict) -> bool:
        """检查是否匹配过滤条件"""
        # 日期范围
        if 'date' in filters and filters['date']:
            start, end = filters['date']
            item_date = item.get('date')
            if item_date:
                if start and item_date < start:
                    return False
                if end and item_date > end:
                    return False
        
        # 年份
        if 'year' in filters and filters['year']:
            if item.get('year') != filters['year']:
                return False
        
        # 月份
        if 'month' in filters and filters['month']:
            if item.get('month') != filters['month']:
                return False
        
        # 人物
        if 'person' in filters and filters['person']:
            persons = item.get('persons', [])
            description = item.get('description', '')
            if filters['person'] not in persons and filters['person'] not in description:
                return False
        
        # 事件
        if 'event' in filters and filters['event']:
            if item.get('event') != filters['event']:
                return False
        
        # 地点
        if 'location' in filters and filters['location']:
            location = item.get('location', '')
            if filters['location'] not in location:
                return False
        
        # 归属
        if 'ownership' in filters and filters['ownership']:
            if item.get('ownership') != filters['ownership']:
                return False
        
        # 关键词
        if 'keyword' in filters and filters['keyword']:
            keyword = filters['keyword'].lower()
            
            # 搜索多个字段
            search_fields = [
                item.get('filename', ''),
                item.get('description', ''),
                item.get('location', ''),
                item.get('directory', ''),
                ' '.join(item.get('persons', []))
            ]
            
            if not any(keyword in field.lower() for field in search_fields if field):
                return False
        
        return True
    
    def get_statistics(self) -> Dict:
        """获取索引统计信息"""
        if not self.index:
            self.load_index()
        
        stats = {
            'total': len(self.index),
            'by_year': {},
            'by_event': {},
            'by_location': {},
            'by_ownership': {}
        }
        
        for item in self.index:
            # 按年份
            year = item.get('year')
            if year:
                stats['by_year'][year] = stats['by_year'].get(year, 0) + 1
            
            # 按事件
            event = item.get('event')
            if event:
                stats['by_event'][event] = stats['by_event'].get(event, 0) + 1
            
            # 按地点
            location = item.get('location')
            if location:
                stats['by_location'][location] = stats['by_location'].get(location, 0) + 1
            
            # 按归属
            ownership = item.get('ownership')
            if ownership:
                stats['by_ownership'][ownership] = stats['by_ownership'].get(ownership, 0) + 1
        
        return stats


# 命令行接口
if __name__ == '__main__':
    import argparse
    
    parser = argparse.ArgumentParser(description='照片搜索引擎')
    parser.add_argument('--build', action='store_true', help='构建索引')
    parser.add_argument('--search', type=str, help='搜索关键词')
    parser.add_argument('--year', type=int, help='按年份搜索')
    parser.add_argument('--event', type=str, help='按事件搜索')
    parser.add_argument('--person', type=str, help='按人物搜索')
    parser.add_argument('--location', type=str, help='按地点搜索')
    parser.add_argument('--stats', action='store_true', help='显示统计信息')
    
    args = parser.parse_args()
    
    engine = SearchEngine()
    
    if args.build:
        # 构建索引
        count = engine.build_index()
        print(f"索引构建完成: {count} 个文件")
    
    elif args.search or args.year or args.event or args.person or args.location:
        # 执行搜索
        filters = {}
        
        if args.search:
            filters['keyword'] = args.search
        if args.year:
            filters['year'] = args.year
        if args.event:
            filters['event'] = args.event
        if args.person:
            filters['person'] = args.person
        if args.location:
            filters['location'] = args.location
        
        results = engine.search(**filters)
        
        print("=" * 60)
        print(f"搜索结果: {len(results)} 个文件")
        print("=" * 60)
        
        for item in results[:10]:
            print(f"\n文件名: {item.get('filename')}")
            print(f"  日期: {item.get('date')}")
            print(f"  事件: {item.get('event')}")
            print(f"  地点: {item.get('location')}")
        
        if len(results) > 10:
            print(f"\n... 还有 {len(results) - 10} 个结果")
    
    elif args.stats:
        # 显示统计
        stats = engine.get_statistics()
        
        print("=" * 60)
        print("索引统计")
        print("=" * 60)
        print(f"总文件数: {stats['total']}")
        print()
        
        print("按年份:")
        for year, count in sorted(stats['by_year'].items()):
            print(f"  {year}: {count}")
        
        print("\n按事件:")
        for event, count in sorted(stats['by_event'].items(), key=lambda x: -x[1])[:10]:
            print(f"  {event}: {count}")
        
        print("\n按地点:")
        for location, count in sorted(stats['by_location'].items(), key=lambda x: -x[1])[:10]:
            print(f"  {location}: {count}")
        
        print("\n按归属:")
        for ownership, count in sorted(stats['by_ownership'].items()):
            print(f"  {ownership}: {count}")
        
        print("=" * 60)
    
    else:
        # 显示帮助
        parser.print_help()
