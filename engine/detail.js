/**
 * 尚唯云影 - 详情页模块（4分类通用）
 * 对齐GL大卡详情风格：hero banner + gallery + photo viewer + fullscreen player
 */

var currentDetail = null;
var currentPlayingEp = null;
var currentLocalPath = null; // 当前播放文件的本地路径，供本机播放

// ES5 兼容的 padStart（2位补零）
function _pad2(n) {
  var s = String(n);
  return s.length < 2 ? '0' + s : s;
}

// ===== 键盘快捷键（对齐GL） =====
(function() {
  var SEEK_STEP = 10;
  var VOLUME_STEP = 0.1;

  // 在捕获阶段拦截，防止浏览器原生video控件也响应空格/方向键导致双触发
  document.addEventListener('keydown', function(e) {
    var video = document.getElementById('detail-video');
    if (!video) return;

    // 搜索框/输入框不拦截
    if (document.activeElement && document.activeElement.tagName === 'INPUT') return;

    switch (e.key) {
      case ' ':
        e.preventDefault();
        e.stopPropagation();
        video.paused ? video.play() : video.pause();
        break;
      case 'ArrowLeft':
        e.preventDefault();
        e.stopPropagation();
        video.currentTime = Math.max(0, video.currentTime - SEEK_STEP);
        break;
      case 'ArrowRight':
        e.preventDefault();
        e.stopPropagation();
        video.currentTime = Math.min(video.duration || 0, video.currentTime + SEEK_STEP);
        break;
      case 'ArrowUp':
        e.preventDefault();
        e.stopPropagation();
        if (video.muted) { video.muted = false; video.volume = 0; }
        video.volume = Math.min(1, video.volume + VOLUME_STEP);
        break;
      case 'ArrowDown':
        e.preventDefault();
        e.stopPropagation();
        if (video.muted && video.volume === 0) break;
        video.volume = Math.max(0, video.volume - VOLUME_STEP);
        if (video.volume === 0) video.muted = true;
        break;
    }
  }, true); // true = 捕获阶段
})();

// ========= 图片查看器状态 =========
var _photoViewerPhotos = [];
var _photoViewerIndex = 0;
var _photoViewerScale = 1;
var _photoViewerDragging = false;
var _photoViewerStartX = 0;
var _photoViewerStartY = 0;
var _photoViewerOffsetX = 0;
var _photoViewerOffsetY = 0;

// 视频初始化：MutationObserver检测video出现时绑手势
document.addEventListener('DOMContentLoaded', function() {
  var observer = new MutationObserver(function() {
    var video = document.getElementById('detail-video');
    if (video) {
      _vgInit(video);
    }
  });
  var detailContent = document.getElementById('detail-content');
  if (detailContent) {
    observer.observe(detailContent, { childList: true, subtree: true });
  }
});

function detailDividerTitle(text) {
  return '<div class="detail-section-title-wrap"><span class="detail-divider"></span><span class="detail-section-title">' + text + '</span><span class="detail-divider"></span></div>';
}

// ========= 打开详情页（回调模式，兼容 Android 4.4） =========
function openDetail(cat, seriesName, itemTitle) {
  var catConfig = CATEGORIES[cat];

  // 确保分类数据已加载
  if (!DataLoader.isLoaded(cat)) {
    DataLoader.load(cat, function(err) {
      if (!err) {
        if (typeof _rebuildCategoryDropdown === 'function') _rebuildCategoryDropdown();
        _openDetailRender(cat, seriesName, itemTitle);
      }
    });
    return;
  }

  _openDetailRender(cat, seriesName, itemTitle);
}

