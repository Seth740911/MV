#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""尚唯云册 - 时间轴地图生成器
按时间顺序展示照片，支持年份筛选和滚动加载
"""

import os
import json
from datetime import datetime
from typing import List, Dict
from collections import defaultdict

# 导入搜索引擎
try:
    from search_engine import SearchEngine
except ImportError:
    SearchEngine = None


class TimelineGenerator:
    """时间轴生成器"""
    
    def __init__(self):
        self.engine = SearchEngine() if SearchEngine else None
        self.timeline_data = {}
    
    def generate(self, year: int = None) -> Dict:
        """
        生成时间轴数据
        
        Args:
            year: 指定年份，None 表示所有年份
        
        Returns:
            {
                'years': [1994, 1995, ...],
                'timeline': {
                    '1994': {
                        '01': [...],  # 1月
                        '02': [...],  # 2月
                        ...
                    },
                    ...
                },
                'stats': {
                    'total': 1000,
                    'by_year': {...}
                }
            }
        """
        if not self.engine:
            print("错误: 搜索引擎不可用")
            return {}
        
        # 加载索引
        if not self.engine.index:
            self.engine.load_index()
        
        # 按年份和月份分组
        timeline = defaultdict(lambda: defaultdict(list))
        years = set()
        
        for item in self.engine.index:
            item_year = item.get('year')
            item_month = item.get('month')
            
            if not item_year or not item_month:
                continue
            
            # 如果指定年份，只处理该年份
            if year and item_year != year:
                continue
            
            years.add(item_year)
            
            # 添加月份信息
            month_str = f"{item_month:02d}"
            
            timeline[item_year][month_str].append({
                'filename': item.get('filename'),
                'date': item.get('date'),
                'event': item.get('event'),
                'location': item.get('location'),
                'persons': item.get('persons', []),
                'ownership': item.get('ownership'),
                'filepath': item.get('filepath')
            })
        
        # 排序年份
        sorted_years = sorted(years)
        
        # 生成统计
        stats = {
            'total': sum(
                len(months) 
                for year_data in timeline.values() 
                for months in year_data.values()
            ),
            'by_year': {
                year: sum(len(months) for months in months_data.values())
                for year, months_data in timeline.items()
            }
        }
        
        return {
            'years': sorted_years,
            'timeline': dict(timeline),
            'stats': stats
        }
    
    def save_timeline(self, output_dir: str = None):
        """保存时间轴数据到文件"""
        if not output_dir:
            output_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data')
        
        os.makedirs(output_dir, exist_ok=True)
        
        # 生成完整时间轴
        timeline_data = self.generate()
        
        # 保存到文件
        output_file = os.path.join(output_dir, 'timeline.json')
        
        try:
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump({
                    'generated_at': datetime.now().isoformat(),
                    'data': timeline_data
                }, f, ensure_ascii=False, indent=2)
            
            print(f"✓ 时间轴已保存: {output_file}")
            print(f"✓ 年份范围: {timeline_data['years'][0]} - {timeline_data['years'][-1]}")
            print(f"✓ 总照片数: {timeline_data['stats']['total']}")
            
            return output_file
        
        except Exception as e:
            print(f"保存时间轴失败: {e}")
            return None
    
    def generate_html_snippet(self, year: int = None) -> str:
        """生成时间轴 HTML 片段（供前端使用）"""
        timeline_data = self.generate(year)
        
        if not timeline_data:
            return '<div class="timeline-empty">暂无数据</div>'
        
        html_parts = ['<div class="timeline-container">']
        
        # 年份导航
        html_parts.append('<div class="timeline-years">')
        for y in timeline_data['years']:
            count = timeline_data['stats']['by_year'].get(y, 0)
            active = 'active' if y == year else ''
            html_parts.append(
                f'<button class="year-btn {active}" data-year="{y}">'
                f'{y}年 <span class="count">({count})</span>'
                f'</button>'
            )
        html_parts.append('</div>')
        
        # 时间轴内容
        html_parts.append('<div class="timeline-content">')
        
        for y in sorted(timeline_data['timeline'].keys(), reverse=True):
            year_data = timeline_data['timeline'][y]
            
            html_parts.append(f'<div class="year-section" data-year="{y}">')
            html_parts.append(f'<h2 class="year-title">{y}年</h2>')
            
            for month in sorted(year_data.keys()):
                month_photos = year_data[month]
                
                html_parts.append(f'<div class="month-section">')
                html_parts.append(f'<h3 class="month-title">{int(month)}月</h3>')
                html_parts.append('<div class="photo-grid">')
                
                for photo in month_photos[:20]:  # 每月最多显示20张
                    event = photo.get('event', '')
                    location = photo.get('location', '')
                    date = photo.get('date', '')
                    
                    html_parts.append(
                        f'<div class="photo-item" data-date="{date}">'
                        f'<img data-src="{photo["filepath"]}" alt="{photo["filename"]}">'
                        f'<div class="photo-info">'
                        f'<span class="event">{event}</span>'
                        f'<span class="location">{location}</span>'
                        f'</div>'
                        f'</div>'
                    )
                
                html_parts.append('</div></div>')
            
            html_parts.append('</div>')
        
        html_parts.append('</div></div>')
        
        return '\n'.join(html_parts)


class PhotoMap:
    """照片地图（按地点分类）"""
    
    def __init__(self):
        self.engine = SearchEngine() if SearchEngine else None
    
    def generate_location_map(self) -> Dict:
        """
        按地点生成照片地图
        
        Returns:
            {
                'locations': {
                    '沈阳': {...},
                    '北京': {...},
                    ...
                }
            }
        """
        if not self.engine:
            return {}
        
        if not self.engine.index:
            self.engine.load_index()
        
        location_map = defaultdict(list)
        
        for item in self.engine.index:
            location = item.get('location')
            if location:
                location_map[location].append({
                    'filename': item.get('filename'),
                    'date': item.get('date'),
                    'event': item.get('event'),
                    'filepath': item.get('filepath')
                })
        
        return {
            'locations': dict(location_map),
            'stats': {
                'total_locations': len(location_map),
                'top_locations': sorted(
                    location_map.items(),
                    key=lambda x: len(x[1]),
                    reverse=True
                )[:20]
            }
        }


# 命令行接口
if __name__ == '__main__':
    import argparse
    
    parser = argparse.ArgumentParser(description='时间轴地图生成器')
    parser.add_argument('--timeline', action='store_true', help='生成时间轴')
    parser.add_argument('--year', type=int, help='指定年份')
    parser.add_argument('--map', action='store_true', help='生成地点地图')
    parser.add_argument('--output', type=str, default='data', help='输出目录')
    
    args = parser.parse_args()
    
    if args.timeline:
        # 生成时间轴
        generator = TimelineGenerator()
        generator.save_timeline(args.output)
    
    elif args.map:
        # 生成地点地图
        photo_map = PhotoMap()
        map_data = photo_map.generate_location_map()
        
        print("=" * 60)
        print("照片地图")
        print("=" * 60)
        print(f"地点总数: {map_data['stats']['total_locations']}")
        print()
        print("热门地点 (Top 20):")
        
        for location, photos in map_data['stats']['top_locations']:
            print(f"  {location}: {len(photos)} 张")
        
        print("=" * 60)
    
    else:
        parser.print_help()
