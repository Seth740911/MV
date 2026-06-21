/**
 * 尚唯云影 - 渲染模块
 * 对齐GL 3行卡片布局（tag+id | title+year | actor+size）+ 收藏按钮
 * 首页、系列页、全部页、搜索页渲染 + 分页（4分类通用）
 */

var ITEMS_PER_PAGE = 30;

var _seriesPageItems = [];
var _seriesPageCat = '';
var _seriesPageName = '';
var _seriesPageCurrent = 0;

var _allPageItems = [];
var _allPageCat = '';
var _allPageCurrent = 0;

// ========= 收藏系统 =========
var _FAV_KEY = 'mv_favorites';

function _getFavs() {
  try { return JSON.parse(localStorage.getItem(_FAV_KEY)) || {}; } catch(e) { return {}; }
}
function _saveFavs(favs) {
  localStorage.setItem(_FAV_KEY, JSON.stringify(favs));
}
function isFav(cat, series, title) {
  var key = cat + '|' + series + '|' + title;
  return !!(_getFavs()[key]);
}
function toggleFav(btn, cat, series, title) {
  var favs = _getFavs();
  var key = cat + '|' + series + '|' + title;
  if (favs[key]) { delete favs[key]; } else { favs[key] = { cat: cat, series: series, title: title, ts: Date.now() }; }
  _saveFavs(favs);
  _updateFavBtnState(btn, cat, series, title);
  updateFavCount();
}
function _updateFavBtnState(btn, cat, series, title) {
  var active = isFav(cat, series, title);
  btn.classList.toggle('active', active);
  btn.textContent = active ? '♥' : '♡';
}
function updateFavCount() {
  var el = document.getElementById('fav-count');
  if (el) el.textContent = Object.keys(_getFavs()).length;
}

// ========= 收藏页面（回调模式，兼容 Android 4.4） ==========
var _favFilterCat = '';

function showFavPage() {
  showPage('favorites');
  _favFilterCat = '';
  _renderFavFilter();
  // 收藏页需要访问各分类数据，确保全部加载
  if (!DataLoader.isLoaded('tv') || !DataLoader.isLoaded('anime') || !DataLoader.isLoaded('doc')) {
    DataLoader.loadAll(function() {
      if (typeof _rebuildCategoryDropdown === 'function') _rebuildCategoryDropdown();
      _renderFavGrid();
    });
    return;
  }
  _renderFavGrid();
}

function _renderFavFilter() {
  var filter = document.getElementById('fav-filter');
  if (!filter) return;
  var favs = _getFavs();
  var cats = {};
  Object.keys(favs).forEach(function(k) { cats[favs[k].cat] = true; });

  var html = '<button class="fav-filter-btn' + (_favFilterCat === '' ? ' active' : '') + '" onclick="_favFilterCat=\'\';_renderFavFilter();_renderFavGrid();">全部</button>';
  Object.keys(CATEGORIES).forEach(function(cat) {
    if (cats[cat]) {
      var catName = CATEGORIES[cat].name;
      var color = getCatColor(cat);
      html += '<button class="fav-filter-btn' + (_favFilterCat === cat ? ' active' : '') + '" style="' + (_favFilterCat === cat ? 'background:' + color + ';border-color:' + color : 'color:' + color) + '" onclick="_favFilterCat=\'' + cat + '\';_renderFavFilter();_renderFavGrid();">' + catName + '</button>';
    }
  });
  filter.innerHTML = html;
}