function _openDetailRender(cat, seriesName, itemTitle) {
  var catConfig = CATEGORIES[cat];

  if (typeof window[catConfig.dataVar] === 'undefined') return;

  var data = window[catConfig.dataVar];
  var series = data[seriesName];
  if (!series) return;

  var items = series.movies || series.shows || [];
  var item = null;
  items.forEach(function(it) {
    if (it.title === itemTitle || it.dir === itemTitle) item = it;
  });
  if (!item && items.length > 0) item = items[0];
  if (!item) return;

  currentDetail = { cat: cat, seriesName: seriesName, item: item, series: series };
  currentPlayingEp = null;

  var isMovie = !!(item.file);
  var itemPath = item.path || series.path;
  var nfo = item.nfo || series.nfo || {};
  var catColor = getCatColor(cat);
  var catName = catConfig.name;

  var posterUrl = item.poster ? resourceUrl(itemPath, item.poster) : '';
  var fanartUrl = item.fanart ? resourceUrl(itemPath, item.fanart) : '';

  // === Hero banner 背景图 ===
  var heroBgHtml = '';
  if (fanartUrl) {
    heroBgHtml = '<div class="detail-hero-bg" style="background-image:url(' + fanartUrl + ')"></div>';
  }

  var posterHtml = posterUrl
    ? '<div class="detail-poster"><img src="' + posterUrl + '" onerror="this.parentElement.innerHTML=\'\'"></div>'
    : '<div class="detail-poster"></div>';

  var titleText = item.title || seriesName;
  var titleEnHtml = item.titleEn ? '<div class="detail-title-en" style="font-size:14px;color:#666;margin-bottom:8px;">' + item.titleEn + '</div>' : '';

  var metaHtml = '<div class="detail-meta">';
  metaHtml += '<span class="detail-cat-tag" style="background:' + catColor + '">' + catName + '</span>';
  var displayName = getSeriesDisplayName(cat, seriesName);
  if (displayName && displayName !== titleText) metaHtml += '<span>' + displayName + '</span>';
  if (item.year) metaHtml += '<span>' + item.year + '年</span>';
  if (item.audio) metaHtml += '<span>' + item.audio + '</span>';
  if (item.episodeCount) metaHtml += '<span>' + item.episodeCount + '集</span>';
  if (item.size) metaHtml += '<span>' + formatSize(item.size) + '</span>';
  metaHtml += '</div>';

  var rating = nfo.rating || item.rating || '';
  var ratingHtml = '';
  if (rating) {
    ratingHtml = '<div class="detail-rating"><span class="rating-star">\u2605</span><span class="rating-value">' + rating + '</span>';
    if (nfo.vote_count) ratingHtml += '<span class="rating-count">(' + nfo.vote_count + '票)</span>';
    ratingHtml += '</div>';
  }

  var genres = nfo.genres || item.genres || [];
  var genresHtml = '';
  if (genres.length > 0) {
    genresHtml = '<div class="detail-genres">' + genres.map(function(g) { return '<span class="genre-tag">' + g + '</span>'; }).join('') + '</div>';
  }

  var plot = nfo.biography || nfo.plot || item.plot || '';
  var plotHtml = plot ? '<div class="detail-plot">' + plot + '</div>' : '';

  var actors = nfo.actors || item.actors || [];
  var actorsHtml = '';
  if (actors.length > 0) {
    actorsHtml = '<div class="detail-people">' + detailDividerTitle('演员') +
      '<div class="detail-actor-list">' +
      actors.slice(0, 20).map(function(a) {
        var name = a.name || a;
        var thumb = a.thumb || '';
        return '<span class="actor-chip">' +
          (thumb ? '<img src="' + thumb + '" onerror="this.style.display=\'none\'">' : '') +
          name + '</span>';
      }).join('') +
      '</div></div>';
  }

  var actionsHtml = '';
  if (isMovie && item.file) {
    var subdir = item.subdir || '';
    var movieFile = subdir ? subdir + '/' + item.file : item.file;
    var localPath = (itemPath + '/' + movieFile).replace(/\\/g, '/').replace(/\/+/g, '/');
    // TV端不需要"本机播放"按钮（所有播放都走系统播放器）
    if (isTV) {
      actionsHtml = '<div class="detail-actions"><button class="detail-play-btn" onclick="playCurrent()">\u25B6 播放</button></div>';
    } else {
      actionsHtml = '<div class="detail-actions"><button class="detail-play-btn" onclick="playCurrent()">\u25B6 播放</button><button class="detail-localplay-btn" onclick="localPlay(\'' + escapeAttr(localPath) + '\')">&#9654;&#9654; 本机播放</button></div>';
    }
  }

  var episodesHtml = '';
  var episodes = item.episodes || [];
  if (episodes.length > 0) {
    var epBtns = '';
  // === 智能分集标签：有季用S01E01，无季用纯数字 ===
  var hasSeasons = /Season\s*\d+/i.test(item.title || '') ||
    episodes.some(function(ep) { return /S\d+E\d+/i.test(ep.file || ep.name || ''); });

  episodes.forEach(function(ep, idx) {
    var epNum = ep.episode || 0;
    var label;
    if (hasSeasons) {
      // 从title提取季号，如"Season 01" → 1，默认用1
      var seasonMatch = (item.title || '').match(/Season\s*(\d+)/i);
      var seasonNum = seasonMatch ? parseInt(seasonMatch[1], 10) : 1;
      var epVal = epNum > 0 ? epNum : (idx + 1);
      // 尝试从文件名提取S##E##
      var fileMatch = (ep.file || ep.name || '').match(/S(\d+)E(\d+)/i);
      if (fileMatch) {
        seasonNum = parseInt(fileMatch[1], 10);
        epVal = parseInt(fileMatch[2], 10);
      }
      label = 'S' + _pad2(seasonNum) + 'E' + _pad2(epVal);
      // 同集多文件时加后缀区分（如S00E01.1 → S00E01-a）
      var partMatch = (ep.file || ep.name || '').match(/S\d+E\d+\.(\d+)/i);
      if (partMatch) {
        label += '-' + String.fromCharCode(96 + parseInt(partMatch[1], 10)); // 1→a, 2→b
      }
    } else {
      label = epNum > 0 ? String(epNum) : String(idx + 1);
    }
    epBtns += '<button class="ep-btn" data-ep="' + epNum + '" data-file="' + escapeAttr(ep.file) + '" ' +
      'data-subdir="' + escapeAttr(ep.subdir || '') + '" onclick="playEpisode(this)">' + label + '</button>';
  });
    // 剧集本机播放按钮（TV端隐藏）
    episodesHtml = '<div class="detail-section" id="detail-episodes-section">' +
      detailDividerTitle('分集列表') +
      '<div class="detail-ep-header"><span class="detail-ep-count">' + episodes.length + '集</span>' +
      (isTV ? '' : '<button class="detail-localplay-btn" onclick="localPlayCurrent()" title="本机播放（支持多音轨/字幕）">&#9654;&#9654; 本机播放</button>') +
      '</div>' +
      '<div class="ep-grid" id="detail-ep-grid">' + epBtns + '</div></div>';
  }

  // === 水平画廊（收集该系列所有海报/图片） ===
  var galleryHtml = '';
  var galleryPhotos = _collectGalleryPhotos(cat, seriesName, item, series);
  if (galleryPhotos.length > 1) {
    var galleryItems = '';
    galleryPhotos.forEach(function(p, idx) {
      galleryItems += '<div class="gallery-item" onclick="openPhotoViewer(' + idx + ')">' +
        '<img src="' + p.url + '" onerror="this.parentElement.style.display=\'none\'">' +
        '<div class="gallery-item-overlay">' + (p.label || '') + '</div></div>';
    });
    galleryHtml = '<div class="detail-section">' +
      detailDividerTitle('剧照') +
      '<div class="detail-gallery" id="detail-gallery">' +
      '<button class="gallery-arrow gallery-arrow-left" onclick="scrollGallery(-1)">\u25C0</button>' +
      '<div class="gallery-track" id="gallery-track">' + galleryItems + '</div>' +
      '<button class="gallery-arrow gallery-arrow-right" onclick="scrollGallery(1)">\u25B6</button>' +
      '</div></div>';
  }

  // === 视频播放器（TV端也显示，支持变速播放） ===
  var playerHtml = '<div class="detail-video-player">' +
    '<video id="detail-video" controls preload="metadata"></video>' +
    '<div class="speed-control">' +
    '<button class="speed-btn" data-speed="0.5">0.5x</button>' +
    '<button class="speed-btn" data-speed="0.75">0.75x</button>' +
    '<button class="speed-btn active" data-speed="1.0">1.0x</button>' +
    '<button class="speed-btn" data-speed="1.25">1.25x</button>' +
    '<button class="speed-btn" data-speed="1.5">1.5x</button>' +
    '<button class="speed-btn" data-speed="2.0">2.0x</button>' +
    '</div></div>';

  var html =
    '<div class="detail">' +
    '<div class="detail-hero">' +
    heroBgHtml +
    posterHtml +
    '<div class="detail-hero-info">' +
    '<h1 class="detail-title">' + titleText + '</h1>' +
    titleEnHtml +
    metaHtml +
    ratingHtml +
    genresHtml +
    plotHtml +
    actorsHtml +
    actionsHtml +
    '</div></div>' +
    episodesHtml +
    playerHtml +
    galleryHtml +
    '</div>';

  document.getElementById('detail-content').innerHTML = html;

  // 初始化播放速度控制
  _initSpeedControl();

  // 保存画廊图片供查看器使用
  if (galleryPhotos.length > 0) {
    _photoViewerPhotos = galleryPhotos;
  }

  showPage('detail');
}

