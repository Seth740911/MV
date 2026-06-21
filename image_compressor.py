#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""尚唯云册 - 图片压缩工具
批量压缩原图，生成多种尺寸
"""

import os
import sys
import hashlib
from pathlib import Path

try:
    from PIL import Image
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False
    print("警告: PIL 未安装，图片压缩功能不可用")
    print("安装命令: pip install Pillow")


# 配置
PHOTO_ROOT = r'G:\照片'
OUTPUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'compressed')

# 输出尺寸
SIZES = {
    'thumb': (300, 300),    # 缩略图
    'medium': (800, 800),   # 中等尺寸
    'large': (1920, 1920),  # 大图
}

# 压缩质量
QUALITY = {
    'thumb': 75,
    'medium': 80,
    'large': 85,
}

# 支持的格式
IMAGE_EXTS = {'.jpg', '.jpeg', '.png', '.webp'}


class ImageCompressor:
    """图片压缩器"""
    
    def __init__(self, photo_root: str = PHOTO_ROOT, output_dir: str = OUTPUT_DIR):
        self.photo_root = photo_root
        self.output_dir = output_dir
        self.stats = {
            'processed': 0,
            'skipped': 0,
            'errors': 0,
            'original_size': 0,
            'compressed_size': 0
        }
    
    def compress_image(self, input_path: str, output_path: str, 
                       size: tuple, quality: int = 80) -> bool:
        """压缩单张图片"""
        if not PIL_AVAILABLE:
            return False
        
        try:
            # 打开图片
            with Image.open(input_path) as img:
                # 保持原始方向（处理 EXIF 旋转）
                try:
                    from PIL import ImageOps
                    img = ImageOps.exif_transpose(img)
                except Exception:
                    pass
                
                # 转换为 RGB（如果需要）
                if img.mode in ('RGBA', 'P'):
                    img = img.convert('RGB')
                
                # 获取原始尺寸
                orig_w, orig_h = img.size
                
                # 计算缩放比例（保持宽高比）
                ratio = min(size[0] / orig_w, size[1] / orig_h)
                
                if ratio >= 1.0:
                    # 图片已经足够小，不需要缩放
                    new_size = (orig_w, orig_h)
                else:
                    new_size = (int(orig_w * ratio), int(orig_h * ratio))
                
                # 缩放
                img = img.resize(new_size, Image.Resampling.LANCZOS)
                
                # 保存
                img.save(output_path, 'JPEG', quality=quality, optimize=True)
                
                return True
        
        except Exception as e:
            print(f"压缩失败: {input_path} - {e}")
            return False
    
    def process_image(self, filepath: str, relative_path: str):
        """处理单张图片"""
        filename = os.path.basename(filepath)
        ext = os.path.splitext(filename)[1].lower()
        
        if ext not in IMAGE_EXTS:
            return
        
        # 计算输出路径
        base_name = os.path.splitext(filename)[0]
        hash_key = hashlib.md5(relative_path.encode()).hexdigest()[:8]
        
        for size_name, size in SIZES.items():
            output_filename = f"{base_name}_{size_name}_{hash_key}.jpg"
            output_path = os.path.join(self.output_dir, size_name, output_filename)
            
            # 检查是否已存在
            if os.path.exists(output_path):
                self.stats['skipped'] += 1
                continue
            
            # 创建目录
            os.makedirs(os.path.dirname(output_path), exist_ok=True)
            
            # 压缩
            quality = QUALITY[size_name]
            if self.compress_image(filepath, output_path, size, quality):
                self.stats['processed'] += 1
                
                # 统计大小
                try:
                    orig_size = os.path.getsize(filepath)
                    comp_size = os.path.getsize(output_path)
                    self.stats['original_size'] += orig_size
                    self.stats['compressed_size'] += comp_size
                except Exception:
                    pass
            else:
                self.stats['errors'] += 1
    
    def process_directory(self, dir_path: str):
        """处理目录下的所有图片"""
        print(f"处理目录: {dir_path}")
        
        for entry in os.scandir(dir_path):
            if entry.is_file():
                relative = os.path.relpath(entry.path, self.photo_root)
                self.process_image(entry.path, relative)
            
            elif entry.is_dir():
                self.process_directory(entry.path)
    
    def run(self, limit: int = 100):
        """
        运行压缩
        
        Args:
            limit: 最多处理的文件数（防止长时间运行）
        """
        if not PIL_AVAILABLE:
            print("错误: PIL 未安装，无法压缩图片")
            return
        
        print("=" * 60)
        print("尚唯云册 - 图片压缩工具")
        print("=" * 60)
        print(f"源目录: {self.photo_root}")
        print(f"输出目录: {self.output_dir}")
        print(f"限制数量: {limit}")
        print()
        
        # 创建输出目录
        for size_name in SIZES.keys():
            os.makedirs(os.path.join(self.output_dir, size_name), exist_ok=True)
        
        # 处理图片
        print("开始压缩...")
        processed = 0
        
        for entry in os.scandir(self.photo_root):
            if entry.is_file():
                ext = os.path.splitext(entry.name)[1].lower()
                if ext in IMAGE_EXTS:
                    self.process_image(entry.path, entry.name)
                    processed += 1
                    
                    if processed >= limit:
                        print(f"已达到限制 ({limit})，停止处理")
                        break
        
        # 输出统计
        print()
        print("=" * 60)
        print("压缩统计")
        print("=" * 60)
        print(f"已处理: {self.stats['processed']}")
        print(f"已跳过: {self.stats['skipped']}")
        print(f"错误数: {self.stats['errors']}")
        
        if self.stats['original_size'] > 0:
            ratio = (1 - self.stats['compressed_size'] / self.stats['original_size']) * 100
            print(f"原始大小: {self._format_size(self.stats['original_size'])}")
            print(f"压缩后大小: {self._format_size(self.stats['compressed_size'])}")
            print(f"压缩率: {ratio:.1f}%")
        
        print("=" * 60)
    
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
    import argparse
    
    parser = argparse.ArgumentParser(description='图片压缩工具')
    parser.add_argument('--limit', type=int, default=100, help='最多处理文件数（默认100）')
    parser.add_argument('--photo-root', type=str, default=PHOTO_ROOT, help='照片根目录')
    parser.add_argument('--output-dir', type=str, default=OUTPUT_DIR, help='输出目录')
    
    args = parser.parse_args()
    
    compressor = ImageCompressor(args.photo_root, args.output_dir)
    compressor.run(args.limit)


if __name__ == '__main__':
    main()