function _renderFavGrid() {
  var grid = document.getElementById('fav-page-grid');
  var titleEl = document.getElementById('fav-page-title');
  var favs = _getFavs();
  var entries = Object.keys(favs).map(function(k) { return favs[k]; });

  if (_favFilterCat) {
    entries = entries.filter(function(e) { return e.cat === _favFilterCat; });
  }

  entries.sort(function(a, b) { return (b.ts || 0) - (a.ts || 0); });

  if (titleEl) {
    titleEl.textContent = '我的收藏 (' + entries.length + ')';
  }

  if (entries.length === 0) {
    grid.innerHTML = '<p style="color:#666">还没有收藏，点击卡片上的 ♡ 按钮添加收藏</p>';
    return;
  }

  var html = '';
  entries.forEach(function(entry) {
    var cat = entry.cat;
    var seriesName = entry.series;
    var itemTitle = entry.title;
    var catConfig = CATEGORIES[cat];
    var color = getCatColor(cat);
    var catName = catConfig.name;

    var posterUrl = '';
    var year = '';
    var actor = '';
    var size = 0;
    var rating = '';
    var indexLabel = '';

    if (typeof window[catConfig.dataVar] !== 'undefined') {
      var data = window[catConfig.dataVar];
      var series = data[seriesName];
      if (series) {
        var items = series.movies || series.shows || [];
        for (var i = 0; i < items.length; i++) {
          if (items[i].title === itemTitle) {
            var item = items[i];
            var itemPath = item.path || series.path;
            if (item.poster) posterUrl = resourceUrl(itemPath, item.poster);
            year = item.year || '';
            actor = item.actor || '';
            size = item.size || 0;
            if (item.nfo && item.nfo.rating) rating = item.nfo.rating;
            if (item.index) indexLabel = '#' + item.index;
            if (item.episodeCount) indexLabel = item.episodeCount + '集';
            break;
          }
        }
      }
    }

    html += renderItemCard({
      cat: cat, series: seriesName, title: itemTitle, year: year,
      actor: actor, size: size, posterUrl: posterUrl,
      catColor: color, catName: catName, indexLabel: indexLabel,
      tagOnClick: "openDetail('" + cat + "','" + escapeAttr(seriesName) + "','" + escapeAttr(itemTitle) + "')",
      showFav: true, rating: rating
    });
  });

  grid.innerHTML = html;
}

// ========= 统一卡片渲染（GL 3行布局） =========
function renderItemCard(opts) {
  // opts: { cat, series, title, year, actor, size, posterUrl, catColor, catName,
  //         tagLabel, tagOnClick, extraLeft, extraRight, showFav, indexLabel, rating, countLabel }
  var color = opts.catColor || '#e62429';
  var catName = opts.catName || '';

  var tagHtml = '<span class="card-video-tag" style="background:' + color + '">' + (catName || '') + '</span>';

  var idHtml = '';
  if (opts.indexLabel) idHtml = '<span class="card-id">' + opts.indexLabel + '</span>';
  if (opts.countLabel) idHtml = '<span class="card-id">' + opts.countLabel + '</span>';

  var posterHtml;
  if (opts.posterUrl) {
    posterHtml = '<img src="' + opts.posterUrl + '" onerror="this.outerHTML=\'<div class=card-no-poster>' + escapeAttr(opts.title || '') + '</div>\'">';
  } else {
    posterHtml = '<div class="card-no-poster">' + escapeAttr(opts.title || '') + '</div>';
  }

  var favHtml = '';
  if (opts.showFav !== false) {
    var favActive = isFav(opts.cat, opts.series, opts.title);
    favHtml = '<button class="fav-btn' + (favActive ? ' active' : '') + '" onclick="event.stopPropagation();toggleFav(this,\'' + opts.cat + '\',\'' + escapeAttr(opts.series) + '\',\'' + escapeAttr(opts.title) + '\')">' + (favActive ? '♥' : '♡') + '</button>';
  }

  // 评分标记
  var ratingBadge = '';
  if (opts.rating) {
    ratingBadge = '<div class="card-rating-badge">' + opts.rating + '</div>';
  }

  // Row1: tag + id
  var row1 = '<div class="card-row1">' + tagHtml + idHtml + '</div>';

  // Row2: title + date
  var dateStr = opts.year ? String(opts.year) : '';
  if (opts.yearRange) dateStr = opts.yearRange;
  var dateHtml = dateStr ? '<span class="card-date">' + dateStr + '</span>' : '';
  var row2 = '<div class="card-row2"><span class="card-title" title="' + escapeAttr(opts.title || '') + '">' + escapeAttr(opts.title || '') + '</span>' + dateHtml + '</div>';

  // Row3: actor + extra
  var actorStr = opts.actor || '';
  var extraLeft = opts.extraLeft || (actorStr ? '<span class="card-actor">' + escapeAttr(actorStr) + '</span>' : '');
  var extraRight = opts.extraRight || '';
  if (!extraRight && opts.rating) extraRight = '<span class="card-rating">★' + opts.rating + '</span>';
  var row3 = (extraLeft || extraRight) ? '<div class="card-row3"><span class="card-row3-left">' + extraLeft + '</span><span class="card-row3-right">' + extraRight + '</span></div>' : '';

  var onclick = opts.tagOnClick || '';

  return '<div class="card" onclick="' + onclick + '">' +
    '<div class="card-thumb">' +
    tagHtml +
    posterHtml +
    favHtml +
    ratingBadge +
    '<div class="card-thumb-overlay"></div>' +
    '</div>' +
    '<div class="card-info">' + row1 + row2 + row3 + '</div></div>';
}

