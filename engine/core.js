/**
 * 尚唯云影 - 核心模块
 * 导航、路由、分类切换、通用逻辑
 * 对齐GL风格：导航历史栈、分类切换、stopAllVideos、下拉增强
 */

// ========= 设备检测 =========
var isMobile = /Android|iPhone|iPad|iPod/i.test(navigator.userAgent);
var isTV = /TV|AFT|SHARP|HISENSE|TCL|Skyworth|Changhong|LENOVO.*TV|Web0S|NetCast|Viera| BRAVIA/i.test(navigator.userAgent) || window.innerWidth >= 1920;
var _isViaBrowser = /VIA/i.test(navigator.userAgent);
// VIA浏览器也视为TV环境
if (_isViaBrowser) isTV = true;

// ========= 4大分类映射 =========
var CATEGORIES = {
  movie: { name: '电影', indexVar: 'MOVIE_INDEX', dataVar: 'MOVIE_DATA', disk: 'I' },
  tv:    { name: '电视剧', indexVar: 'TV_INDEX', dataVar: 'TV_DATA', disk: 'H' },
  anime: { name: '动画片', indexVar: 'ANIME_INDEX', dataVar: 'ANIME_DATA', disk: 'I' },
  doc:   { name: '纪录片', indexVar: 'DOC_INDEX', dataVar: 'DOC_DATA', disk: 'I' }
};

// ========= 分类颜色 =========
var CAT_COLORS = { movie: '#e62429', tv: '#4d9fff', anime: '#ff8c00', doc: '#00d4aa' };
function getCatColor(cat) { return CAT_COLORS[cat] || '#e62429'; }

// ========= 全局状态 =========
var currentPage = 'home';
var currentDetail = null;
var currentCat = 'movie';

// ========= 导航历史栈 =========
var _navHistory = [];
var _navSkipPush = false;

function _isLeafPage(pageId) {
  return ['detail', 'series', 'all', 'search', 'favorites'].indexOf(pageId) >= 0;
}

function _pushHistory(pageId) {
  try {
    history.pushState({ page: pageId, ts: Date.now() }, '');
  } catch(e) {}
}

function navGoBack() {
  // 1. 视频全屏中 → 退出全屏，不跳页
  if (_vgIsFullscreen && _vgIsFullscreen()) {
    if (document.exitFullscreen) document.exitFullscreen();
    else if (document.webkitExitFullscreen) document.webkitExitFullscreen();
    else if (document.msExitFullscreen) document.msExitFullscreen();
    return;
  }
  // 2. 视频播放中 → 停止视频，留在详情页
  var video = document.getElementById('detail-video');
  if (video && !video.paused && video.src) {
    video.pause();
    return;
  }
  // 3. 正常导航回退
  if (_navHistory.length > 0) {
    var prev = _navHistory.pop();
    _navSkipPush = true;
    showPage(prev);
    _navSkipPush = false;
  } else {
    showPage('home');
  }
}

// 拦截 Android 系统返回键（popstate）
window.addEventListener('popstate', function(e) {
  // popstate 触发说明 history 已退了一步，我们要用应用内逻辑决定去哪
  // 重新 push 一个 state 避免 history 耗尽后跳出 WebView
  _pushHistory(currentPage);
  navGoBack();
});

function _updateNavHomeLink() {
  var el = document.getElementById('nav-home-link');
  if (!el) return;
  if (_navHistory.length > 0) {
    el.textContent = '\u2190 \u8fd4\u56de';
    el.setAttribute('onclick', 'navGoBack()');
  } else {
    el.textContent = '\u9996\u9875';
    el.setAttribute('onclick', "showPage('home')");
  }
}

// ========= 页面路由 =========
function showPage(page) {
  closeAllDropdowns();
  stopAllVideos();

  var currentActive = document.querySelector('.page.active');
  var currentPageId = currentActive ? currentActive.id.replace('page-', '') : '';

  if (currentActive && currentActive.id === 'page-detail' && page !== 'detail') {
    var detailEl = document.getElementById('detail-content');
    if (detailEl) detailEl.innerHTML = '';
  }

  if (!_navSkipPush && currentPageId && currentPageId !== page) {
    if (_isLeafPage(page)) {
      _navHistory.push(currentPageId);
    } else {
      _navHistory = [];
    }
  }

  document.querySelectorAll('.page').forEach(function(p) { p.classList.remove('active'); });
  var el = document.getElementById('page-' + page);
  if (el) el.classList.add('active');
  currentPage = page;

  // 每次页面切换都 push 一个 history state，确保系统返回键能被 popstate 拦截
  if (!_navSkipPush) {
    _pushHistory(page);
  }

  document.querySelectorAll('.nav-link').forEach(function(l) { l.classList.remove('active'); });
  var homeLink = document.getElementById('nav-home-link');
  if (page === 'home' && homeLink) homeLink.classList.add('active');

  _updateNavHomeLink();
  window.scrollTo(0, 0);

  // TV端：渲染完成后启用焦点导航（延迟等待DOM更新）
  if (isTV) {
    _tvFocusCardIdx = 0;
    setTimeout(function() { _tvFocusEnable(); }, 150);
  }
}