// ========= 收集画廊图片 =========
function _collectGalleryPhotos(cat, seriesName, item, series) {
  var photos = [];
  var itemPath = item.path || series.path;

  // 当前片的海报
  if (item.poster) {
    photos.push({ url: resourceUrl(itemPath, item.poster), label: '海报' });
  }
  // 当前片的 fanart
  if (item.fanart) {
    photos.push({ url: resourceUrl(itemPath, item.fanart), label: '背景' });
  }

  // 系列下其他片的海报
  var items = series.movies || series.shows || [];
  items.forEach(function(it) {
    if (it === item) return;
    var itPath = it.path || series.path;
    if (it.poster) {
      photos.push({ url: resourceUrl(itPath, it.poster), label: it.title || '' });
    }
    if (it.fanart) {
      photos.push({ url: resourceUrl(itPath, it.fanart), label: (it.title || '') + ' 背景' });
    }
  });

  return photos;
}

// ========= 画廊滚动 =========
function scrollGallery(dir) {
  var track = document.getElementById('gallery-track');
  if (!track) return;
  track.scrollBy({ left: dir * 260, behavior: 'smooth' });
}

// ========= 图片查看器 =========
function openPhotoViewer(index) {
  if (_photoViewerPhotos.length === 0) return;
  _photoViewerIndex = index || 0;
  _photoViewerScale = 1;
  _photoViewerOffsetX = 0;
  _photoViewerOffsetY = 0;

  var overlay = document.getElementById('photo-overlay');
  if (!overlay) return;

  _renderPhotoViewer();
  overlay.classList.add('active');
  document.body.style.overflow = 'hidden';
}