// ========= 首页渲染 =========
function renderHomePage() {
  var HOME_PAGE_LIMIT = 18; // 首页每分类最多显示3行×6个
  ['movie', 'tv', 'anime', 'doc'].forEach(function(cat) {
    var grid = document.getElementById(cat + '-grid');
    if (!grid) return;
    var section = document.getElementById(cat + '-section');
    var catConfig = CATEGORIES[cat];

    // 未加载的分类显示占位，点击时触发加载
    if (!DataLoader.isLoaded(cat)) {
      grid.innerHTML = '<div class="home-loading" style="text-align:center;padding:40px;color:#666;cursor:pointer;" onclick="switchCat(\'' + cat + '\')">点击加载' + catConfig.name + '数据...</div>';
      // 移除可能残留的"查看更多"
      var more = section ? section.querySelector('.home-more-link') : null;
      if (more) more.remove();
      return;
    }

    if (typeof window[catConfig.indexVar] === 'undefined') return;
    var index = window[catConfig.indexVar];
    var keys = Object.keys(index);
    keys.sort(function(a, b) { return (index[b].count || 0) - (index[a].count || 0); });
    var color = getCatColor(cat);
    var catName = catConfig.name;
    var totalValid = 0;
    var html = '';
    keys.forEach(function(name) {
      var s = index[name];
      // 跳过空系列（没有实际内容的残留数据）
      if (!s.count || s.count === 0) return;
      // 跳过 DATA 中不存在的孤儿系列（INDEX 有但 DATA 没有，点击会 404）
      if (typeof window[catConfig.dataVar] !== 'undefined') {
        var d = window[catConfig.dataVar];
        if (!d[name]) return;
      }
      totalValid++;

      // 首页只显示前 HOME_PAGE_LIMIT 个
      if (totalValid > HOME_PAGE_LIMIT) return;

      var displayName = getSeriesDisplayName(cat, name);
      var posterUrl = getSeriesPosterUrl(cat, name);

      // 尝试获取系列代表评分（第一部有NFO评分的）
      var seriesRating = '';
      if (typeof window[catConfig.dataVar] !== 'undefined') {
        var d = window[catConfig.dataVar];
        var seriesData = d[name];
        if (seriesData) {
          var items = seriesData.movies || seriesData.shows || [];
          for (var i = 0; i < items.length; i++) {
            if (items[i].nfo && items[i].nfo.rating) {
              seriesRating = items[i].nfo.rating;
              break;
            }
          }
        }
      }

      html += renderItemCard({
        cat: cat, series: name, title: displayName, yearRange: s.yearRange || '',
        actor: '', countLabel: (s.count || 0) + '部',
        posterUrl: posterUrl, catColor: color, catName: catName,
        tagOnClick: "showSeriesPage('" + cat + "','" + escapeAttr(name) + "')",
        showFav: true,
        extraLeft: (s.totalEpisodes ? '<span class="card-actor">' + s.totalEpisodes + '集</span>' : ''),
        extraRight: '',
        rating: seriesRating
      });
    });
    grid.innerHTML = html;

    // 如果还有更多系列，显示"查看全部"链接
    var moreLink = section ? section.querySelector('.home-more-link') : null;
    if (totalValid > HOME_PAGE_LIMIT) {
      if (!moreLink) {
        moreLink = document.createElement('div');
        moreLink.className = 'home-more-link';
        section.appendChild(moreLink);
      }
      moreLink.innerHTML = '<button class="home-more-btn" onclick="showSeriesPage(\'' + cat + '\',\'\')">查看全部 ' + totalValid + ' 个系列 ▸</button>';
    } else if (moreLink) {
      moreLink.remove();
    }
  });
}

