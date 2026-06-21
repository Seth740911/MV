/* ============================================
   尚唯云册 4.0 - 双导航栏控制器
   效仿尚唯云色：第一栏彩色徽章 + 第二栏下拉分类
   ============================================ */

// 第一导航栏配置：每个大类的子导航
var FIRST_NAV_CONFIG = {
  photo: {
    label: 'PHOTO',
    links: [
      { id: 'all', label: '全部照片', type: 'link' },
      { id: 'ownership', label: '归属', type: 'dropdown', items: [
        { id: 'owner-S', label: 'Seth' },
        { id: 'owner-R', label: 'Roger' },
        { id: 'owner-SR', label: 'Seth & Roger' }
      ]},
      { id: 'event', label: '事件', type: 'dropdown', items: 'TAGS_EVENT' },
      { id: 'year', label: '年份', type: 'dropdown', items: 'YEARS' },
      { id: 'random', label: '随机' },
      { id: 'memory', label: '回忆' }
    ]
  },
  life: {
    label: 'LIFE',
    links: [
      { id: 'life-all', label: '全部', type: 'link' },
      { id: 'life-event', label: '事件', type: 'dropdown', items: 'TAGS_EVENT' },
      { id: 'life-year', label: '年份', type: 'dropdown', items: 'YEARS' },
      { id: 'life-ownership', label: '归属', type: 'dropdown', items: [
        { id: 'owner-S', label: 'Seth' },
        { id: 'owner-R', label: 'Roger' },
        { id: 'owner-SR', label: 'Seth & Roger' }
      ]}
    ]
  },
  memory: {
    label: 'MEMORY',
    links: [
      { id: 'mem-start', label: '开始回忆' },
      { id: 'mem-year', label: '按年份', type: 'dropdown', items: 'YEARS' },
      { id: 'mem-event', label: '按事件', type: 'dropdown', items: 'TAGS_EVENT' }
    ]
  },
  people: {
    label: 'PEOPLE',
    links: [
      { id: 'people-all', label: '全部', type: 'link' },
      { id: 'people-tag', label: '人物', type: 'dropdown', items: 'TAGS_PEOPLE' }
    ]
  },
  place: {
    label: 'PLACE',
    links: [
      { id: 'place-all', label: '全部', type: 'link' },
      { id: 'place-tag', label: '地点', type: 'dropdown', items: 'TAGS_PLACE' }
    ]
  },
  doc: {
    label: 'DOC',
    links: [
      { id: 'doc-all', label: '全部文档', type: 'link' },
      { id: 'doc-type', label: '类型', type: 'dropdown', items: [
        { id: 'doc-cert', label: '证件' },
        { id: 'doc-card', label: '卡' },
        { id: 'doc-medical', label: '医疗' }
      ]}
    ]
  },
  tool: {
    label: 'TOOL',
    links: [
      { id: 'tool-upload', label: '上传' },
      { id: 'tool-scan', label: '扫描' },
      { id: 'tool-stats', label: '统计' }
    ]
  }
};

// 事件类标签（从 albumTagDefs 动态提取）
var EVENT_TAGS = [
  { id: 'tag-聚餐', label: '聚餐' },
  { id: 'tag-家宴', label: '家宴' },
  { id: 'tag-参加婚礼', label: '参加婚礼' },
  { id: 'tag-旅游结婚', label: '旅游结婚' },
  { id: 'tag-婚礼', label: '婚礼' },
  { id: 'tag-结婚照', label: '结婚照' },
  { id: 'tag-聚会', label: '聚会' },
  { id: 'tag-旅游', label: '旅游' },
  { id: 'tag-游玩', label: '游玩' },
  { id: 'tag-工作', label: '工作' },
  { id: 'tag-生活照', label: '生活照' },
  { id: 'tag-艺术照', label: '艺术照' },
  { id: 'tag-集体', label: '集体' },
  { id: 'tag-寸照', label: '寸照' }
];

var PEOPLE_TAGS = [
  { id: 'tag-亲属', label: '亲属' },
  { id: 'tag-他她人', label: '他/她人' },
  { id: 'tag-四毛', label: '四毛' }
];