// ========= 同步导航状态到指定分类 =========
function syncNavToCat(cat) {
  currentCat = cat;
  applyCatColor(cat);
  document.querySelectorAll('.cat-badge-nav').forEach(function(b) {
    b.classList.toggle('active', b.dataset.cat === cat);
  });
  var stamp = document.getElementById('nav-cat-badge');
  if (stamp) {
    stamp.dataset.cat = cat;
    stamp.textContent = CATEGORIES[cat].name;
  }
}

// ========= 分类切换（按需加载，回调模式） =========
function switchCat(cat, callback) {
  if (!CATEGORIES[cat]) return;
  syncNavToCat(cat);

  // 确保该分类数据已加载（DataLoader.load 现在是回调模式）
  if (!DataLoader.isLoaded(cat)) {
    DataLoader.load(cat, function(err) {
      if (!err) {
        // 刷新导航栏下拉（补全该分类的系列列表）
        _rebuildCategoryDropdown();
        // 重新渲染首页该分类区域
        if (typeof renderHomePage === 'function') renderHomePage();
      }
      _switchCatScroll(cat);
      if (callback) callback(err);
    });
    return;
  }

  _switchCatScroll(cat);
  if (callback) callback(null);
}

function _switchCatScroll(cat) {
  // 如果不在首页，先切回首页（showPage 会 scrollTo(0,0)）
  if (currentPage !== 'home') {
    showPage('home');
  }

  var section = document.getElementById(cat + '-section');
  if (section) {
    // Android 4.4 不支持 scrollIntoView({behavior:'smooth'})，降级为即时滚动
    try { section.scrollIntoView({ behavior: 'smooth', block: 'start' }); } catch(e) { section.scrollIntoView(true); }
  }
}

// ========= 下拉菜单 =========
function closeAllDropdowns() {
  document.querySelectorAll('.dropdown-content.visible').forEach(function(d) {
    d.classList.remove('visible');
  });
}

function toggleDropdown(el) {
  var content;
  if (el.classList && el.classList.contains('dropdown')) {
    content = el.querySelector('.dropdown-content');
  } else if (el.querySelector) {
    content = el.querySelector('.dropdown-content');
  } else {
    return;
  }
  if (!content) return;
  var wasVisible = content.classList.contains('visible');
  closeAllDropdowns();
  if (!wasVisible) content.classList.add('visible');
}

// ========= 导航栏初始化 =========
function initNav() {
  _rebuildCategoryDropdown();

  if (typeof LIBRARY_STATS !== 'undefined') {
    setText('stat-movies', LIBRARY_STATS.movieCount || 0);
    setText('stat-tv-shows', LIBRARY_STATS.tvShowCount || 0);
    setText('stat-anime', LIBRARY_STATS.animeCount || 0);
    setText('stat-doc', LIBRARY_STATS.docCount || 0);
  }
}

// ========= 重建分类下拉菜单（数据就绪后调用） =========
function _rebuildCategoryDropdown() {
  var dropdown = document.getElementById('category-dropdown');
  if (!dropdown) return;
  var html = '';
  ['movie', 'tv', 'anime', 'doc'].forEach(function(cat) {
    var catConfig = CATEGORIES[cat];
    var color = getCatColor(cat);
    var count = typeof LIBRARY_STATS !== 'undefined' ?
      (cat === 'movie' ? LIBRARY_STATS.movieCount :
       cat === 'tv' ? LIBRARY_STATS.tvShowCount :
       cat === 'anime' ? LIBRARY_STATS.animeCount : LIBRARY_STATS.docCount) : 0;

    html += '<div class="dropdown-item" style="color:' + color + ';font-weight:700;padding:10px 14px;border-bottom:1px solid rgba(255,255,255,0.08);" onclick="showAllItems(\'' + cat + '\')">' +
      '<span>\u5168\u90e8' + catConfig.name + '</span>' +
      '<span style="font-weight:400;font-size:12px;color:#999;">' + count + '\u90e8</span></div>';

    // 只渲染已加载数据的分类系列列表
    if (DataLoader.isLoaded(cat) && typeof window[catConfig.indexVar] !== 'undefined') {
      var index = window[catConfig.indexVar];
      var keys = Object.keys(index);
      keys.sort(function(a, b) { return (index[b].count || 0) - (index[a].count || 0); });
      keys.forEach(function(name) {
        var s = index[name];
        var displayName = getSeriesDisplayName(cat, name);
        html += '<div class="dropdown-item" onclick="showSeriesPage(\'' + cat + '\',\'' + escapeAttr(name) + '\')">' +
          '<span class="dropdown-item-name"><span style="display:inline-block;width:8px;height:8px;border-radius:2px;background:' + color + ';margin-right:6px;vertical-align:middle;"></span>' + escapeAttr(displayName) + '</span>' +
          '<span class="dropdown-item-count">' + (s.count || 0) + '\u90e8</span></div>';
      });
    }
  });
  dropdown.innerHTML = html;
}

