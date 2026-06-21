// ===== 观看进度模块（云影版）=====
// 功能：播放进度记忆与恢复
// 存储：localStorage mv_watched
// 数据结构：{ videos: { "movie|xxx": { ts, progress }, "episode|xxx": { ts, progress } } }

var MV_WATCH_KEY = 'mv_watched';

// ----- 数据读写 -----

function getWatched() {
  var raw = localStorage.getItem(MV_WATCH_KEY);
  return raw ? JSON.parse(raw) : { videos: {} };
}

function saveWatched(data) {
  localStorage.setItem(MV_WATCH_KEY, JSON.stringify(data));
}

// ----- 进度读写 -----

function getWatchProgress(type, id) {
  var data = getWatched();
  var key = type + '|' + id;
  return (data.videos[key] && data.videos[key].progress) || 0;
}

function setWatchProgress(type, id, progress) {
  var data = getWatched();
  var key = type + '|' + id;
  if (data.videos[key]) {
    data.videos[key].progress = progress;
    data.videos[key].ts = Date.now();
  } else {
    data.videos[key] = { ts: Date.now(), progress: progress };
  }
  saveWatched(data);
}

// ----- 标记已看 -----

function markWatched(type, id, progress) {
  var data = getWatched();
  var key = type + '|' + id;
  data.videos[key] = { ts: Date.now(), progress: (progress !== undefined && progress !== null) ? progress : 1 };
  saveWatched(data);
}

function isWatched(type, id) {
  var key = type + '|' + id;
  var data = getWatched();
  return !!data.videos[key];
}