var PLACE_TAGS = [
  { id: 'tag-旅游', label: '旅游' },
  { id: 'tag-游玩', label: '游玩' }
];

// 分类配置映射到第一导航
var CAT_TO_FIRSTNAV = {
  'LS': 'photo', 'CZ': 'doc', 'FC': 'doc', 'KA': 'doc',
  'TX': 'people', 'YL': 'life', 'YX': 'tool', 'ZJ': 'people', 'ZMN': 'memory'
};

// ====== 状态 ======
var currentFirstNav = 'photo';
var _allAlbumsCache = {};
var _currentSubFilter = null;
var _memoryTimer = null;
var _memoryPhotos = [];
var _memoryIndex = 0;

// ====== 初始化 ======
function initNavSystem() {
  // 默认激活照片
  switchFirstNav('photo');
  // 加载首页数据
  loadHomeData();
}

// ====== 切换第一导航 ======
function switchFirstNav(catId) {
  currentFirstNav = catId;

  // 更新徽章状态
  document.querySelectorAll('.brand-badge').forEach(function(b) {
    b.classList.toggle('active', b.getAttribute('data-cat') === catId);
  });

  // 更新编码戳
  var badge = document.getElementById('nav-badge');
  if (badge) {
    var config = FIRST_NAV_CONFIG[catId];
    badge.textContent = config ? config.label : catId.toUpperCase();
    badge.setAttribute('data-cat', catId);
  }

  // 生成第二导航栏
  renderSubNav(catId);

  // 显示首页
  showPage('home');
}

// ====== 渲染第二导航栏 ======
function renderSubNav(catId) {
  var container = document.getElementById('nav-sub-links');
  if (!container) return;

  var config = FIRST_NAV_CONFIG[catId];
  if (!config) { container.innerHTML = ''; return; }

  var html = '';
  var links = config.links || [];

  for (var i = 0; i < links.length; i++) {
    var link = links[i];

    if (link.type === 'dropdown') {
      html += '<div class="nav-link dropdown" data-dropdown="' + link.id + '">';
      html += '<span onclick="toggleDropdown(this.closest(\'.nav-link.dropdown\'))">' + link.label + ' <span class="nav-count" id="count-' + link.id + '"></span> &#9662;</span>';
      html += '<div class="dropdown-content">';

      var items = resolveItems(link.items);
      for (var j = 0; j < items.length; j++) {
        html += '<div onclick="handleSubNavClick(\'' + catId + '\', \'' + link.id + '\', \'' + items[j].id + '\')">' + items[j].label + '</div>';
      }

      html += '</div></div>';
    } else {
      html += '<div class="nav-link" onclick="handleSubNavClick(\'' + catId + '\', null, \'' + link.id + '\')">' + link.label + '</div>';
    }
  }

  // 搜索框
  html += '<div class="nav-spacer"></div>';
  html += '<div class="nav-search">';
  html += '<input type="text" id="search-input" placeholder="搜索相册/标签..." oninput="handleSearchInput(this.value)" autocomplete="off">';
  html += '</div>';

  container.innerHTML = html;
}

// ====== 解析下拉项 ======
function resolveItems(items) {
  if (items === 'TAGS_EVENT') return EVENT_TAGS;
  if (items === 'TAGS_PEOPLE') return PEOPLE_TAGS;
  if (items === 'TAGS_PLACE') return PLACE_TAGS;
  if (items === 'YEARS') {
    // 动态生成年份（从2000到2026）
    var years = [];
    for (var y = 2026; y >= 2000; y--) {
      years.push({ id: 'year-' + y, label: y + '年' });
    }
    return years;
  }
  return Array.isArray(items) ? items : [];
}

// ====== 下拉菜单切换 ======
function toggleDropdown(el) {
  if (!el) return;
  // 关闭其他
  document.querySelectorAll('.nav-link.dropdown').forEach(function(d) {
    if (d !== el) d.classList.remove('active');
  });
  el.classList.toggle('active');
}

// 点击外部关闭
document.addEventListener('click', function(e) {
  if (!e.target.closest('.nav-link.dropdown')) {
    document.querySelectorAll('.nav-link.dropdown').forEach(function(d) {
      d.classList.remove('active');
    });
  }
});

