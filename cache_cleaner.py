#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""尚唯云册 - 缓存自动清理工具
定期清理超过30天未访问的缩略图缓存
"""

import os
import sys
import time
import hashlib
from datetime import datetime, timedelta
from pathlib import Path


# 配置
CACHE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'cache')
DEFAULT_MAX_AGE_DAYS = 30
DEFAULT_MIN_KEEP = 100  # 至少保留的文件数


class CacheCleaner:
    """缓存清理器"""
    
    def __init__(self, cache_dir: str = CACHE_DIR):
        self.cache_dir = cache_dir
        self.stats = {
            'total_files': 0,
            'deleted_files': 0,
            'freed_space': 0,
            'errors': 0
        }
    
    def get_cache_files(self) -> list:
        """获取所有缓存文件"""
        if not os.path.exists(self.cache_dir):
            return []
        
        files = []
        for entry in os.scandir(self.cache_dir):
            if entry.is_file() and entry.name.endswith('.jpg'):
                try:
                    stat = entry.stat()
                    files.append({
                        'path': entry.path,
                        'name': entry.name,
                        'size': stat.st_size,
                        'mtime': stat.st_mtime,
                        'atime': stat.st_atime
                    })
                except Exception:
                    pass
        
        return files
    
    def cleanup(self, max_age_days: int = DEFAULT_MAX_AGE_DAYS, 
                min_keep: int = DEFAULT_MIN_KEEP) -> dict:
        """
        清理过期缓存
        
        Args:
            max_age_days: 最大保留天数
            min_keep: 至少保留的文件数（防止误删）
        
        Returns:
            清理统计信息
        """
        print("=" * 60)
        print("尚唯云册 - 缓存清理工具")
        print("=" * 60)
        print(f"缓存目录: {self.cache_dir}")
        print(f"保留天数: {max_age_days}")
        print(f"最少保留: {min_keep}")
        print()
        
        # 获取所有文件
        files = self.get_cache_files()
        self.stats['total_files'] = len(files)
        
        if not files:
            print("没有缓存文件")
            return self.stats
        
        print(f"缓存文件数: {len(files)}")
        
        # 计算过期时间
        cutoff_time = time.time() - (max_age_days * 86400)
        
        # 按访问时间排序（最老的在前）
        files.sort(key=lambda x: x['atime'])
        
        # 找出过期文件
        expired_files = [f for f in files if f['atime'] < cutoff_time]
        
        # 保留最少文件数
        if len(files) - len(expired_files) < min_keep:
            keep_count = max(0, len(files) - min_keep)
            expired_files = expired_files[-keep_count:] if keep_count > 0 else []
        
        print(f"过期文件数: {len(expired_files)}")
        print()
        
        if not expired_files:
            print("没有需要清理的文件")
            return self.stats
        
        # 删除过期文件
        print("清理过期文件...")
        for file in expired_files:
            try:
                os.remove(file['path'])
                self.stats['deleted_files'] += 1
                self.stats['freed_space'] += file['size']
            except Exception as e:
                self.stats['errors'] += 1
        
        # 输出统计
        print(f"✓ 删除文件: {self.stats['deleted_files']}")
        print(f"✓ 释放空间: {self._format_size(self.stats['freed_space'])}")
        print(f"✓ 错误数: {self.stats['errors']}")
        print()
        print("=" * 60)
        
        return self.stats
    
    def preview(self, max_age_days: int = DEFAULT_MAX_AGE_DAYS) -> dict:
        """预览将要删除的文件（不实际删除）"""
        files = self.get_cache_files()
        cutoff_time = time.time() - (max_age_days * 86400)
        
        expired = [f for f in files if f['atime'] < cutoff_time]
        
        total_size = sum(f['size'] for f in expired)
        
        return {
            'expired_count': len(expired),
            'expired_size': total_size,
            'expired_size_str': self._format_size(total_size),
            'oldest_file': expired[0] if expired else None,
            'newest_expired': expired[-1] if expired else None
        }
    
    def _format_size(self, size_bytes: int) -> str:
        """格式化文件大小"""
        if size_bytes < 1024:
            return f"{size_bytes} B"
        elif size_bytes < 1024 * 1024:
            return f"{size_bytes / 1024:.1f} KB"
        elif size_bytes < 1024 * 1024 * 1024:
            return f"{size_bytes / (1024 * 1024):.1f} MB"
        else:
            return f"{size_bytes / (1024 * 1024 * 1024):.2f} GB"


def main():
    """主函数"""
    import argparse
    
    parser = argparse.ArgumentParser(description='缓存清理工具')
    parser.add_argument('--days', type=int, default=30, help='保留天数（默认30）')
    parser.add_argument('--min-keep', type=int, default=100, help='最少保留文件数（默认100）')
    parser.add_argument('--preview', action='store_true', help='仅预览，不删除')
    parser.add_argument('--cache-dir', type=str, default=CACHE_DIR, help='缓存目录')
    
    args = parser.parse_args()
    
    cleaner = CacheCleaner(args.cache_dir)
    
    if args.preview:
        # 预览模式
        preview = cleaner.preview(args.days)
        print("=" * 60)
        print("缓存清理预览")
        print("=" * 60)
        print(f"过期文件数: {preview['expired_count']}")
        print(f"将释放空间: {preview['expired_size_str']}")
        
        if preview['oldest_file']:
            print(f"最老文件: {preview['oldest_file']['name']}")
            print(f"  访问时间: {datetime.fromtimestamp(preview['oldest_file']['atime'])}")
        
        print()
        print("提示: 使用 --days 参数调整保留天数")
        print("=" * 60)
    else:
        # 执行清理
        stats = cleaner.cleanup(args.days, args.min_keep)
        
        # 返回退出码
        return 0 if stats['errors'] == 0 else 1


if __name__ == '__main__':
    sys.exit(main())