// ========= 路径函数 =========
function diskToHttp(path) {
  var http = path.replace(/\\/g, '/').replace(/^([A-Z]):\//, '/media/$1/');
  var parts = http.split('/');
  return parts.map(function(p) { return encodeURIComponent(p); }).join('/');
}

function httpToLocal(httpPath) {
  // /media/H/xxx → H:/xxx
  var decoded = decodeURIComponent(httpPath);
  return decoded.replace(/^\/media\/([A-Z])\//, '$1:/');
}

// ========= 本机播放（XMLHttpRequest，兼容 Android 4.4） =========
// APK 内通过 intent:// 协议调用手机播放器，PC 端走 KMPlayer
var _isAPK = (window.__SHANGWEI_APK === true);

function localPlay(filePath) {
  // APK 内：用视频的 HTTP URL 调手机播放器
  if (_isAPK) {
    var mediaUrl = filePath;
    // 本地路径 → HTTP URL
    if (filePath.indexOf('/media/') === 0) {
      mediaUrl = filePath; // 已经是 /media/X/... 相对路径
    } else if (/^[A-Z]:/i.test(filePath)) {
      // X:/... → /media/X/...
      mediaUrl = filePath.replace(/^([A-Z]):/i, '/media/$1');
    }
    // 构造完整 HTTP URL
    var base = window.location.origin;
    var videoUrl = base + mediaUrl.replace(/\/+/g, '/');
    // 通过自定义协议让 APK WebViewClient 拦截，调用手机播放器
    window.location.href = 'localplay://' + encodeURIComponent(videoUrl);
    return;
  }
  // PC 端：调 KMPlayer
  if (filePath.indexOf('/media/') === 0) {
    filePath = httpToLocal(filePath);
  }
  var xhr = new XMLHttpRequest();
  xhr.open('GET', '/localplay?path=' + encodeURIComponent(filePath), true);
  xhr.onreadystatechange = function() {
    if (xhr.readyState === 4 && xhr.status === 200) {
      try {
        var d = JSON.parse(xhr.responseText);
        if (!d.ok) console.error('[localPlay] failed:', d.error);
      } catch(e) { console.error('[localPlay] parse error:', e); }
    }
  };
  xhr.send();
}

// ========= 更新数据（XMLHttpRequest，兼容 Android 4.4） =========
function runUpdate() {
  var btn = document.getElementById('nav-update-btn');
  if (btn.dataset.running === '1') return;
  btn.dataset.running = '1';
  btn.innerHTML = '更新中...';
  btn.style.color = '#e62429';

  var xhr = new XMLHttpRequest();
  xhr.open('POST', '/api/update', true);
  xhr.onreadystatechange = function() {
    if (xhr.readyState !== 4) return;
    try {
      var data = JSON.parse(xhr.responseText);
      if (data.success) {
        btn.innerHTML = '完成';
        btn.style.color = '#4dff88';
        setTimeout(function() { location.reload(); }, 1500);
      } else {
        _runUpdateResetBtn(btn);
        console.error('[SETH] Update failed:', data.error || data.output);
        btn.style.color = '#ff4444';
        setTimeout(function() { btn.style.color = ''; }, 3000);
      }
    } catch(e) {
      _runUpdateResetBtn(btn);
      btn.style.color = '#ff4444';
      console.error('[SETH] Update error:', e);
      setTimeout(function() { btn.style.color = ''; }, 3000);
    }
  };
  xhr.onerror = function() {
    _runUpdateResetBtn(btn);
    btn.style.color = '#ff4444';
    setTimeout(function() { btn.style.color = ''; }, 3000);
  };
  xhr.send();
}

function _runUpdateResetBtn(btn) {
  btn.innerHTML = '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21.5 2v6h-6M2.5 22v-6h6M2 11.5a10 10 0 0 1 18.8-4.3M22 12.5a10 10 0 0 1-18.8 4.3"/></svg>';
  btn.dataset.running = '0';
}

function resourceUrl(diskPath, filename) {
  if (!filename) return '';
  var normFile = filename.replace(/\\/g, '/');

  // 下载的海报/背景图：poster字段格式为 "posters/tv/xxx.jpg" 或 "fanart/movie/xxx.jpg"
  // 这些文件在项目根目录下，直接用相对路径（不需要 diskPath）
  if (normFile.indexOf('posters/') === 0 || normFile.indexOf('fanart/') === 0) {
    return normFile.split('/').map(function(p) { return encodeURIComponent(p); }).join('/');
  }

  if (!diskPath) return '';
  var dir = diskPath.replace(/[\\\/]+$/, '');
  if (normFile.indexOf('/') >= 0) {
    var fileParts = normFile.split('/');
    return diskToHttp(dir) + '/' + fileParts.map(function(p) { return encodeURIComponent(p); }).join('/');
  }
  return diskToHttp(dir) + '/' + encodeURIComponent(filename);
}

function getSeriesPosterUrl(cat, seriesName) {
  var catConfig = CATEGORIES[cat];
  if (typeof window[catConfig.indexVar] === 'undefined') return '';
  var index = window[catConfig.indexVar];
  var s = index[seriesName];
  if (!s || !s.samplePosterFile) return '';

  // posters/ 前缀的在线下载海报不需要 dir，直接走 resourceUrl
  if (s.samplePosterFile.indexOf('posters/') === 0) {
    return resourceUrl('', s.samplePosterFile);
  }

  if (!s.dir) return '';

  var basePath = '';
  if (cat === 'movie') basePath = 'I:/电影/' + s.dir;
  else if (cat === 'tv') basePath = 'H:/电视剧/' + s.dir;
  else if (cat === 'anime') basePath = 'I:/动画片/' + s.dir;
  else if (cat === 'doc') basePath = 'I:/纪录片/' + s.dir;

  return resourceUrl(basePath, s.samplePosterFile);
}

// ========= 系列名清洗 =========
var _cleanCache = {};
function cleanSeriesName(name) {
  if (_cleanCache[name] !== undefined) return _cleanCache[name];
  var s = name;

  var bracketName = s.match(/【([^】]+)】/);
  if (bracketName) { s = bracketName[1]; }

  s = s.replace(/[【\[]\s*(?:www\.)?[^】\]]*?(?:\.com|\.cn|\.tv|\.me|\.mx|\.org|\.net)[^】\]]*?[】\]]\s*/g, '');
  s = s.replace(/\[\s*[^]]*?(?:高清电影之家|mkvhome|gaoqing\.tv)[^]]*?\]\s*/g, '');
  s = s.replace(/[【\[][\d]*(?:动画片|纪录片|电视剧|电影|剧情|纪录|TV|道兰)[^】\]]*?[】\]]\s*/g, '');
  s = s.replace(/[【\[《][^】\]》]*?[】\]》]/g, '');

  var dotMatch = s.match(/^([\u4e00-\u9fff\u3000-\u303f\uff00-\uffef\w\s]+?)(?:\.[A-Za-z].*)?$/);
  if (dotMatch && dotMatch[1].trim().length >= 2) {
    s = dotMatch[1].trim();
  }

  s = s.replace(/\s*[-\u2013\u2014]\s*[A-Z][A-Za-z0-9()\uff08\uff09]*$/g, '');
  s = s.replace(/\.\s*S\d+.*$/gi, '');

  // 前导序号
  s = s.replace(/^\d{2}\.\d{2}\s*/, '');
  s = s.replace(/^A\d{3}\s*/, '');
  s = s.replace(/^\d+\.\s*/, '');

  // CCTV/频道前缀
  s = s.replace(/^CCTV\d*[.\uff0e\-]+/, '');

  // 补全完整版
  s = s.replace(/^补全完整版/, '');

  // 文件大小+描述
  s = s.replace(/\s*\d+[\.\d]*\s*(MB|GB|G|TB|T)\b.*$/gi, '');

  // @用户名
  s = s.replace(/@\S+/, '');

  // 特定描述词
  s = s.replace(/(宽屏亮丽版|慈悲得道篇|最新高清晰|破.*?纪录.*?元|简繁英字幕|中日双语字幕|英语中字)/g, '');

  // 年份+类型描述
  s = s.replace(/\d{4}年?.*?(电影|电视剧|动画|纪录片|剧情).*$/, '');

  // 下划线+描述
  s = s.replace(/[_\s]+CCTV.*$/, '');
  s = s.replace(/[_\s]+纪录片.*$/, '');

  // 点号+年份
  s = s.replace(/\.\d{4}.*$/, '');

  // DVDRip
  s = s.replace(/\.DVDRip$/i, '');

  // 末尾括号
  s = s.replace(/\s*[\(\uff08][^\)\uff09]*[\)\uff09]\s*$/g, '');

  // 特殊映射
  s = s.replace(/^LS$/, '连载动画');
  s = s.replace(/^20240531$/, '哆啦A梦');
  s = s.replace(/^Teenage Mutant Ninja Turtles$/, '忍者神龟');
  s = s.replace(/^The Smurfs Complete Seasons 1-9 dvdrip$/, '蓝精灵');

  s = s.replace(/\s*[.\uff0e,\uff0c\u3001\-–—:：]\s*$/g, '');
  s = s.replace(/\s{2,}/g, ' ');
  s = s.trim();

  var result = s || name;
  _cleanCache[name] = result;
  return result;
}

