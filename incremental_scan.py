#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""尚唯云册 - 增量扫描工具
只扫描自上次扫描以来新增或修改的文件
"""

import os
import sys
import json
import hashlib
from datetime import datetime
from pathlib import Path

# 导入智能解析器
try:
    from photo_parser import PhotoNameParser
except ImportError:
    print("警告: photo_parser.py 未找到，使用基础解析")
    PhotoNameParser = None

# ============ 配置 ============
PHOTO_ROOT = r'G:\照片'
PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUT_DIR = os.path.join(PROJECT_DIR, 'data')
STATE_FILE = os.path.join(PROJECT_DIR, '.scan_state.json')
INCREMENTAL_FILE = os.path.join(PROJECT_DIR, '.incremental_cache.json')

# 图片扩展名
IMAGE_EXTS = {'.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp', '.tif', '.tiff'}


class IncrementalScanner:
    """增量扫描器"""
    
    def __init__(self):
        self.state = self._load_state()
        self.parser = PhotoNameParser() if PhotoNameParser else None
        self.new_files = []
        self.modified_files = []
        self.deleted_files = []
    
    def _load_state(self) -> dict:
        """加载上次扫描状态"""
        if not os.path.exists(STATE_FILE):
            return {
                'last_scan': None,
                'file_count': 0,
                'files': {}
            }
        
        try:
            with open(STATE_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            print(f"加载状态失败: {e}")
            return {'last_scan': None, 'file_count': 0, 'files': {}}
    
    def _save_state(self):
        """保存当前扫描状态"""
        state = {
            'last_scan': datetime.now().isoformat(),
            'file_count': len(self.state['files']),
            'files': self.state['files']
        }
        
        try:
            with open(STATE_FILE, 'w', encoding='utf-8') as f:
                json.dump(state, f, ensure_ascii=False, indent=2)
            print(f"✓ 状态已保存: {len(state['files'])} 个文件")
        except Exception as e:
            print(f"保存状态失败: {e}")
    
    def _get_file_hash(self, filepath: str) -> str:
        """计算文件哈希（用于检测修改）"""
        try:
            stat = os.stat(filepath)
            key = f"{filepath}:{stat.st_size}:{stat.st_mtime}"
            return hashlib.md5(key.encode()).hexdigest()
        except Exception:
            return ''
    
    def scan_directory(self, dir_path: str) -> dict:
        """扫描单个目录，返回文件信息"""
        files = {}
        
        try:
            for entry in os.scandir(dir_path):
                if entry.is_file():
                    ext = os.path.splitext(entry.name)[1].lower()
                    if ext in IMAGE_EXTS:
                        try:
                            stat = entry.stat()
                            files[entry.path] = {
                                'name': entry.name,
                                'size': stat.st_size,
                                'mtime': stat.st_mtime,
                                'hash': self._get_file_hash(entry.path)
                            }
                        except Exception:
                            pass
                elif entry.is_dir():
                    # 递归扫描子目录
                    sub_files = self.scan_directory(entry.path)
                    files.update(sub_files)
        except PermissionError:
            pass
        
        return files
    
    def scan_all(self):
        """执行完整扫描"""
        print("=" * 60)
        print("尚唯云册 - 增量扫描工具")
        print("=" * 60)
        print(f"扫描目录: {PHOTO_ROOT}")
        print()
        
        # 检查上次扫描时间
        if self.state['last_scan']:
            print(f"上次扫描: {self.state['last_scan']}")
            print(f"上次文件数: {self.state['file_count']}")
            print()
        else:
            print("首次扫描")
            print()
        
        # 扫描当前文件
        print("扫描当前文件...")
        current_files = self.scan_directory(PHOTO_ROOT)
        print(f"当前文件数: {len(current_files)}")
        print()
        
        # 比较差异
        print("比较差异...")
        old_files = self.state['files']
        
        # 新增文件
        for path in current_files:
            if path not in old_files:
                self.new_files.append(path)
            elif current_files[path]['hash'] != old_files[path]['hash']:
                self.modified_files.append(path)
        
        # 删除文件
        for path in old_files:
            if path not in current_files:
                self.deleted_files.append(path)
        
        # 输出统计
        print(f"新增文件: {len(self.new_files)}")
        print(f"修改文件: {len(self.modified_files)}")
        print(f"删除文件: {len(self.deleted_files)}")
        print()
        
        # 更新状态
        self.state['files'] = current_files
        self._save_state()
        
        return len(self.new_files) + len(self.modified_files) > 0
    
    def parse_new_files(self):
        """解析新增文件的元数据"""
        if not self.parser:
            print("跳过解析（解析器不可用）")
            return
        
        if not self.new_files and not self.modified_files:
            print("没有需要解析的文件")
            return
        
        print("解析文件元数据...")
        
        results = []
        files_to_parse = self.new_files + self.modified_files
        
        for filepath in files_to_parse[:100]:  # 最多解析100个
            filename = os.path.basename(filepath)
            parsed = self.parser.parse_filename(filename)
            parsed['filepath'] = filepath
            parsed['size'] = os.path.getsize(filepath)
            results.append(parsed)
        
        # 保存增量数据
        try:
            with open(INCREMENTAL_FILE, 'w', encoding='utf-8') as f:
                json.dump({
                    'scan_time': datetime.now().isoformat(),
                    'new_count': len(self.new_files),
                    'modified_count': len(self.modified_files),
                    'parsed': results
                }, f, ensure_ascii=False, indent=2)
            
            print(f"✓ 已解析 {len(results)} 个文件")
            print(f"✓ 增量数据已保存: {INCREMENTAL_FILE}")
        except Exception as e:
            print(f"保存增量数据失败: {e}")
    
    def generate_report(self):
        """生成扫描报告"""
        print()
        print("=" * 60)
        print("扫描报告")
        print("=" * 60)
        print(f"新增文件: {len(self.new_files)}")
        print(f"修改文件: {len(self.modified_files)}")
        print(f"删除文件: {len(self.deleted_files)}")
        print()
        
        if self.new_files:
            print("新增文件示例:")
            for f in self.new_files[:5]:
                print(f"  + {os.path.basename(f)}")
            if len(self.new_files) > 5:
                print(f"  ... 还有 {len(self.new_files) - 5} 个")
            print()
        
        if self.modified_files:
            print("修改文件示例:")
            for f in self.modified_files[:5]:
                print(f"  ~ {os.path.basename(f)}")
            if len(self.modified_files) > 5:
                print(f"  ... 还有 {len(self.modified_files) - 5} 个")
            print()
        
        print("=" * 60)


def main():
    scanner = IncrementalScanner()
    
    # 执行扫描
    has_changes = scanner.scan_all()
    
    # 解析新增文件
    if has_changes:
        scanner.parse_new_files()
    
    # 生成报告
    scanner.generate_report()
    
    # 返回退出码
    return 0 if not has_changes else 1


if __name__ == '__main__':
    sys.exit(main())