function closePhotoViewer() {
  var overlay = document.getElementById('photo-overlay');
  if (overlay) overlay.classList.remove('active');
  document.body.style.overflow = '';
}

function _renderPhotoViewer() {
  var photo = _photoViewerPhotos[_photoViewerIndex];
  if (!photo) return;

  var img = document.getElementById('photo-overlay-img');
  var counter = document.getElementById('photo-overlay-counter');
  if (img) {
    img.src = photo.url;
    img.style.transform = 'scale(' + _photoViewerScale + ') translate(' + _photoViewerOffsetX + 'px,' + _photoViewerOffsetY + 'px)';
  }
  if (counter) {
    counter.textContent = (_photoViewerIndex + 1) + ' / ' + _photoViewerPhotos.length;
  }
}

function photoViewerPrev() {
  if (_photoViewerIndex > 0) {
    _photoViewerIndex--;
    _photoViewerScale = 1;
    _photoViewerOffsetX = 0;
    _photoViewerOffsetY = 0;
    _renderPhotoViewer();
  }
}

function photoViewerNext() {
  if (_photoViewerIndex < _photoViewerPhotos.length - 1) {
    _photoViewerIndex++;
    _photoViewerScale = 1;
    _photoViewerOffsetX = 0;
    _photoViewerOffsetY = 0;
    _renderPhotoViewer();
  }
}

