/**
 * 尚唯云影 - 数据加载器（ES5 兼容版）
 * 按需加载：切换分类时才加载对应 index + data JS
 * 数据缓存：已加载的分类数据缓存在内存中
 * 
 * Android 4.4 兼容：不使用 async/await，不使用原生 Promise
 * 通过回调模式实现异步加载
 */

var DataLoader = (function() {

  // 数据缓存：{ cat: { index, data } }
  var _cache = {};

  // 正在加载中的回调队列，防止并发重复加载
  var _loadingCallbacks = {};

  // 分类 → 文件映射
  var _catFiles = {
    movie: { index: 'data/movie-index.js', data: 'data/movie-data.js' },
    tv:    { index: 'data/tv-index.js',    data: 'data/tv-data.js' },
    anime: { index: 'data/anime-index.js', data: 'data/anime-data.js' },
    doc:   { index: 'data/doc-index.js',   data: 'data/doc-data.js' }
  };

  /**
   * 动态加载JS文件（回调模式）
   * @param {string} src - JS文件路径
   * @param {Function} callback - function(err)
   */
  function loadScript(src, callback) {
    var existing = document.querySelector('script[src="' + src + '"]');
    if (existing) { callback(null); return; }

    var script = document.createElement('script');
    script.src = src;
    script.onload = function() { callback(null); };
    script.onerror = function() { callback(new Error('Failed to load: ' + src)); };
    document.head.appendChild(script);
  }

  /**
   * 加载指定分类的数据（index + data），回调模式
   * @param {string} cat - 分类编码，如 'movie', 'tv', 'anime', 'doc'
   * @param {Function} callback - function(err, result) result = { index, data }
   */
  function load(cat, callback) {
    if (typeof callback !== 'function') callback = function() {};

    // 已缓存则直接返回
    if (_cache[cat]) { callback(null, _cache[cat]); return; }

    // 防止并发重复加载：将回调加入队列
    if (_loadingCallbacks[cat]) {
      _loadingCallbacks[cat].push(callback);
      return;
    }

    var files = _catFiles[cat];
    if (!files) {
      console.error('[DataLoader] Unknown category:', cat);
      callback(new Error('Unknown category: ' + cat), null);
      return;
    }

    _loadingCallbacks[cat] = [callback];

    // 1. 加载 index 文件
    loadScript(files.index, function(err) {
      if (err) { _flushCallbacks(cat, err, null); return; }

      // 2. 加载 data 文件
      loadScript(files.data, function(err2) {
        if (err2) { _flushCallbacks(cat, err2, null); return; }

        // 3. 从全局变量中提取数据
        var catConfig = CATEGORIES[cat];
        var indexData = typeof window[catConfig.indexVar] !== 'undefined' ? window[catConfig.indexVar] : null;
        var mainData = typeof window[catConfig.dataVar] !== 'undefined' ? window[catConfig.dataVar] : null;

        var result = { index: indexData, data: mainData };
        _cache[cat] = result;

        console.log('[DataLoader] Loaded', cat, '- series:',
          (indexData ? Object.keys(indexData).length : 0),
          ', items:', countItems(mainData));

        _flushCallbacks(cat, null, result);
      });
    });
  }

  /**
   * 刷新某分类的所有等待回调
   */
  function _flushCallbacks(cat, err, result) {
    var cbs = _loadingCallbacks[cat];
    delete _loadingCallbacks[cat];
    if (!cbs) return;
    for (var i = 0; i < cbs.length; i++) {
      try { cbs[i](err, result); } catch(e) { console.error('[DataLoader] callback error:', e); }
    }
  }

  /**
   * 统计数据中的项目数
   */
  function countItems(data) {
    if (!data) return 0;
    var count = 0;
    Object.keys(data).forEach(function(k) {
      var series = data[k];
      var items = series.movies || series.shows || [];
      count += items.length;
    });
    return count;
  }

  /**
   * 获取已缓存的分类数据
   */
  function getCached(cat) {
    return _cache[cat] || null;
  }

  /**
   * 检查分类数据是否已加载
   */
  function isLoaded(cat) {
    return !!_cache[cat];
  }

  /**
   * 预加载所有分类数据，回调模式
   * @param {Function} callback - function(err)
   */
  function loadAll(callback) {
    if (typeof callback !== 'function') callback = function() {};
    var cats = Object.keys(_catFiles);
    var remaining = cats.length;
    var hasError = false;

    if (remaining === 0) { callback(null); return; }

    cats.forEach(function(cat) {
      load(cat, function(err) {
        if (err) { hasError = true; }
        remaining--;
        if (remaining === 0) {
          console.log('[DataLoader] All categories loaded:', Object.keys(_cache));
          callback(hasError ? new Error('Some categories failed to load') : null);
        }
      });
    });
  }

  /**
   * 清除指定分类缓存（用于数据更新后重新加载）
   */
  function invalidate(cat) {
    delete _cache[cat];
  }

  /**
   * 确保分类数据已加载，如果未加载则自动加载
   * 回调模式，用于各模块的安全访问入口
   * @param {string} cat
   * @param {Function} callback - function(err, result)
   */
  function ensure(cat, callback) {
    if (_cache[cat]) {
      if (callback) callback(null, _cache[cat]);
      return;
    }
    load(cat, callback);
  }

  // Public API
  return {
    load: load,
    loadAll: loadAll,
    getCached: getCached,
    isLoaded: isLoaded,
    invalidate: invalidate,
    ensure: ensure,
    loadScript: loadScript
  };

})();