function getSeriesDisplayName(cat, name) {
  var catConfig = CATEGORIES[cat];
  if (typeof window[catConfig.indexVar] !== 'undefined') {
    var index = window[catConfig.indexVar];
    if (index[name] && index[name].displayName) {
      return index[name].displayName;
    }
  }
  return cleanSeriesName(name);
}

function getSeriesColor(name) {
  var hash = 0;
  for (var i = 0; i < name.length; i++) hash = name.charCodeAt(i) + ((hash << 5) - hash);
  var hue = Math.abs(hash) % 360;
  return 'hsl(' + hue + ', 60%, 50%)';
}

// ========= 搜索（按需加载数据，回调模式） =========
var _searchPending = false;
function handleSearch() {
  var input = document.getElementById('search-input');
  var query = input.value.trim().toLowerCase();
  var dropdown = document.getElementById('search-dropdown');
  if (!query || query.length < 1) { dropdown.classList.remove('visible'); return; }

  // 确保所有分类数据已加载（搜索需要跨分类检索）
  if (!DataLoader.isLoaded('tv') || !DataLoader.isLoaded('anime') || !DataLoader.isLoaded('doc')) {
    if (!_searchPending) {
      _searchPending = true;
      dropdown.innerHTML = '<div class="search-item"><span class="search-item-meta">加载中...</span></div>';
      dropdown.classList.add('visible');
      DataLoader.loadAll(function() {
        _searchPending = false;
        handleSearch(); // 加载完成后重新执行搜索
      });
      return;
    }
  }

  _doSearch(query);
}