function photoViewerZoom(delta) {
  _photoViewerScale = Math.max(0.5, Math.min(5, _photoViewerScale + delta));
  var img = document.getElementById('photo-overlay-img');
  if (img) {
    img.style.transform = 'scale(' + _photoViewerScale + ') translate(' + _photoViewerOffsetX + 'px,' + _photoViewerOffsetY + 'px)';
  }
}

// ========= 视频播放 =========
function playCurrent() {
  if (!currentDetail) return;
  var item = currentDetail.item;
  var series = currentDetail.series;
  var cat = currentDetail.cat;
  var isMovie = !!(item.file);

  if (!isMovie) return;

  var itemPath = item.path || series.path;
  var subdir = item.subdir || '';
  var movieFile = subdir ? subdir + '/' + item.file : item.file;

  // 保存本地文件路径供本机播放
  currentLocalPath = (itemPath + '/' + movieFile).replace(/\\/g, '/').replace(/\/+/g, '/');

  var videoUrl = resourceUrl(itemPath, movieFile);

  var player = document.querySelector('.detail-video-player');
  var video = document.getElementById('detail-video');
  video.src = videoUrl;

  // 预设音量0.3，尝试有声播放；浏览器阻止自动播放时静音兜底
  video.volume = 0.3;
  video.muted = false;

  video.play().catch(function() {
    // 浏览器自动播放策略阻止，静音重试
    video.muted = true;
    video.play();
  });
  player.scrollIntoView({ behavior: 'smooth', block: 'center' });

  _vgInit(video);

  // 进度追踪：用系列名+标题作为唯一标识
  var videoId = (series.name || series.path || '') + '/' + (item.title || item.file || '');
  _initWatchProgressTracker('movie', videoId);
}

function playEpisode(btn) {
  if (!currentDetail) return;
  var item = currentDetail.item;
  var series = currentDetail.series;

  var file = btn.dataset.file;
  var subdir = btn.dataset.subdir || '';
  var itemPath = item.path || series.path;

  document.querySelectorAll('.ep-btn').forEach(function(b) { b.classList.remove('active'); });
  btn.classList.add('active');

  var filename = subdir ? subdir + '/' + file : file;

  currentPlayingEp = btn.dataset.ep;

  // 保存本地文件路径供本机播放
  currentLocalPath = (itemPath + '/' + filename).replace(/\\/g, '/').replace(/\/+/g, '/');

  var videoUrl = resourceUrl(itemPath, filename);

  var player = document.querySelector('.detail-video-player');
  var video = document.getElementById('detail-video');
  video.src = videoUrl;

  // 预设音量0.3，尝试有声播放；浏览器阻止自动播放时静音兜底
  video.volume = 0.3;
  video.muted = false;

  video.play().catch(function() {
    // 浏览器自动播放策略阻止，静音重试
    video.muted = true;
    video.play();
  });
  player.scrollIntoView({ behavior: 'smooth', block: 'center' });

  _vgInit(video);

  // 进度追踪：用系列名+集号作为唯一标识
  var videoId = (series.name || series.path || '') + '/E' + (btn.dataset.ep || '');
  _initWatchProgressTracker('episode', videoId);
}