// ====== 第二导航栏点击 ======
function handleSubNavClick(catId, groupId, itemId) {
  // 关闭下拉
  document.querySelectorAll('.nav-link.dropdown').forEach(function(d) {
    d.classList.remove('active');
  });

  // 处理特殊动作
  if (itemId === 'mem-start') {
    startMemoryMode();
    return;
  }
  if (itemId === 'tool-upload') {
    window.location.href = '/upload.html';
    return;
  }
  if (itemId === 'tool-scan') {
    triggerScan();
    return;
  }
  if (itemId === 'random') {
    showRandomAlbum();
    return;
  }

  // 设置过滤并加载相册
  _currentSubFilter = { catId: catId, groupId: groupId, itemId: itemId };
  loadFilteredAlbums(catId, itemId);
}

// ====== 加载过滤后的相册 ======
function loadFilteredAlbums(catId, filterId) {
  showPage('albums');
  var grid = document.getElementById('albums-grid');
  var title = document.getElementById('albums-title');
  var countEl = document.getElementById('albums-count');

  if (grid) grid.innerHTML = '<div class="loading-spinner"><div class="spinner"></div></div>';
  if (title) title.textContent = getFilterLabel(filterId);

  // 确定要加载的分类代码
  var catCodes = getCatCodesForFirstNav(catId);
  var allAlbums = [];
  var loaded = 0;

  if (catCodes.length === 0) {
    // 全部分类
    catCodes = Object.keys(typeof PHOTO_CATEGORIES !== 'undefined' ? PHOTO_CATEGORIES : {});
    if (catCodes.length === 0) catCodes = ['LS','CZ','FC','KA','TX','YL','YX','ZJ','ZMN'];
  }

  catCodes.forEach(function(code) {
    DataLoader.load(code, function(albums) {
      allAlbums = allAlbums.concat(albums || []);
      loaded++;
      if (loaded === catCodes.length) {
        var filtered = applyFilter(allAlbums, filterId);
        renderAlbumList(filtered, grid, countEl);
      }
    });
  });
}

// ====== 获取第一导航对应的分类代码 ======
function getCatCodesForFirstNav(catId) {
  var mapping = {
    photo: ['LS'],
    life: ['YL'],
    memory: ['ZMN'],
    people: ['TX', 'ZJ'],
    place: [],
    doc: ['CZ', 'FC', 'KA'],
    tool: ['YX']
  };
  return mapping[catId] || [];
}

// ====== 应用过滤 ======
function applyFilter(albums, filterId) {
  if (!filterId || filterId === 'all' || filterId === 'life-all' || filterId === 'people-all' || filterId === 'place-all' || filterId === 'doc-all') {
    return albums;
  }

  // 归属过滤
  if (filterId.indexOf('owner-') === 0) {
    var owner = filterId.replace('owner-', '');
    return albums.filter(function(a) {
      return a.ownership === owner || (a.tags && a.tags.indexOf(owner) >= 0);
    });
  }

  // 标签过滤
  if (filterId.indexOf('tag-') === 0) {
    var tag = filterId.replace('tag-', '');
    return albums.filter(function(a) {
      return a.tags && a.tags.indexOf(tag) >= 0;
    });
  }

  // 年份过滤
  if (filterId.indexOf('year-') === 0) {
    var year = filterId.replace('year-', '');
    return albums.filter(function(a) {
      return a.date && a.date.indexOf(year) === 0;
    });
  }

  return albums;
}

// ====== 获取过滤标签 ======
function getFilterLabel(filterId) {
  if (!filterId) return '全部相册';
  // 在EVENT_TAGS里找
  for (var i = 0; i < EVENT_TAGS.length; i++) {
    if (EVENT_TAGS[i].id === filterId) return EVENT_TAGS[i].label;
  }
  for (var i = 0; i < PEOPLE_TAGS.length; i++) {
    if (PEOPLE_TAGS[i].id === filterId) return PEOPLE_TAGS[i].label;
  }
  if (filterId.indexOf('owner-') === 0) return filterId.replace('owner-', '');
  if (filterId.indexOf('year-') === 0) return filterId.replace('year-', '') + '年';
  if (filterId === 'all' || filterId.indexOf('-all') >= 0) return '全部';
  return filterId;
}