function _doSearch(query) {
  var dropdown = document.getElementById('search-dropdown');
  var results = [];
  ['movie', 'tv', 'anime', 'doc'].forEach(function(cat) {
    var catConfig = CATEGORIES[cat];
    if (typeof window[catConfig.dataVar] === 'undefined') return;
    var data = window[catConfig.dataVar];
    Object.keys(data).forEach(function(seriesName) {
      var series = data[seriesName];
      var items = series.movies || series.shows || [];
      items.forEach(function(item) {
        var match = (item.title || '').toLowerCase().indexOf(query) >= 0 ||
                    (item.titleEn || '').toLowerCase().indexOf(query) >= 0 ||
                    (item.actor || '').toLowerCase().indexOf(query) >= 0 ||
                    String(item.year || '').indexOf(query) >= 0;
        if (match) {
          item._seriesPath = series.path || item.path || '';
          item._seriesName = seriesName;
          results.push({cat: cat, series: seriesName, data: item});
        }
      });
    });
  });

  if (results.length === 0) {
    dropdown.innerHTML = '<div class="search-item"><span class="search-item-meta">\u65e0\u7ed3\u679c</span></div>';
  } else {
    var html = '';
    results.slice(0, 20).forEach(function(r) {
      var catName = CATEGORIES[r.cat].name;
      var color = getCatColor(r.cat);
      html += '<div class="search-item" onclick="openDetail(\'' + r.cat + '\',\'' + escapeAttr(r.series) + '\',\'' + escapeAttr(r.data.title || r.data.dir || '') + '\')">' +
        '<span class="search-item-title">' +
        '<span style="display:inline-block;width:6px;height:6px;border-radius:2px;background:' + color + ';margin-right:4px;"></span>' +
        (r.data.title || '') + '</span>' +
        '<span class="search-item-meta">' + catName + ' | ' + (r.data.year || '') + ' | ' + (r.data.actor || '') + '</span></div>';
    });
    dropdown.innerHTML = html;
  }
  dropdown.classList.add('visible');
}

// ========= stopAllVideos =========
function stopAllVideos() {
  var videos = document.querySelectorAll('video');
  videos.forEach(function(v) {
    v.pause();
    if (v.src && !v.dataset.src) {
      v.dataset.src = v.src;
    }
    v.removeAttribute('src');
    v.load();
  });
}

// ========= 浮动播放器 =========
function openFloatingPlayer(url, title) {
  var container = document.getElementById('floating-player');
  var video = document.getElementById('floating-video');
  setText('floating-player-title', title || '\u64ad\u653e\u4e2d');
  video.src = url;
  video.play();
  container.style.display = 'block';
}

function closeFloatingPlayer() {
  var container = document.getElementById('floating-player');
  var video = document.getElementById('floating-video');
  video.pause();
  video.src = '';
  container.style.display = 'none';
}

// ========= 工具函数 =========
function setText(id, text) { var el = document.getElementById(id); if (el) el.textContent = text; }
function escapeAttr(str) { return String(str).replace(/'/g, "\\'").replace(/"/g, '&quot;').replace(/</g, '&lt;').replace(/>/g, '&gt;'); }
function formatSize(bytes) {
  if (!bytes) return '';
  if (bytes < 1073741824) return (bytes / 1048576).toFixed(0) + 'MB';
  return (bytes / 1073741824).toFixed(1) + 'GB';
}