// ========= 本机播放（KMPlayer，支持多音轨/字幕） =========
function localPlayCurrent() {
  if (!currentLocalPath) return;
  localPlay(currentLocalPath);
}

// ========= 全屏播放（对齐GL，webkit兼容） =========
function toggleFullscreen() {
  var player = document.querySelector('.detail-video-player');
  if (!player) return;
  if (document.fullscreenElement || document.webkitFullscreenElement) {
    if (document.exitFullscreen) {
      document.exitFullscreen();
    } else if (document.webkitExitFullscreen) {
      document.webkitExitFullscreen();
    }
    return;
  }
  if (player.requestFullscreen) {
    player.requestFullscreen();
    try { screen.orientation.lock('landscape'); } catch(e) {}
  } else if (player.webkitRequestFullscreen) {
    player.webkitRequestFullscreen();
  } else if (player.msRequestFullscreen) {
    player.msRequestFullscreen();
  }
}

// ========= 视频手势控制（全屏时生效，对齐GL） ==========
function _vgIsFullscreen() {
  return !!(document.fullscreenElement || document.webkitFullscreenElement || document.msFullscreenElement);
}

var _vGesture = {
  startX: 0, startY: 0, startTime: 0,
  startBrightness: 1, startVolume: 0.5, startTimeOffset: 0,
  isLeft: false, moved: false, seeking: false,
  overlay: null, seekBar: null
};

function _vgInit(video) {
  if (video._vgBound) return;
  video._vgBound = true;

  video.addEventListener('touchstart', function(e) {
    if (!_vgIsFullscreen()) return;
    if (e.touches.length !== 1) return;
    var t = e.touches[0];
    var rect = video.getBoundingClientRect();
    _vGesture.startX = t.clientX;
    _vGesture.startY = t.clientY;
    _vGesture.startTime = Date.now();
    _vGesture.isLeft = t.clientX < rect.left + rect.width / 2;
    _vGesture.moved = false;
    _vGesture.seeking = false;
    _vGesture.startBrightness = _vgGetBrightness();
    _vGesture.startVolume = video.volume;
    _vGesture.startTimeOffset = video.currentTime;
  }, { passive: true });

  video.addEventListener('touchmove', function(e) {
    if (!_vgIsFullscreen()) return;
    if (e.touches.length !== 1) return;
    var t = e.touches[0];
    var dx = t.clientX - _vGesture.startX;
    var dy = t.clientY - _vGesture.startY;
    if (Math.abs(dx) < 10 && Math.abs(dy) < 10) return;
    _vGesture.moved = true;

    var absDx = Math.abs(dx), absDy = Math.abs(dy);

    // 水平滑动 → 快进快退
    if (absDx > absDy && absDx > 30) {
      e.preventDefault();
      if (!_vGesture.seeking) _vGesture.seeking = true;
      // 每100px = 30秒
      var seekSec = Math.round(dx / 3.33);
      var targetTime = Math.max(0, Math.min(video.duration || 0, _vGesture.startTimeOffset + seekSec));
      _vgShowSeek(targetTime, seekSec);
    }
    // 垂直滑动
    else if (absDy > absDx && absDy > 20) {
      e.preventDefault();
      var ratio = -dy / (video.getBoundingClientRect().height || 400);

      if (_vGesture.isLeft) {
        // 左半屏：亮度
        var newB = Math.max(0.2, Math.min(2, _vGesture.startBrightness + ratio * 2));
        _vgSetBrightness(newB);
        _vgShowOverlay(Math.round(newB * 100) + '%', 'brightness');
      } else {
        // 右半屏：音量（首次滑动自动取消静音）
        if (video.muted) video.muted = false;
        var newV = Math.max(0, Math.min(1, _vGesture.startVolume + ratio));
        video.volume = newV;
        video.muted = newV === 0;
        _vgShowOverlay(Math.round(newV * 100) + '%', 'volume');
      }
    }
  }, { passive: false });

  video.addEventListener('touchend', function(e) {
    if (!_vgIsFullscreen()) return;
    if (_vGesture.seeking) {
      // 执行快进快退
      var t = e.changedTouches[0];
      var dx = t.clientX - _vGesture.startX;
      var seekSec = Math.round(dx / 3.33);
      var targetTime = Math.max(0, Math.min(video.duration || 0, _vGesture.startTimeOffset + seekSec));
      video.currentTime = targetTime;
      _vgHideSeek();
    }
    _vgHideOverlay();
    _vGesture.seeking = false;
  }, { passive: true });

  // 双击全屏切换（触屏）
  var _lastTap = 0;
  video.addEventListener('touchend', function(e) {
    var now = Date.now();
    if (now - _lastTap < 300) {
      toggleFullscreen();
    }
    _lastTap = now;
  }, { passive: true });

  // 双击全屏切换（PC鼠标）
  video.addEventListener('dblclick', function() {
    toggleFullscreen();
  });
}

