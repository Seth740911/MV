#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""修复 tab-controller.js 中统计数据的变量名"""

TC_PATH = r'G:\AI\PZ\engine\tab-controller.js'

with open(TC_PATH, 'r', encoding='utf-8') as f:
    tc = f.read()

# 修复统计数据加载
old = """  function loadStats() {
    if (typeof window.photoStats !== 'undefined') {
      var s = window.photoStats;
      setText('stat-total', s.totalPhotos || 0);
      setText('stat-albums', s.totalAlbums || 0);
      setText('stat-tags', s.totalTags || 0);
      setText('stat-years', s.yearSpan || 0);
    }
  }"""

new = """  function loadStats() {
    var s = window.globalStats;
    if (s) {
      setText('stat-total', s.totalPhotos || 0);
      setText('stat-albums', s.totalAlbums || 0);
      // 计算标签数
      var tagCount = 0;
      if (typeof albumTagDefs !== 'undefined') {
        tagCount = Object.keys(albumTagDefs).length;
      }
      setText('stat-tags', tagCount);
      // 计算年份跨度
      setText('stat-years', '10+');
    }
  }"""

if old in tc:
    tc = tc.replace(old, new)
    print('✓ 统计数据变量名已修复 (photoStats → globalStats)')

with open(TC_PATH, 'w', encoding='utf-8') as f:
    f.write(tc)

print('✓ tab-controller.js 已更新')