// ========= 图片查看器触摸手势 =========
var _pvTouchStartX = 0, _pvTouchStartY = 0, _pvTouchMoved = false;
function _pvTouchStart(e) {
  if (e.touches.length === 1) {
    _pvTouchStartX = e.touches[0].clientX;
    _pvTouchStartY = e.touches[0].clientY;
    _pvTouchMoved = false;
  }
}
function _pvTouchMove(e) {
  _pvTouchMoved = true;
}
function _pvTouchEnd(e) {
  if (!_pvTouchMoved) return;
  var dx = e.changedTouches[0].clientX - _pvTouchStartX;
  if (Math.abs(dx) > 80 && _photoViewerPhotos.length > 1) {
    if (dx > 0) photoViewerPrev(); else photoViewerNext();
  }
}

// ======== 视频播放速度控制（TV遥控器：菜单键 + ←→）============
window._speedOverlayVisible = false;
window._speedOptions = [0.5, 0.75, 1.0, 1.25, 1.5, 2.0];
window._speedIndex = 2; // 默认1.0x

window._tvHideSpeed = function() {
  window._speedOverlayVisible = false;
  var el = document.getElementById('speed-overlay');
  if (el) el.style.display = 'none';
};

window._tvRenderSpeedOverlay = function() {
  var video = document.getElementById('detail-video');
  if (!video) return;
  var el = document.getElementById('speed-overlay');
  if (!el) {
    el = document.createElement('div');
    el.id = 'speed-overlay';
    el.style.cssText = 'position:fixed;bottom:80px;left:50%;transform:translateX(-50%);' +
      'background:rgba(0,0,0,0.85);color:#fff;padding:12px 20px;border-radius:10px;' +
      'display:flex;gap:10px;z-index:9999;font-size:18px;';
    document.body.appendChild(el);
  }
  el.style.display = 'flex';
  el.innerHTML = '';
  for (var i = 0; i < window._speedOptions.length; i++) {
    var spd = window._speedOptions[i];
    var btn = document.createElement('span');
    btn.textContent = spd + 'x';
    btn.style.cssText = 'padding:6px 12px;border-radius:6px;cursor:pointer;font-weight:' +
      (i === window._speedIndex ? 'bold' : 'normal') + ';background:' +
      (i === window._speedIndex ? '#e62429' : 'transparent') + ';';
    (function(idx) {
      btn.addEventListener('click', function() {
        window._speedIndex = idx;
        video.playbackRate = window._speedOptions[idx];
        window._tvRenderSpeedOverlay();
        if (typeof _updateSpeedButton === 'function') _updateSpeedButton(window._speedOptions[idx]);
      });
    })(i);
    el.appendChild(btn);
  }
  clearTimeout(el._timer);
  el._timer = setTimeout(function() { window._tvHideSpeed(); }, 5000);
};

