/**
 * 尚唯云册 3.0 - 照片渲染引擎
 * 负责照片卡片渲染、网格布局、查看器、回忆模式
 */
(function() {
  'use strict';

  var viewerState = {
    photos: [],
    index: 0,
    zoom: 1,
    rotation: 0
  };

  var memoryState = {
    photos: [],
    index: 0,
    timer: null,
    interval: 5000
  };

  var perPage = 48;
  var pageState = {};

  /**
   * 渲染照片网格
   */
  function renderGrid(tabId, albums) {
    var grid = document.getElementById(tabId + '-grid');
    if (!grid) return;

    pageState[tabId] = {
      albums: albums,
      page: 1,
      total: albums.length
    };

    renderGridPage(tabId, 1);
  }

  /**
   * 渲染网格的某一页
   */
  function renderGridPage(tabId, page) {
    var ps = pageState[tabId];
    if (!ps) return;

    ps.page = page;
    var grid = document.getElementById(tabId + '-grid');
    if (!grid) return;

    var start = (page - 1) * perPage;
    var end = Math.min(start + perPage, ps.albums.length);
    var pageAlbums = ps.albums.slice(start, end);

    var html = '';
    pageAlbums.forEach(function(album) {
      html += buildPhotoCard(album, tabId);
    });

    grid.innerHTML = html;

    // 渲染分页
    renderPagination(tabId);

    // 绑定卡片点击
    var cards = grid.querySelectorAll('.photo-card');
    cards.forEach(function(card) {
      card.addEventListener('click', function() {
        var idx = parseInt(this.getAttribute('data-index')) + start;
        openAlbum(ps.albums[idx], tabId);
      });
    });
  }

  /**
   * 构建照片卡片HTML
   */
  function buildPhotoCard(album, tabId) {
    var cover = '';
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
    }

    var photoCount = album.photos ? album.photos.length : 0;
    var tags = '';
    if (album.tags && album.tags.length > 0) {
      var tag = album.tags[0];
      var tagDef = (typeof albumTagDefs !== 'undefined' && albumTagDefs[tag]) ? albumTagDefs[tag] : null;
      var tagColor = tagDef ? tagDef.color : '#666';
      tags = '<span class="photo-card-tag" style="background:' + tagColor + '22;color:' + tagColor + '">' + tag + '</span>';
    }

    return '<div class="photo-card">' +
           '<div class="photo-card-cover">' + cover +
           '<span class="photo-card-count">' + photoCount + ' 张</span>' +
           '</div>' +
           '<div class="photo-card-info">' +
           '<div class="photo-card-title">' + escHtml(album.name) + '</div>' +
           '<div class="photo-card-meta">' +
           '<span>' + (album.date || '') + '</span>' +
           tags +
           '</div></div></div>';
  }

  /**
   * 渲染横向滚动卡片
   */
  function renderScroll(containerId, albums) {
    var container = document.getElementById(containerId);
    if (!container) return;

    var html = '';
    albums.forEach(function(album, i) {
      html += buildPhotoCard(album, 'scroll');
    });
    container.innerHTML = html;

    // 绑定点击
    var cards = container.querySelectorAll('.photo-card');
    cards.forEach(function(card, i) {
      card.addEventListener('click', function() {
        openAlbum(albums[i], 'home');
      });
    });
  }

  /**
   * 渲染分页
   */
  function renderPagination(tabId) {
    var pag = document.getElementById(tabId + '-pagination');
    if (!pag) return;

    var ps = pageState[tabId];
    if (!ps || ps.total <= perPage) {
      pag.innerHTML = '';
      return;
    }

    var totalPages = Math.ceil(ps.total / perPage);
    var html = '';

    // 上一页
    html += '<button class="page-btn" onclick="RenderNew.goPage(\'' + tabId + '\',' + (ps.page - 1) + ')"' +
            (ps.page <= 1 ? ' disabled' : '') + '>&larr;</button>';

    // 页码
    for (var i = 1; i <= totalPages; i++) {
      if (i === 1 || i === totalPages || (i >= ps.page - 2 && i <= ps.page + 2)) {
        html += '<button class="page-btn' + (i === ps.page ? ' active' : '') + '" onclick="RenderNew.goPage(\'' + tabId + '\',' + i + ')">' + i + '</button>';
      } else if (i === ps.page - 3 || i === ps.page + 3) {
        html += '<span style="color:var(--text-muted);padding:0 4px">...</span>';
      }
    }

    // 下一页
    html += '<button class="page-btn" onclick="RenderNew.goPage(\'' + tabId + '\',' + (ps.page + 1) + ')"' +
            (ps.page >= totalPages ? ' disabled' : '') + '>&rarr;</button>';

    pag.innerHTML = html;
  }

  /**
   * 打开相册详情
   */
  function openAlbum(album, tabId) {
    var modal = document.getElementById('album-modal');
    if (!modal || !album) return;

    var photos = album.photos || [];
    var html = '<div class="album-modal-inner">' +
               '<button class="album-modal-close" onclick="RenderNew.closeAlbum()">&times;</button>' +
               '<div class="album-modal-header">' +
               '<h2>' + escHtml(album.name) + '</h2>' +
               '<span>' + (album.date || '') + ' · ' + photos.length + ' 张照片</span>';

    if (album.tags && album.tags.length > 0) {
      html += '<div class="album-modal-tags">';
      album.tags.forEach(function(tag) {
        var tagDef = (typeof albumTagDefs !== 'undefined' && albumTagDefs[tag]) ? albumTagDefs[tag] : null;
        var color = tagDef ? tagDef.color : '#666';
        html += '<span class="tag-chip" style="border-color:' + color + ';color:' + color + '">' + (tagDef && tagDef.icon ? tagDef.icon + ' ' : '') + tag + '</span>';
      });
      html += '</div>';
    }

    html += '</div><div class="album-modal-grid">';

    photos.forEach(function(p, i) {
      var imgUrl = '';
      if (typeof toThumbPath === 'function') {
        imgUrl = toThumbPath(p.path || p, 400, 400);
      } else {
        imgUrl = p.url || p.path || p;
      }
      var fullName = typeof toMediaPath === 'function' ? toMediaPath(p.path || p) : (p.url || p.path || p);
      html += '<div class="album-photo-item" data-index="' + i + '" data-full="' + escAttr(fullName) + '">' +
              '<img src="' + imgUrl + '" alt="" loading="lazy">' +
              '</div>';
    });

    html += '</div></div>';
    modal.innerHTML = html;
    modal.style.display = 'block';
    document.body.style.overflow = 'hidden';

    // 绑定照片点击 → 打开查看器
    var items = modal.querySelectorAll('.album-photo-item');
    items.forEach(function(item) {
      item.addEventListener('click', function() {
        var idx = parseInt(this.getAttribute('data-index'));
        var allPhotos = [];
        items.forEach(function(el) {
          allPhotos.push(el.getAttribute('data-full'));
        });
        openViewer(allPhotos, idx, album);
      });
    });
  }

  /**
   * 关闭相册
   */
  function closeAlbum() {
    var modal = document.getElementById('album-modal');
    if (modal) {
      modal.style.display = 'none';
      modal.innerHTML = '';
    }
    document.body.style.overflow = '';
  }

  // ====== 照片查看器 ======

  function openViewer(photos, index, album) {
    viewerState.photos = photos;
    viewerState.index = index;
    viewerState.zoom = 1;
    viewerState.rotation = 0;

    var overlay = document.getElementById('viewer-overlay');
    if (overlay) {
      overlay.style.display = 'flex';
      showViewerPhoto();
    }
  }

  function showViewerPhoto() {
    var img = document.getElementById('viewer-img');
    var counter = document.getElementById('viewer-counter');
    if (!img) return;

    img.src = viewerState.photos[viewerState.index];
    img.style.transform = 'scale(' + viewerState.zoom + ') rotate(' + viewerState.rotation + 'deg)';

    if (counter) {
      counter.textContent = (viewerState.index + 1) + ' / ' + viewerState.photos.length;
    }
  }

  function viewerPrev() {
    if (viewerState.index > 0) {
      viewerState.index--;
      viewerState.zoom = 1;
      viewerState.rotation = 0;
      showViewerPhoto();
    }
  }

  function viewerNext() {
    if (viewerState.index < viewerState.photos.length - 1) {
      viewerState.index++;
      viewerState.zoom = 1;
      viewerState.rotation = 0;
      showViewerPhoto();
    }
  }

  function viewerZoom(delta) {
    viewerState.zoom = Math.max(0.3, Math.min(5, viewerState.zoom + delta));
    var img = document.getElementById('viewer-img');
    if (img) img.style.transform = 'scale(' + viewerState.zoom + ') rotate(' + viewerState.rotation + 'deg)';
  }

  function viewerRotate() {
    viewerState.rotation = (viewerState.rotation + 90) % 360;
    var img = document.getElementById('viewer-img');
    if (img) img.style.transform = 'scale(' + viewerState.zoom + ') rotate(' + viewerState.rotation + 'deg)';
  }

  function closeViewer() {
    var overlay = document.getElementById('viewer-overlay');
    if (overlay) overlay.style.display = 'none';
  }

  // ====== 回忆模式 ======

  function startMemory() {
    // 收集所有照片
    var allPhotos = [];
    var cache = window.TabSystem ? window.TabSystem.state.albumsCache : {};
    Object.keys(cache).forEach(function(tabId) {
      (cache[tabId] || []).forEach(function(album) {
        if (album.photos) {
          album.photos.forEach(function(p) {
            var url = typeof toMediaPath === 'function' ? toMediaPath(p.path || p) : (p.url || p.path || p);
            allPhotos.push({
              url: url,
              name: album.name,
              date: album.date || '',
              tags: album.tags || []
            });
          });
        }
      });
    });

    if (allPhotos.length === 0) {
      // 从生活分类取
      if (typeof DataLoader !== 'undefined') {
        DataLoader.load('LS').then(function(albums) {
          (albums || []).forEach(function(album) {
            if (album.photos) {
              album.photos.forEach(function(p) {
                var url = typeof toMediaPath === 'function' ? toMediaPath(p.path || p) : (p.url || p.path || p);
                allPhotos.push({ url: url, name: album.name, date: album.date || '' });
              });
            }
          });
          if (allPhotos.length > 0) startMemoryWith(allPhotos);
        });
      }
    } else {
      startMemoryWith(allPhotos);
    }
  }

  function startMemoryWith(photos) {
    // 随机打乱
    for (var i = photos.length - 1; i > 0; i--) {
      var j = Math.floor(Math.random() * (i + 1));
      var tmp = photos[i]; photos[i] = photos[j]; photos[j] = tmp;
    }

    memoryState.photos = photos.slice(0, 50);
    memoryState.index = 0;

    var overlay = document.getElementById('memory-overlay');
    if (overlay) overlay.style.display = 'block';

    showMemoryPhoto();
    memoryState.timer = setInterval(nextMemory, memoryState.interval);
  }

  function showMemoryPhoto() {
    var photo = memoryState.photos[memoryState.index];
    if (!photo) return;

    var img = document.getElementById('memory-img');
    var bg = document.getElementById('memory-bg');
    var title = document.getElementById('memory-title');
    var date = document.getElementById('memory-date');
    var bar = document.getElementById('memory-bar');

    if (img) img.src = photo.url;
    if (bg) bg.style.backgroundImage = 'url(' + photo.url + ')';
    if (title) title.textContent = photo.name;
    if (date) date.textContent = photo.date;
    if (bar) bar.style.width = ((memoryState.index + 1) / memoryState.photos.length * 100) + '%';
  }

  function nextMemory() {
    if (memoryState.index < memoryState.photos.length - 1) {
      memoryState.index++;
      showMemoryPhoto();
    } else {
      clearInterval(memoryState.timer);
    }
  }

  function memPrev() {
    if (memoryState.index > 0) {
      memoryState.index--;
      showMemoryPhoto();
    }
  }

  function memNext() {
    if (memoryState.index < memoryState.photos.length - 1) {
      memoryState.index++;
      showMemoryPhoto();
    }
  }

  function closeMemory() {
    clearInterval(memoryState.timer);
    var overlay = document.getElementById('memory-overlay');
    if (overlay) overlay.style.display = 'none';
  }

  // ====== 搜索 ======

  function search(query) {
    var tabId = window.TabSystem ? window.TabSystem.getActive() : 'home';
    if (tabId === 'home' || tabId === 'memory') return;

    var ps = pageState[tabId];
    if (!ps) return;

    if (!query) {
      renderGridPage(tabId, 1);
      return;
    }

    var q = query.toLowerCase();
    var filtered = ps.albums.filter(function(album) {
      return (album.name && album.name.toLowerCase().indexOf(q) >= 0) ||
             (album.tags && album.tags.some(function(t) { return t.toLowerCase().indexOf(q) >= 0; })) ||
             (album.date && album.date.indexOf(q) >= 0);
    });

    var grid = document.getElementById(tabId + '-grid');
    if (grid) {
      var html = '';
      filtered.forEach(function(album, i) {
        html += buildPhotoCard(album, tabId);
      });
      grid.innerHTML = html;
    }

    // 隐藏分页
    var pag = document.getElementById(tabId + '-pagination');
    if (pag) pag.innerHTML = '';
  }

  // ====== 工具函数 ======

  function escHtml(s) {
    if (!s) return '';
    return s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
  }

  function escAttr(s) {
    return escHtml(s);
  }

  // 全局键盘事件
  document.addEventListener('keydown', function(e) {
    var viewer = document.getElementById('viewer-overlay');
    var memory = document.getElementById('memory-overlay');

    if (viewer && viewer.style.display !== 'none') {
      if (e.key === 'ArrowLeft') viewerPrev();
      else if (e.key === 'ArrowRight') viewerNext();
      else if (e.key === 'Escape') closeViewer();
    } else if (memory && memory.style.display !== 'none') {
      if (e.key === 'ArrowLeft') memPrev();
      else if (e.key === 'ArrowRight') memNext();
      else if (e.key === 'Escape') closeMemory();
    } else if (e.key === 'Escape') {
      closeAlbum();
    }
  });

  // 导出
  window.RenderNew = {
    renderGrid: renderGrid,
    renderScroll: renderScroll,
    goPage: function(tabId, page) { renderGridPage(tabId, page); },
    openAlbum: openAlbum,
    closeAlbum: closeAlbum,
    search: search
  };

  window.viewerPrev = viewerPrev;
  window.viewerNext = viewerNext;
  window.viewerZoom = viewerZoom;
  window.viewerRotate = viewerRotate;
  window.closeViewer = closeViewer;
  window.startMemory = startMemory;
  window.memPrev = memPrev;
  window.memNext = memNext;
  window.closeMemory = closeMemory;

})();