// ========= 系列列表页（回调模式，兼容 Android 4.4） ==========
function showSeriesPage(cat, seriesName) {
  showPage('series');
  _seriesPageCat = cat;
  _seriesPageName = seriesName;
  _seriesPageCurrent = 0;

  var catConfig = CATEGORIES[cat];
  if (typeof syncNavToCat === 'function') syncNavToCat(cat);

  // 确保分类数据已加载
  if (!DataLoader.isLoaded(cat)) {
    document.getElementById('series-page-grid').innerHTML = '<p style="color:#666">数据加载中...</p>';
    DataLoader.load(cat, function(err) {
      if (!err) {
        _rebuildCategoryDropdown();
        _showSeriesPageRender(cat, seriesName);
      }
    });
    return;
  }

  _showSeriesPageRender(cat, seriesName);
}

function _showSeriesPageRender(cat, seriesName) {
  var catConfig = CATEGORIES[cat];

  if (typeof window[catConfig.indexVar] === 'undefined') {
    document.getElementById('series-page-grid').innerHTML = '<p style="color:#666">暂无数据</p>';
    return;
  }

  // 空系列名 → 显示该分类全部系列列表
  if (!seriesName) {
    setText('series-page-title', catConfig.name + ' - 全部系列');
    var index = window[catConfig.indexVar];
    var keys = Object.keys(index);
    keys.sort(function(a, b) { return (index[b].count || 0) - (index[a].count || 0); });
    var color = getCatColor(cat);
    var catName = catConfig.name;
    var html = '';
    keys.forEach(function(name) {
      var s = index[name];
      if (!s.count || s.count === 0) return;
      if (typeof window[catConfig.dataVar] !== 'undefined') {
        var d = window[catConfig.dataVar];
        if (!d[name]) return;
      }
      var displayName = getSeriesDisplayName(cat, name);
      var posterUrl = getSeriesPosterUrl(cat, name);
      var seriesRating = '';
      if (typeof window[catConfig.dataVar] !== 'undefined') {
        var d = window[catConfig.dataVar];
        var seriesData = d[name];
        if (seriesData) {
          var items = seriesData.movies || seriesData.shows || [];
          for (var i = 0; i < items.length; i++) {
            if (items[i].nfo && items[i].nfo.rating) {
              seriesRating = items[i].nfo.rating;
              break;
            }
          }
        }
      }
      html += renderItemCard({
        cat: cat, series: name, title: displayName, yearRange: s.yearRange || '',
        actor: '', countLabel: (s.count || 0) + '部',
        posterUrl: posterUrl, catColor: color, catName: catName,
        tagOnClick: "showSeriesPage('" + cat + "','" + escapeAttr(name) + "')",
        showFav: true,
        extraLeft: (s.totalEpisodes ? '<span class="card-actor">' + s.totalEpisodes + '集</span>' : ''),
        extraRight: '', rating: seriesRating
      });
    });
    document.getElementById('series-page-grid').innerHTML = html;
    document.getElementById('series-pagination-top').innerHTML = '';
    document.getElementById('series-pagination-bottom').innerHTML = '';
    return;
  }

  var displayName = getSeriesDisplayName(cat, seriesName);
  setText('series-page-title', displayName + ' - ' + catConfig.name);

  if (typeof window[catConfig.dataVar] === 'undefined') {
    document.getElementById('series-page-grid').innerHTML = '<p style="color:#666">暂无数据</p>';
    return;
  }

  var data = window[catConfig.dataVar];
  var series = data[seriesName];
  if (!series) {
    document.getElementById('series-page-grid').innerHTML = '<p style="color:#666">未找到</p>';
    return;
  }

  var movies = series.movies || [];
  var shows = series.shows || [];
  _seriesPageItems = [];

  if (movies.length > 0) {
    movies.forEach(function(m) {
      var posterUrl = m.poster ? resourceUrl(series.path, m.poster) : '';
      _seriesPageItems.push({ type: 'movie', title: m.title || '', year: m.year || '',
        actor: m.actor || '', size: m.size || 0, index: m.index || 0,
        posterUrl: posterUrl, meta: m, seriesPath: series.path });
    });
  } else {
    shows.forEach(function(s) {
      var posterUrl = s.poster ? resourceUrl(s.path || series.path, s.poster) : '';
      _seriesPageItems.push({ type: 'tv', title: s.title || '', year: s.year || '',
        actor: s.actor || '', size: s.size || 0, episodeCount: s.episodeCount || 0,
        posterUrl: posterUrl, meta: s, seriesPath: s.path || series.path });
    });
  }

  _renderSeriesPage();
}