window._tvToggleSpeed = function() {
  var video = document.getElementById('detail-video');
  if (!video || video.readyState === 0) return;
  if (window._speedOverlayVisible) {
    window._tvHideSpeed();
  } else {
    window._speedOverlayVisible = true;
    for (var i = 0; i < window._speedOptions.length; i++) {
      if (Math.abs(window._speedOptions[i] - video.playbackRate) < 0.01) {
        window._speedIndex = i; break;
      }
    }
    window._tvRenderSpeedOverlay();
  }
};
// ======== 键盘事件（增强：图片查看器ESC关闭，左右切换 + TV遥控器导航） =========
function initKeyboard() {
  document.addEventListener('keydown', function(e) {
    if (e.key === '/' && document.activeElement.tagName !== 'INPUT' && document.activeElement.tagName !== 'TEXTAREA') {
      e.preventDefault();
      var input = document.getElementById('search-input');
      if (input) input.focus();
    }
    if (e.key === 'Escape') {
      closeAllDropdowns();
      var sd = document.getElementById('search-dropdown');
      if (sd) sd.classList.remove('visible');
      closePhotoViewer();
    }
    // 图片查看器键盘导航
    var overlay = document.getElementById('photo-overlay');
    if (overlay && overlay.classList.contains('active')) {
      if (e.key === 'ArrowLeft') photoViewerPrev();
      if (e.key === 'ArrowRight') photoViewerNext();
      if (e.key === '+' || e.key === '=') photoViewerZoom(0.3);
      if (e.key === '-') photoViewerZoom(-0.3);
      return;
    }
    // 视频全屏切换（F键）
    if (e.key === 'f' || e.key === 'F') {
      if (document.fullscreenElement || document.webkitFullscreenElement) {
        if (document.exitFullscreen) document.exitFullscreen();
        else if (document.webkitExitFullscreen) document.webkitExitFullscreen();
      } else if (document.querySelector('.detail-video-player')) {
        toggleFullscreen();
      }
    }
    // 视频播放速度控制（TV遥控器：菜单键显示/隐藏速度面板，←→调速度）
    // 菜单键（context menu）切换速度面板
    if (e.keyCode === 93 || e.keyCode === 229 || e.key === 'ContextMenu') {
      var video = document.getElementById('detail-video');
      if (video && video.readyState > 0) {
        e.preventDefault();
        _tvToggleSpeed();
        return;
      }
    }
    // ← 减速
    if ((e.keyCode === 37 || e.key === 'ArrowLeft') && window._speedOverlayVisible) {
      e.preventDefault();
      window._speedIndex = Math.max(0, window._speedIndex - 1);
      var video = document.getElementById('detail-video');
      if (video) video.playbackRate = window._speedOptions[window._speedIndex];
      _tvRenderSpeedOverlay();
      if (typeof _updateSpeedButton === 'function') _updateSpeedButton(window._speedOptions[window._speedIndex]);
      return;
    }
    // → 加速
    if ((e.keyCode === 39 || e.key === 'ArrowRight') && window._speedOverlayVisible) {
      e.preventDefault();
      window._speedIndex = Math.min(window._speedOptions.length - 1, window._speedIndex + 1);
      var video = document.getElementById('detail-video');
      if (video) video.playbackRate = window._speedOptions[window._speedIndex];
      _tvRenderSpeedOverlay();
      if (typeof _updateSpeedButton === 'function') _updateSpeedButton(window._speedOptions[window._speedIndex]);
      return;
    }
  });

  // ========= TV 遥控器方向键导航 =========
  if (isTV) {
    document.addEventListener('keydown', function(e) {
      var isCardFocused = document.activeElement && document.activeElement.classList.contains('card');
      var isEpFocused = document.activeElement && (document.activeElement.classList.contains('ep-btn') || document.activeElement.classList.contains('episode-btn'));
      var isBtnFocused = document.activeElement && (document.activeElement.classList.contains('detail-play-btn') || document.activeElement.classList.contains('detail-localplay-btn'));

      switch (e.key) {
        case 'ArrowUp':
          if (isCardFocused) { e.preventDefault(); _tvFocusMove('up'); return; }
          break;
        case 'ArrowDown':
          if (isCardFocused) { e.preventDefault(); _tvFocusMove('down'); return; }
          break;
        case 'ArrowLeft':
          if (isCardFocused) { e.preventDefault(); _tvFocusMove('left'); return; }
          if (isEpFocused) { e.preventDefault(); _tvFocusMoveLinear(-1); return; }
          break;
        case 'ArrowRight':
          if (isCardFocused) { e.preventDefault(); _tvFocusMove('right'); return; }
          if (isEpFocused) { e.preventDefault(); _tvFocusMoveLinear(1); return; }
          break;
        case 'Enter':
          // 详情页按钮聚焦→触发点击
          if (isBtnFocused) {
            e.preventDefault();
            document.activeElement.click();
            return;
          }
          // 卡片聚焦→触发点击
          if (isCardFocused) {
            e.preventDefault();
            document.activeElement.click();
            return;
          }
          // 选集按钮聚焦→触发点击
          if (isEpFocused) {
            e.preventDefault();
            document.activeElement.click();
            return;
          }
          break;
        case 'Backspace':
        case 'Escape':
          e.preventDefault();
          navGoBack();
          break;
      }
    });
  }
}

// ========= TV 遥控器焦点导航系统 =========
var _tvFocusCardIdx = 0;
var _tvFocusCardsPerRow = 6;

function _tvFocusGetContainer() {
  if (currentPage === 'home') {
    // 在首页，找第一个可见的分类 grid
    var sections = document.querySelectorAll('.home-section');
    for (var i = 0; i < sections.length; i++) {
      var sec = sections[i];
      if (sec.style.display !== 'none') {
        return sec.querySelector('.card-grid');
      }
    }
    return document.querySelector('.card-grid');
  }
  if (currentPage === 'series') return document.getElementById('series-page-grid');
  if (currentPage === 'all') return document.getElementById('all-page-grid');
  if (currentPage === 'favorites') return document.getElementById('fav-page-grid');
  if (currentPage === 'search') return document.getElementById('search-page-grid');
  if (currentPage === 'detail') return document.querySelector('.ep-grid, .episode-list');
  return document.querySelector('.card-grid');
}