// ====== 渲染相册列表 ======
function renderAlbumList(albums, gridEl, countEl) {
  if (!gridEl) return;

  // 排序：按日期降序
  albums.sort(function(a, b) {
    return (b.date || '').localeCompare(a.date || '');
  });

  if (countEl) countEl.textContent = albums.length + ' 个相册';

  if (albums.length === 0) {
    gridEl.innerHTML = '<div style="text-align:center;padding:60px;color:#666;">暂无相册</div>';
    return;
  }

  // 分页
  var perPage = 48;
  var totalPages = Math.ceil(albums.length / perPage);
  var currentPage = 1;

  window._albumListState = { albums: albums, page: 1, perPage: perPage, totalPages: totalPages };
  renderAlbumPage(1);
}

function renderAlbumPage(page) {
  var state = window._albumListState;
  if (!state) return;
  state.page = page;

  var grid = document.getElementById('albums-grid');
  var start = (page - 1) * state.perPage;
  var pageAlbums = state.albums.slice(start, start + state.perPage);

  var html = '';
  for (var i = 0; i < pageAlbums.length; i++) {
    html += buildAlbumCard(pageAlbums[i]);
  }
  grid.innerHTML = html;

  // 渲染分页
  renderPagination('albums-pagination', page, state.totalPages);
  window.scrollTo(0, 0);
}