// 进全屏时显示退出提示，退全屏时重置亮度+解锁方向
document.addEventListener('fullscreenchange', function() {
  if (document.fullscreenElement) {
    _vgShowExitHint();
  } else {
    _vgSetBrightness(1);
    try { screen.orientation.unlock(); } catch(e) {}
  }
});
document.addEventListener('webkitfullscreenchange', function() {
  if (document.webkitFullscreenElement) {
    _vgShowExitHint();
  } else {
    _vgSetBrightness(1);
  }
});

// 全屏退出提示（3秒后自动消失）
function _vgShowExitHint() {
  var id = 'vg-exit-hint';
  var el = document.getElementById(id);
  if (!el) {
    el = document.createElement('div');
    el.id = id;
    el.style.cssText = 'position:absolute;top:20px;left:50%;transform:translateX(-50%);background:rgba(0,0,0,0.7);color:#fff;padding:8px 20px;border-radius:6px;font-size:13px;z-index:60;pointer-events:none;transition:opacity 0.5s;';
    var player = document.querySelector('.detail-video-player');
    if (player) player.appendChild(el);
  }
  el.textContent = '按 Esc / F / 双击 退出全屏';
  el.style.opacity = '1';
  clearTimeout(el._timer);
  el._timer = setTimeout(function() { el.style.opacity = '0'; }, 3000);
}

function _vgGetBrightness() {
  var mask = document.getElementById('vg-brightness-mask');
  if (!mask) return 1;
  return 1 - mask.style.opacity * 1;
}

function _vgSetBrightness(val) {
  var mask = document.getElementById('vg-brightness-mask');
  if (!mask) {
    var player = document.querySelector('.detail-video-player');
    if (!player) return;
    mask = document.createElement('div');
    mask.id = 'vg-brightness-mask';
    mask.style.cssText = 'position:absolute;inset:0;background:#000;pointer-events:none;z-index:5;opacity:0;transition:opacity 0.1s;';
    player.style.position = 'relative';
    player.appendChild(mask);
  }
  var maskOpacity = Math.max(0, Math.min(0.8, (1 - val) * 1));
  mask.style.opacity = maskOpacity;
}

function _vgShowOverlay(text, type) {
  var id = 'vg-overlay';
  var el = document.getElementById(id);
  if (!el) {
    el = document.createElement('div');
    el.id = id;
    el.style.cssText = 'position:absolute;top:50%;left:50%;transform:translate(-50%,-50%);background:rgba(0,0,0,0.7);color:#fff;padding:12px 20px;border-radius:8px;font-size:1.1rem;z-index:50;pointer-events:none;transition:opacity 0.3s;';
    var player = document.querySelector('.detail-video-player');
    if (player) player.appendChild(el);
  }
  var icon = type === 'brightness' ? '☀' : '🔊';
  el.textContent = icon + ' ' + text;
  el.style.opacity = '1';
  clearTimeout(el._timer);
  el._timer = setTimeout(function() { _vgHideOverlay(); }, 1500);
}