function _renderSeriesPage() {
  var total = _seriesPageItems.length;
  var totalPages = Math.max(1, Math.ceil(total / ITEMS_PER_PAGE));
  if (_seriesPageCurrent >= totalPages) _seriesPageCurrent = totalPages - 1;
  var start = _seriesPageCurrent * ITEMS_PER_PAGE;
  var end = Math.min(start + ITEMS_PER_PAGE, total);
  var pageItems = _seriesPageItems.slice(start, end);
  var color = getCatColor(_seriesPageCat);
  var catName = CATEGORIES[_seriesPageCat].name;

  var html = '';
  pageItems.forEach(function(item) {
    var indexLabel = item.type === 'movie' ? '#' + item.index : item.episodeCount + '集';
    var rating = item.meta && item.meta.nfo && item.meta.nfo.rating ? item.meta.nfo.rating : '';
    html += renderItemCard({
      cat: _seriesPageCat, series: _seriesPageName, title: item.title, year: item.year,
      actor: item.actor, size: item.size, posterUrl: item.posterUrl,
      catColor: color, catName: indexLabel, indexLabel: '',
      tagOnClick: "openDetail('" + _seriesPageCat + "','" + escapeAttr(_seriesPageName) + "','" + escapeAttr(item.title) + "')",
      showFav: true, rating: rating
    });
  });

  document.getElementById('series-page-grid').innerHTML = html;
  renderPagination('series-pagination-top', _seriesPageCurrent, totalPages, _seriesGoPage);
  renderPagination('series-pagination-bottom', _seriesPageCurrent, totalPages, _seriesGoPage);
}

function _seriesGoPage(page) {
  _seriesPageCurrent = page;
  _renderSeriesPage();
  window.scrollTo(0, 0);
}

