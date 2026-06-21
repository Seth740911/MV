#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""修复 render-new.js - 适配实际数据结构"""

RN_PATH = r'G:\AI\PZ\engine\render-new.js'

with open(RN_PATH, 'r', encoding='utf-8') as f:
    rn = f.read()

# 相册数据结构:
# { id, name, path, date, count, cover, hasVideo, tags, photos: [{ f, w, h, s, d }] }
# path 是相对路径如 "007-北方重工设备彩页/全断面隧道掘进机"
# 完整路径需要拼接: G:/照片/LS/ + path + / + f

# 1. 修复 buildPhotoCard 中的缩略图URL构建
old_cover = """    var cover = '';
    if (album.photos && album.photos.length > 0) {
      var p = album.photos[0];
      var thumbUrl = '';
      if (typeof toThumbPath === 'function') {
        thumbUrl = toThumbPath(p.path || p, 400, 300);
      } else {
        thumbUrl = p.url || p.path || p;
      }
      cover = '<img src="' + thumbUrl + '" alt="' + escHtml(album.name) + '" loading="lazy">';
    } else {
      cover = '<div style="display:flex;align-items:center;justify-content:center;height:100%;color:var(--text-muted);font-size:40px;">📷</div>';
    }"""

new_cover = """    var cover = '';
    if (album.photos && album.photos.length > 0) {
      var p = album.photos[0];
      var fullRelPath = buildPhotoPath(album, p);
      var thumbUrl = typeof toThumbPath === 'function'
        ? toThumbPath(fullRelPath, 400, 300)
        : fullRelPath;
      cover = '<img src="' + thumbUrl + '" alt="' + escHtml(album.name) + '" loading="lazy">';
    } else if (album.cover) {
      var coverPath = 'G:/照片/' + (typeof _currentCatCode !== 'undefined' ? _currentCatCode : 'LS') + '/' + album.path + '/' + album.cover;
      var thumbUrl = typeof toThumbPath === 'function' ? toThumbPath(coverPath, 400, 300) : coverPath;
      cover = '<img src="' + thumbUrl + '" alt="' + escHtml(album.name) + '" loading="lazy">';
    } else {
      cover = '<div style="display:flex;align-items:center;justify-content:center;height:100%;color:var(--text-muted);font-size:40px;">📷</div>';
    }"""

if old_cover in rn:
    rn = rn.replace(old_cover, new_cover)
    print('✓ buildPhotoCard: 缩略图URL已适配数据结构')

# 2. 修复 photoCount 使用 album.count 或 album.photos.length
old_count = "    var photoCount = album.photos ? album.photos.length : 0;"
new_count = "    var photoCount = album.count || (album.photos ? album.photos.length : 0);"

if old_count in rn:
    rn = rn.replace(old_count, new_count)
    print('✓ buildPhotoCard: 照片计数已适配')

# 3. 修复 openAlbum 中的照片路径构建
old_photos = """    photos.forEach(function(p, i) {
      var imgUrl = '';
      if (typeof toThumbPath === 'function') {
        imgUrl = toThumbPath(p.path || p, 400, 400);
      } else {
        imgUrl = p.url || p.path || p;
      }
      var fullName = typeof toMediaPath === 'function' ? toMediaPath(p.path || p) : (p.url || p.path || p);"""

new_photos = """    var catCode = _currentCatCode || 'LS';
    photos.forEach(function(p, i) {
      var fullRelPath = 'G:/照片/' + catCode + '/' + album.path + '/' + (p.f || p.path || p);
      var imgUrl = typeof toThumbPath === 'function' ? toThumbPath(fullRelPath, 400, 400) : fullRelPath;
      var fullName = typeof toMediaPath === 'function' ? toMediaPath(fullRelPath) : fullRelPath;"""

if old_photos in rn:
    rn = rn.replace(old_photos, new_photos)
    print('✓ openAlbum: 照片路径已适配')

# 4. 在 renderGrid 中记录当前分类代码
old_render = """    pageState[tabId] = {
      albums: albums,
      page: 1,
      total: albums.length
    };

    renderGridPage(tabId, 1);"""

new_render = """    _currentCatCode = tabId.toUpperCase();
    pageState[tabId] = {
      albums: albums,
      page: 1,
      total: albums.length
    };

    renderGridPage(tabId, 1);"""

if old_render in rn:
    rn = rn.replace(old_render, new_render)
    print('✓ renderGrid: 记录当前分类代码')

# 5. 添加辅助函数
helper = """
  var _currentCatCode = 'LS';

  /**
   * 构建照片完整路径
   */
  function buildPhotoPath(album, photo) {
    var catCode = _currentCatCode || 'LS';
    var fileName = photo.f || photo.path || photo;
    return 'G:/照片/' + catCode + '/' + album.path + '/' + fileName;
  }

"""

# 在 viewerState 定义之后插入
marker = "  var perPage = 48;"
if marker in rn:
    rn = rn.replace(marker, helper + marker)
    print('✓ 辅助函数已添加')

with open(RN_PATH, 'w', encoding='utf-8') as f:
    f.write(rn)

print('✓ render-new.js 修复完成')