// ====== 构建相册卡片 ======
function buildAlbumCard(album) {
  var thumbUrl = '';
  var cover = album.cover || (album.photos && album.photos.length > 0 ? album.photos[0].f : '');
  if (cover) {
    var catCode = album.id ? album.id.split('-')[0] : 'LS';
    var localPath = 'G:/照片/' + catCode + '/' + (album.path ? album.path + '/' : '') + cover;
    thumbUrl = (typeof toThumbPath === 'function') ? toThumbPath(localPath, 400) : '/thumb/media/G/%E7%85%A7%E7%89%87/' + catCode + '/' + (album.path ? album.path + '/' : '') + encodeURIComponent(cover) + '?w=400';
  }

  var photoCount = album.count || (album.photos ? album.photos.length : 0);
  var dateStr = album.date || '';

  var tagsHtml = '';
  if (album.tags && album.tags.length > 0) {
    var tagDef = (typeof albumTagDefs !== 'undefined') ? albumTagDefs : {};
    for (var i = 0; i < Math.min(album.tags.length, 2); i++) {
      var t = album.tags[i];
      var td = tagDef[t];
      var color = td ? td.color : '#666';
      tagsHtml += '<span class="card-tag" style="background:' + color + '20;color:' + color + ';">' + t + '</span> ';
    }
  }

  var albumJson = JSON.stringify(album).replace(/"/g, '&quot;').replace(/'/g, '&#39;');
  return '<div class="card" onclick=\'openAlbumDetail(' + albumJson + ')\'>' +
    '<div class="card-thumb">' +
      (thumbUrl ? '<img src="' + thumbUrl + '" alt="" loading="lazy">' : '') +
      '<span class="count-badge">' + photoCount + '张</span>' +
    '</div>' +
    '<div class="card-info">' +
      '<div class="card-title">' + album.name + '</div>' +
      '<div class="card-meta"><span>' + dateStr + '</span>' + tagsHtml + '</div>' +
    '</div>' +
  '</div>';
}

// ====== 分页 ======
function renderPagination(containerId, currentPage, totalPages) {
  var container = document.getElementById(containerId);
  if (!container || totalPages <= 1) { if (container) container.innerHTML = ''; return; }

  var html = '';
  if (currentPage > 1) {
    html += '<button class="page-btn" onclick="renderAlbumPage(' + (currentPage - 1) + ')">&laquo;</button>';
  }

  var start = Math.max(1, currentPage - 3);
  var end = Math.min(totalPages, currentPage + 3);
  if (start > 1) html += '<button class="page-btn" onclick="renderAlbumPage(1)">1</button><span style="color:#666">...</span>';
  for (var p = start; p <= end; p++) {
    html += '<button class="page-btn' + (p === currentPage ? ' active' : '') + '" onclick="renderAlbumPage(' + p + ')">' + p + '</button>';
  }
  if (end < totalPages) html += '<span style="color:#666">...</span><button class="page-btn" onclick="renderAlbumPage(' + totalPages + ')">' + totalPages + '</button>';
  if (currentPage < totalPages) {
    html += '<button class="page-btn" onclick="renderAlbumPage(' + (currentPage + 1) + ')">&raquo;</button>';
  }

  container.innerHTML = html;
}

// ====== 打开相册详情 ======
function openAlbumDetail(album) {
  showPage('album-detail');

  var titleEl = document.getElementById('detail-title');
  var metaEl = document.getElementById('detail-meta');
  var tagsEl = document.getElementById('detail-tags');
  var gridEl = document.getElementById('detail-grid');

  if (titleEl) titleEl.textContent = album.name;
  if (metaEl) metaEl.textContent = (album.date || '') + ' | ' + (album.count || (album.photos ? album.photos.length : 0)) + ' 张照片';

  // 标签
  if (tagsEl) {
    var tagsHtml = '';
    if (album.tags) {
      var tagDef = (typeof albumTagDefs !== 'undefined') ? albumTagDefs : {};
      for (var i = 0; i < album.tags.length; i++) {
        var t = album.tags[i];
        var td = tagDef[t];
        var color = td ? td.color : '#666';
        tagsHtml += '<span class="tag-chip"><span class="tag-dot" style="background:' + color + '"></span>' + t + '</span>';
      }
    }
    tagsEl.innerHTML = tagsHtml;
  }

  // 照片网格
  window._currentAlbum = album;
  window._currentPhotos = album.photos || [];
  window._currentPhotoIndex = 0;

  if (gridEl) {
    var catCode = album.id ? album.id.split('-')[0] : 'LS';
    var html = '';
    for (var i = 0; i < window._currentPhotos.length; i++) {
      var photo = window._currentPhotos[i];
      var localPath = 'G:/照片/' + catCode + '/' + (album.path ? album.path + '/' : '') + photo.f;
      var imgUrl = (typeof toThumbPath === 'function') ? toThumbPath(localPath, 300) : '/thumb/media/G/%E7%85%A7%E7%89%87/' + catCode + '/' + (album.path ? album.path + '/' : '') + encodeURIComponent(photo.f) + '?w=300';
      html += '<div class="photo-item" onclick="openViewer(' + i + ')"><img src="' + imgUrl + '" alt="" loading="lazy"></div>';
    }
    gridEl.innerHTML = html;
  }
  window.scrollTo(0, 0);
}

// ====== 照片查看器 ======
function openViewer(index) {
  window._currentPhotoIndex = index;
  var photos = window._currentPhotos;
  var album = window._currentAlbum;
  if (!photos || !album) return;

  var photo = photos[index];
  var catCode = album.id ? album.id.split('-')[0] : 'LS';
  var localPath = 'G:/照片/' + catCode + '/' + (album.path ? album.path + '/' : '') + photo.f;
  var fullUrl = (typeof toMediaPath === 'function') ? toMediaPath(localPath) : '/media/G/%E7%85%A7%E7%89%87/' + catCode + '/' + (album.path ? album.path + '/' : '') + encodeURIComponent(photo.f);

  var img = document.getElementById('viewer-img');
  if (img) { img.src = fullUrl; img.style.transform = 'scale(1) rotate(0deg)'; }

  var counter = document.getElementById('viewer-counter');
  if (counter) counter.textContent = (index + 1) + '/' + photos.length;

  var fnEl = document.getElementById('viewer-filename');
  if (fnEl) fnEl.textContent = photo.f;
  var dimEl = document.getElementById('viewer-dims');
  if (dimEl) dimEl.textContent = (photo.w || '') + 'x' + (photo.h || '');
  var dateEl = document.getElementById('viewer-date');
  if (dateEl) dateEl.textContent = photo.d || album.date || '';

  document.getElementById('viewer-overlay').style.display = 'flex';
  document.body.style.overflow = 'hidden';
}

function closeViewer() {
  document.getElementById('viewer-overlay').style.display = 'none';
  document.body.style.overflow = '';
}

function viewerPrev() {
  var photos = window._currentPhotos;
  if (!photos) return;
  var idx = (window._currentPhotoIndex - 1 + photos.length) % photos.length;
  openViewer(idx);
}

function viewerNext() {
  var photos = window._currentPhotos;
  if (!photos) return;
  var idx = (window._currentPhotoIndex + 1) % photos.length;
  openViewer(idx);
}

var _viewerZoom = 1, _viewerRotate = 0;
function viewerZoom(delta) {
  _viewerZoom = Math.max(0.3, Math.min(3, _viewerZoom + delta));
  var img = document.getElementById('viewer-img');
  if (img) img.style.transform = 'scale(' + _viewerZoom + ') rotate(' + _viewerRotate + 'deg)';
}
function viewerRotate() {
  _viewerRotate = (_viewerRotate + 90) % 360;
  var img = document.getElementById('viewer-img');
  if (img) img.style.transform = 'scale(' + _viewerZoom + ') rotate(' + _viewerRotate + 'deg)';
}

// 键盘控制
document.addEventListener('keydown', function(e) {
  if (document.getElementById('viewer-overlay').style.display === 'flex') {
    if (e.key === 'Escape') closeViewer();
    else if (e.key === 'ArrowLeft') viewerPrev();
    else if (e.key === 'ArrowRight') viewerNext();
    else if (e.key === '+' || e.key === '=') viewerZoom(0.3);
    else if (e.key === '-') viewerZoom(-0.3);
    else if (e.key === 'r' || e.key === 'R') viewerRotate();
  } else if (document.getElementById('memory-overlay').style.display !== 'none') {
    if (e.key === 'Escape') closeMemory();
    else if (e.key === 'ArrowLeft') memPrev();
    else if (e.key === 'ArrowRight') memNext();
  }
});

// ====== 回忆模式 ======
function startMemoryMode() {
  // 收集所有照片
  var catCodes = ['LS','CZ','FC','KA','TX','YL','YX','ZJ','ZMN'];
  var allPhotos = [];
  var loaded = 0;

  catCodes.forEach(function(code) {
    DataLoader.load(code, function(albums) {
      (albums || []).forEach(function(album) {
        if (album.photos) {
          album.photos.forEach(function(p) {
            allPhotos.push({ album: album, photo: p, catCode: code });
          });
        }
      });
      loaded++;
      if (loaded === catCodes.length) {
        // 随机打乱，取前50张
        allPhotos.sort(function() { return Math.random() - 0.5; });
        _memoryPhotos = allPhotos.slice(0, 50);
        _memoryIndex = 0;
        if (_memoryPhotos.length > 0) {
          document.getElementById('memory-overlay').style.display = 'block';
          document.body.style.overflow = 'hidden';
          showMemoryPhoto(0);
          _memoryTimer = setInterval(memNext, 5000);
        }
      }
    });
  });
}

function showMemoryPhoto(idx) {
  if (!_memoryPhotos[idx]) return;
  var item = _memoryPhotos[idx];
  var album = item.album;
  var photo = item.photo;

  var fullUrl = '/media/G/%E7%85%A7%E7%89%87/' + item.catCode + '/' + album.path + '/' + encodeURIComponent(photo.f);
  var memLocalPath = 'G:/照片/' + item.catCode + '/' + (album.path ? album.path + '/' : '') + photo.f;
  var thumbUrl = (typeof toThumbPath === 'function') ? toThumbPath(memLocalPath, 800) : '/thumb/media/G/%E7%85%A7%E7%89%87/' + item.catCode + '/' + (album.path ? album.path + '/' : '') + encodeURIComponent(photo.f) + '?w=800';

  var img = document.getElementById('memory-img');
  if (img) img.src = thumbUrl;
  var bg = document.getElementById('memory-bg');
  if (bg) bg.style.backgroundImage = 'url(' + thumbUrl + ')';

  var titleEl = document.getElementById('memory-title');
  if (titleEl) titleEl.textContent = album.name;
  var dateEl = document.getElementById('memory-date');
  if (dateEl) dateEl.textContent = album.date || '';
  var tagsEl = document.getElementById('memory-tags');
  if (tagsEl) tagsEl.textContent = (album.tags || []).join(' · ');

  var bar = document.getElementById('memory-bar');
  if (bar) bar.style.width = ((idx + 1) / _memoryPhotos.length * 100) + '%';
}

function memNext() {
  _memoryIndex = (_memoryIndex + 1) % _memoryPhotos.length;
  showMemoryPhoto(_memoryIndex);
}
function memPrev() {
  _memoryIndex = (_memoryIndex - 1 + _memoryPhotos.length) % _memoryPhotos.length;
  showMemoryPhoto(_memoryIndex);
}
function closeMemory() {
  document.getElementById('memory-overlay').style.display = 'none';
  document.body.style.overflow = '';
  if (_memoryTimer) { clearInterval(_memoryTimer); _memoryTimer = null; }
}

// ====== 首页数据 ======
function loadHomeData() {
  // 统计
  if (typeof window.globalStats !== 'undefined') {
    var s = window.globalStats;
    setStat('stat-photos', s.totalPhotos || s.total || 0);
    setStat('stat-life', s.totalAlbums || 0);
    setStat('stat-people', 0);
    setStat('stat-places', 0);
  }

  // 最近更新（取LS前12个）
  DataLoader.load('LS', function(albums) {
    var recent = (albums || []).slice(0, 12);
    var grid = document.getElementById('home-recent-grid');
    if (grid) {
      var html = '';
      for (var i = 0; i < recent.length; i++) {
        html += buildAlbumCard(recent[i]);
      }
      grid.innerHTML = html;
    }
  });

  // 标签云
  loadTagCloud();
}

function setStat(id, val) {
  var el = document.getElementById(id);
  if (el) el.textContent = typeof val === 'number' ? val.toLocaleString() : val;
}

function loadTagCloud() {
  var cloud = document.getElementById('home-tag-cloud');
  if (!cloud) return;

  var tagDefs = (typeof albumTagDefs !== 'undefined') ? albumTagDefs : {};
  var html = '';
  var keys = Object.keys(tagDefs).slice(0, 20);
  for (var i = 0; i < keys.length; i++) {
    var tag = tagDefs[keys[i]];
    html += '<span class="tag-chip" onclick="handleSubNavClick(\'photo\', null, \'tag-' + keys[i] + '\')">';
    html += '<span class="tag-dot" style="background:' + (tag.color || '#666') + '"></span>';
    html += (tag.icon || '') + ' ' + (tag.label || keys[i]);
    html += '</span>';
  }
  cloud.innerHTML = html;
}

// ====== 搜索 ======
function handleSearchInput(query) {
  if (!query || query.length < 2) return;
  // 简单搜索：加载LS后过滤
  DataLoader.load('LS', function(albums) {
    var results = (albums || []).filter(function(a) {
      return (a.name && a.name.indexOf(query) >= 0) ||
             (a.tags && a.tags.some(function(t) { return t.indexOf(query) >= 0; }));
    });
    if (results.length > 0) {
      showPage('albums');
      var grid = document.getElementById('albums-grid');
      var countEl = document.getElementById('albums-count');
      var titleEl = document.getElementById('albums-title');
      if (titleEl) titleEl.textContent = '搜索: ' + query;
      renderAlbumList(results, grid, countEl);
    }
  });
}

// ====== 随机相册 ======
function showRandomAlbum() {
  DataLoader.load('LS', function(albums) {
    if (!albums || albums.length === 0) return;
    var idx = Math.floor(Math.random() * albums.length);
    openAlbumDetail(albums[idx]);
  });
}

// ====== 扫描 ======
function triggerScan() {
  fetch('/api/scan', { method: 'POST' })
    .then(function(r) { return r.json(); })
    .then(function(d) { alert(d.message || '扫描已触发'); })
    .catch(function() { alert('扫描触发失败'); });
}

// ====== 页面加载后初始化 ======
document.addEventListener('DOMContentLoaded', function() {
  if (typeof DataLoader !== 'undefined') {
    initNavSystem();
  } else {
    var check = setInterval(function() {
      if (typeof DataLoader !== 'undefined') {
        clearInterval(check);
        initNavSystem();
      }
    }, 500);
  }
});