// ========= 全部列表（回调模式，兼容 Android 4.4） ==========
function showAllItems(cat) {
  showPage('all');
  _allPageCat = cat;
  _allPageCurrent = 0;

  var catConfig = CATEGORIES[cat];
  setText('all-page-title', '全部' + catConfig.name);
  if (typeof syncNavToCat === 'function') syncNavToCat(cat);

  // 确保分类数据已加载
  if (!DataLoader.isLoaded(cat)) {
    document.getElementById('all-page-grid').innerHTML = '<p style="color:#666">数据加载中...</p>';
    DataLoader.load(cat, function(err) {
      if (!err) {
        _rebuildCategoryDropdown();
        _showAllItemsRender(cat);
      }
    });
    return;
  }

  _showAllItemsRender(cat);
}

function _showAllItemsRender(cat) {
  var catConfig = CATEGORIES[cat];

  if (typeof window[catConfig.dataVar] === 'undefined') return;
  var data = window[catConfig.dataVar];

  _allPageItems = [];
  Object.keys(data).forEach(function(seriesName) {
    var series = data[seriesName];
    var items = series.movies || series.shows || [];
    items.forEach(function(item) {
      _allPageItems.push({
        cat: cat,
        series: seriesName,
        seriesPath: series.path,
        itemPath: item.path || series.path || '',
        title: item.title || '',
        year: item.year || '',
        actor: item.actor || '',
        size: item.size || 0,
        poster: item.poster,
        type: series.movies ? 'movie' : 'tv',
        episodeCount: item.episodeCount || 0,
        index: item.index || 0,
        meta: item
      });
    });
  });
  _allPageItems.sort(function(a, b) { return (b.year || 0) - (a.year || 0); });

  _renderAllPage();
}

function _renderAllPage() {
  var total = _allPageItems.length;
  var totalPages = Math.max(1, Math.ceil(total / ITEMS_PER_PAGE));
  if (_allPageCurrent >= totalPages) _allPageCurrent = totalPages - 1;
  var start = _allPageCurrent * ITEMS_PER_PAGE;
  var end = Math.min(start + ITEMS_PER_PAGE, total);
  var pageItems = _allPageItems.slice(start, end);
  var color = getCatColor(_allPageCat);
  var catName = CATEGORIES[_allPageCat].name;

  var html = '';
  pageItems.forEach(function(item) {
    var posterUrl = item.poster ? resourceUrl(item.itemPath, item.poster) : '';
    var indexLabel = item.type === 'movie' ? '#' + item.index : item.episodeCount + '集';
    var seriesDisplayName = getSeriesDisplayName(item.cat, item.series);

    html += renderItemCard({
      cat: item.cat, series: item.series, title: item.title, year: item.year,
      actor: item.actor, size: item.size, posterUrl: posterUrl,
      catColor: color, catName: catName, indexLabel: indexLabel,
      tagOnClick: "openDetail('" + item.cat + "','" + escapeAttr(item.series) + "','" + escapeAttr(item.title) + "')",
      showFav: true,
      extraLeft: '<span class="card-actor" style="color:' + color + '">' + escapeAttr(seriesDisplayName) + '</span>'
    });
  });

  document.getElementById('all-page-grid').innerHTML = html;
  renderPagination('all-pagination-top', _allPageCurrent, totalPages, _allGoPage);
  renderPagination('all-pagination-bottom', _allPageCurrent, totalPages, _allGoPage);
}

function _allGoPage(page) {
  _allPageCurrent = page;
  _renderAllPage();
  window.scrollTo(0, 0);
}