function _tvFocusEnable() {
  var container = _tvFocusGetContainer();
  if (!container) return;

  // 分类导航徽章也可聚焦
  var badges = document.querySelectorAll('.cat-badge-nav');
  for (var b = 0; b < badges.length; b++) {
    badges[b].setAttribute('tabindex', '0');
  }

  // 导航链接也可聚焦
  var navLinks = document.querySelectorAll('.nav-link');
  for (var n = 0; n < navLinks.length; n++) {
    navLinks[n].setAttribute('tabindex', '0');
  }

  // 详情页选集按钮聚焦
  var epBtns = container.querySelectorAll('.ep-btn, .episode-btn');
  if (epBtns.length > 0) {
    for (var i = 0; i < epBtns.length; i++) {
      epBtns[i].setAttribute('tabindex', '0');
    }
  }

  // 详情页播放按钮聚焦
  var playBtns = document.querySelectorAll('.detail-play-btn, .detail-localplay-btn, .play-btn');
  for (var j = 0; j < playBtns.length; j++) {
    playBtns[j].setAttribute('tabindex', '0');
  }

  var cards = container.querySelectorAll('.card');
  if (cards.length === 0) {
    // 详情页没有卡片→聚焦第一个播放按钮
    if (playBtns.length > 0) playBtns[0].focus();
    return;
  }

  // 给所有卡片加 tabindex
  for (var c = 0; c < cards.length; c++) {
    cards[c].setAttribute('tabindex', '0');
  }

  // 计算每行卡片数
  var cardWidth = cards[0].offsetWidth + _getMarginH(cards[0]);
  var gridWidth = container.clientWidth;
  _tvFocusCardsPerRow = Math.max(1, Math.floor(gridWidth / Math.max(cardWidth, 1)));

  // 聚焦第一个或恢复上次位置
  _tvFocusCardIdx = Math.min(_tvFocusCardIdx, cards.length - 1);
  cards[_tvFocusCardIdx].focus();
}

function _getMarginH(el) {
  var s = window.getComputedStyle(el);
  return (parseInt(s.marginLeft, 10) || 0) + (parseInt(s.marginRight, 10) || 0);
}

function _tvFocusMove(direction) {
  var container = _tvFocusGetContainer();
  if (!container) return;

  var cards = container.querySelectorAll('.card');
  var total = cards.length;
  if (total === 0) return;

  var perRow = _tvFocusCardsPerRow || 6;
  var idx = _tvFocusCardIdx;
  var newIdx = idx;

  switch (direction) {
    case 'up':    newIdx = Math.max(0, idx - perRow); break;
    case 'down':  newIdx = Math.min(total - 1, idx + perRow); break;
    case 'left':  newIdx = (idx % perRow > 0) ? idx - 1 : idx; break;
    case 'right': newIdx = (idx + 1 < total && (idx + 1) % perRow > 0) ? idx + 1 : idx; break;
  }

  if (newIdx !== idx && newIdx >= 0 && newIdx < total) {
    _tvFocusCardIdx = newIdx;
    cards[newIdx].focus();
    cards[newIdx].scrollIntoView(false);
  }
}

// 线性移动焦点（用于选集按钮等非网格布局）
function _tvFocusMoveLinear(delta) {
  var container = _tvFocusGetContainer();
  if (!container) return;

  var items;
  if (currentPage === 'detail') {
    items = container.querySelectorAll('.ep-btn, .episode-btn');
  } else {
    return;
  }

  var total = items.length;
  if (total === 0) return;

  var currentIdx = -1;
  for (var i = 0; i < total; i++) {
    if (items[i] === document.activeElement) { currentIdx = i; break; }
  }
  if (currentIdx < 0) return;

  var newIdx = Math.max(0, Math.min(total - 1, currentIdx + delta));
  if (newIdx !== currentIdx) {
    items[newIdx].focus();
    items[newIdx].scrollIntoView(false);
  }
}

// ========= CSS变量映射（桌面端通过CSS变量切换主题色，TV端无效但无害） =========
function applyCatColor(cat) {
  var color = getCatColor(cat);
  try {
    document.documentElement.style.setProperty('--primary-color', color);
    document.documentElement.style.setProperty('--primary-hover', color);
  } catch(e) {
    // Android 4.4 不支持CSS变量，静默忽略
  }
}

// ========= 全局点击关闭下拉 =========
function initGlobalClick() {
  document.addEventListener('click', function(e) {
    if (!e.target.closest('.dropdown')) {
      closeAllDropdowns();
    }
    if (!e.target.closest('.nav-search')) {
      var sd = document.getElementById('search-dropdown');
      if (sd) sd.classList.remove('visible');
    }
  });
}

// ========= 初始化 =========
var _appInited = false;
function initApp() {
  if (_appInited) return;
  _appInited = true;
  // 初始 history state，确保系统返回键不会跳出 WebView
  _pushHistory('home');
  initNav();
  initKeyboard();
  initGlobalClick();
  applyCatColor('movie');
  if (typeof renderHomePage === 'function') renderHomePage();
  if (typeof updateFavCount === 'function') updateFavCount();
}

if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', initApp);
} else {
  initApp();
}