function _vgHideOverlay() {
  var el = document.getElementById('vg-overlay');
  if (el) el.style.opacity = '0';
}

function _vgShowSeek(targetTime, seekSec) {
  var id = 'vg-seek';
  var el = document.getElementById(id);
  if (!el) {
    el = document.createElement('div');
    el.id = id;
    el.style.cssText = 'position:absolute;top:50%;left:50%;transform:translate(-50%,-50%);background:rgba(0,0,0,0.7);color:#fff;padding:10px 18px;border-radius:8px;font-size:1rem;z-index:50;pointer-events:none;white-space:nowrap;';
    var player = document.querySelector('.detail-video-player');
    if (player) player.appendChild(el);
  }
  var sign = seekSec >= 0 ? '+' : '';
  var mm = Math.floor(targetTime / 60);
  var ss = Math.floor(targetTime % 60);
  el.textContent = sign + seekSec + 's → ' + mm + ':' + _pad2(ss);
}

function _vgHideSeek() {
  var el = document.getElementById('vg-seek');
  if (el) el.style.display = 'none';
  setTimeout(function() { if (el) el.remove(); }, 100);
}

// ===== 视频进度追踪（对齐GL） =====
var _watchProgressInterval = null;
var _currentWatchId = null;

function _initWatchProgressTracker(videoType, videoId) {
  // 清除上一次的追踪
  if (_watchProgressInterval) {
    clearInterval(_watchProgressInterval);
    _watchProgressInterval = null;
  }
  _currentWatchId = videoType + '|' + videoId;

  // 等待video元素就绪后绑定
  setTimeout(function() {
    var video = document.getElementById('detail-video');
    if (!video) return;

    // 恢复上次播放进度（等metadata加载完）
    function restoreProgress() {
      if (typeof getWatchProgress !== 'function') return;
      var savedProgress = getWatchProgress(videoType, videoId);
      if (savedProgress > 0 && savedProgress < 1 && video.duration) {
        video.currentTime = savedProgress * video.duration;
      }
    }

    if (video.readyState >= 1) {
      restoreProgress();
    } else {
      video.addEventListener('loadedmetadata', restoreProgress, { once: true });
    }

    // 定时保存进度（每5秒）
    _watchProgressInterval = setInterval(function() {
      if (!video.duration || video.paused) return;
      var progress = video.currentTime / video.duration;
      if (typeof setWatchProgress === 'function') {
        setWatchProgress(videoType, videoId, Math.min(progress, 0.999));
      }
    }, 5000);

    // 播放结束时标记为100%
    video.addEventListener('ended', function() {
      if (typeof markWatched === 'function') {
        markWatched(videoType, videoId, 1);
      }
    }, { once: true });
  }, 300);
}

// ===== 播放速度控制 =====
function _initSpeedControl() {
  var speedBtns = document.querySelectorAll('.speed-btn');
  var video = document.getElementById('detail-video');
  if (!video || speedBtns.length === 0) return;

  speedBtns.forEach(function(btn) {
    btn.addEventListener('click', function() {
      var speed = parseFloat(btn.dataset.speed);
      video.playbackRate = speed;

      // 更新按钮激活状态
      speedBtns.forEach(function(b) { b.classList.remove('active'); });
      btn.classList.add('active');
    });
  });
}

// ===== 更新速度按钮激活状态（供键盘快捷键调用）=====
function _updateSpeedButton(speed) {
  var speedBtns = document.querySelectorAll('.speed-btn');
  if (speedBtns.length === 0) return;

  speedBtns.forEach(function(btn) {
    var btnSpeed = parseFloat(btn.dataset.speed);
    if (Math.abs(btnSpeed - speed) < 0.01) {
      btn.classList.add('active');
    } else {
      btn.classList.remove('active');
    }
  });
}