// ========= 分页渲染 =========
function renderPagination(containerId, currentPage, totalPages, callback) {
  var container = document.getElementById(containerId);
  if (!container || totalPages <= 1) {
    if (container) container.innerHTML = '';
    return;
  }

  var cbName = '_pgCb_' + containerId.replace(/-/g, '_');
  window[cbName] = callback;

  var isFirst = currentPage === 0;
  var isLast = currentPage === totalPages - 1;

  var html = '';

  html += '<span class="pagination-btn first' + (isFirst ? ' disabled' : '') + '"' +
    (isFirst ? '' : ' onclick="' + cbName + '(0)"') + '>FIRST</span>';
  html += '<span class="pagination-btn' + (isFirst ? ' disabled' : '') + '"' +
    (isFirst ? '' : ' onclick="' + cbName + '(' + (currentPage - 1) + ')"') + '>\u2190</span>';

  html += '<span class="pagination-numbers">';
  var maxVisible = 7;
  var rangeStart = Math.max(0, currentPage - Math.floor(maxVisible / 2));
  var rangeEnd = Math.min(totalPages, rangeStart + maxVisible);
  if (rangeEnd - rangeStart < maxVisible) rangeStart = Math.max(0, rangeEnd - maxVisible);

  if (rangeStart > 0) {
    html += '<span class="pagination-num" onclick="' + cbName + '(0)">1</span>';
    if (rangeStart > 1) html += '<span class="pagination-ellipsis">...</span>';
  }
  for (var i = rangeStart; i < rangeEnd; i++) {
    var active = i === currentPage ? ' active' : '';
    html += '<span class="pagination-num' + active + '" onclick="' + cbName + '(' + i + ')">' + (i + 1) + '</span>';
  }
  if (rangeEnd < totalPages) {
    if (rangeEnd < totalPages - 1) html += '<span class="pagination-ellipsis">...</span>';
    html += '<span class="pagination-num" onclick="' + cbName + '(' + (totalPages - 1) + ')">' + totalPages + '</span>';
  }
  html += '</span>';

  html += '<span class="pagination-jump"><input type="number" min="1" max="' + totalPages + '" placeholder="页码" onkeydown="if(event.key===\'Enter\'){var v=parseInt(this.value);if(v>=1&&v<=' + totalPages + '){' + cbName + '(v-1);}}"><span class="pagination-jump-btn" onclick="var inp=this.previousElementSibling;var v=parseInt(inp.value);if(v>=1&&v<=' + totalPages + '){' + cbName + '(v-1);}">跳转</span></span>';

  html += '<span class="pagination-info">' + (currentPage + 1) + '/' + totalPages + '</span>';

  html += '<span class="pagination-btn' + (isLast ? ' disabled' : '') + '"' +
    (isLast ? '' : ' onclick="' + cbName + '(' + (currentPage + 1) + ')"') + '>\u2192</span>';
  html += '<span class="pagination-btn last' + (isLast ? ' disabled' : '') + '"' +
    (isLast ? '' : ' onclick="' + cbName + '(' + (totalPages - 1) + ')"') + '>LAST</span>';

  container.innerHTML = html;
}

// ========= 搜索渲染 =========
function renderSearchResults(results, query) {
  showPage('search');
  setText('search-page-title', '搜索结果: ' + query);

  var gridEl = document.getElementById('search-page-grid');
  if (!results || results.length === 0) {
    gridEl.innerHTML = '<p style="color:#666">无结果</p>';
    return;
  }

  var html = '';
  results.forEach(function(r) {
    var color = getCatColor(r.cat);
    var catName = CATEGORIES[r.cat].name;
    var item = r.data;
    var series = r.series;
    var displayName = getSeriesDisplayName(r.cat, series);
    var posterUrl = item.poster ? resourceUrl(item._seriesPath || '', item.poster) : '';

    var highlightedTitle = item.title || '';
    if (query) {
      var re = new RegExp('(' + query.replace(/[.*+?^${}()|[\]\\]/g, '\\$&') + ')', 'gi');
      highlightedTitle = highlightedTitle.replace(re, '<span class="search-highlight">$1</span>');
    }

    html += renderItemCard({
      cat: r.cat, series: series, title: item.title || '', year: item.year,
      actor: item.actor || '', posterUrl: posterUrl,
      catColor: color, catName: catName,
      tagOnClick: "openDetail('" + r.cat + "','" + escapeAttr(series) + "','" + escapeAttr(item.title || item.dir || '') + "')",
      showFav: true,
      extraLeft: '<span class="card-actor">' + highlightedTitle + '</span>'
    });
  });

  gridEl.innerHTML = html;
}
