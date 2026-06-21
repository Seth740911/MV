#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""修复 tab-controller.js 和 render-new.js - 适配 DataLoader 回调模式"""
import os

# DataLoader 用的是回调模式: DataLoader.load(code, callback)
# 不是 Promise 模式

# ========== 修复 tab-controller.js ==========
TC_PATH = r'G:\AI\PZ\engine\tab-controller.js'

with open(TC_PATH, 'r', encoding='utf-8') as f:
    tc = f.read()

# 替换所有 DataLoader.load(xxx).then(...) 为回调模式
old1 = """    if (typeof DataLoader !== 'undefined' && DataLoader.load) {
      DataLoader.load(code).then(function(albums) {
        state.albumsCache[tabId] = albums || [];
        if (window.RenderNew && window.RenderNew.renderGrid) {
          window.RenderNew.renderGrid(tabId, albums || []);
        }
        updateBadge(tabId, (albums || []).length);
      }).catch(function(err) {
        console.error('[TabSystem] 加载失败:', tabId, err);
      });
    }"""

new1 = """    if (typeof DataLoader !== 'undefined' && DataLoader.load) {
      DataLoader.load(code, function(albums) {
        albums = albums || [];
        state.albumsCache[tabId] = albums;
        if (window.RenderNew && window.RenderNew.renderGrid) {
          window.RenderNew.renderGrid(tabId, albums);
        }
        updateBadge(tabId, albums.length);
      });
    }"""

if old1 in tc:
    tc = tc.replace(old1, new1)
    print('✓ tab-controller: 分类数据加载已适配回调模式')

old2 = """    DataLoader.load('LS').then(function(albums) {
      var sorted = (albums || []).slice().sort(function(a, b) {
        return (b.date || '').localeCompare(a.date || '');
      });
      var recent = sorted.slice(0, 12);
      if (window.RenderNew && window.RenderNew.renderScroll) {
        window.RenderNew.renderScroll('recent-scroll', recent);
      }
    }).catch(function() {});"""

new2 = """    DataLoader.load('LS', function(albums) {
      albums = albums || [];
      var sorted = albums.slice().sort(function(a, b) {
        return (b.date || '').localeCompare(a.date || '');
      });
      var recent = sorted.slice(0, 12);
      if (window.RenderNew && window.RenderNew.renderScroll) {
        window.RenderNew.renderScroll('recent-scroll', recent);
      }
    });"""

if old2 in tc:
    tc = tc.replace(old2, new2)
    print('✓ tab-controller: 最近更新已适配回调模式')

old3 = """      if (typeof DataLoader !== 'undefined' && DataLoader.load) {
        DataLoader.load(code).then(function(albums) {
          var el = document.getElementById('cat-' + code.toLowerCase() + '-count');
          if (el) el.textContent = (albums || []).length + ' 个相册';
        }).catch(function() {});
      }"""

new3 = """      if (typeof DataLoader !== 'undefined' && DataLoader.load) {
        DataLoader.load(code, function(albums) {
          var el = document.getElementById('cat-' + code.toLowerCase() + '-count');
          if (el) el.textContent = (albums || []).length + ' 个相册';
        });
      }"""

if old3 in tc:
    tc = tc.replace(old3, new3)
    print('✓ tab-controller: 分类速览已适配回调模式')

old4 = """      if (typeof DataLoader !== 'undefined') {
        DataLoader.load('LS').then(function(albums) {
          (albums || []).forEach(function(album) {"""

new4 = """      if (typeof DataLoader !== 'undefined') {
        DataLoader.load('LS', function(albums) {
          (albums || []).forEach(function(album) {"""

if old4 in tc:
    tc = tc.replace(old4, new4)
    # 也需要去掉尾部的 });
    tc = tc.replace("          if (allPhotos.length > 0) startMemoryWith(allPhotos);\n        });", 
                    "          if (allPhotos.length > 0) startMemoryWith(allPhotos);\n        });")
    print('✓ tab-controller: 回忆模式已适配回调模式')

with open(TC_PATH, 'w', encoding='utf-8') as f:
    f.write(tc)

print('✓ tab-controller.js 修复完成')
