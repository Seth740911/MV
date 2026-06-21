// TV 页面加速播放控制（ES5 兼容，Android 4.4 WebView）
// 在 server_new.py 的 /tv 页面中通过 <script src="/tv-speed.js"> 加载

var _tvSpeedVisible = false;
var _tvSpeedOpts = [0.5, 0.75, 1.0, 1.25, 1.5, 2.0];
var _tvSpeedIdx = 2;

function _tvHideSpeed() {
  _tvSpeedVisible = false;
  var el = document.getElementById('speed-overlay');
  if (el) el.style.display = 'none';
}

function _tvRenderSpeed() {
  var video = document.getElementById('tv-video');
  if (!video) return;
  var el = document.getElementById('speed-overlay');
  if (!el) {
    el = document.createElement('div');
    el.id = 'speed-overlay';
    el.style.cssText = 'position:fixed;bottom:60px;left:50%;transform:translateX(-50%);' +
      'background:rgba(0,0,0,0.85);color:#fff;padding:10px 18px;border-radius:10px;' +
      'display:flex;gap:10px;z-index:9999;font-size:18px;';
    document.body.appendChild(el);
  }
  el.style.display = 'flex';
  el.innerHTML = '';
  for (var i = 0; i < _tvSpeedOpts.length; i++) {
    var spd = _tvSpeedOpts[i];
    var btn = document.createElement('span');
    btn.textContent = spd + 'x';
    btn.style.cssText = 'padding:6px 14px;border-radius:6px;cursor:pointer;font-weight:' +
      (i === _tvSpeedIdx ? 'bold' : 'normal') + ';background:' +
      (i === _tvSpeedIdx ? '#e62429' : 'transparent') + ';color:#fff;';
    (function(idx) {
      btn.onclick = function() {
        _tvSpeedIdx = idx;
        video.playbackRate = _tvSpeedOpts[idx];
        _tvRenderSpeed();
      };
    })(i);
    el.appendChild(btn);
  }
  clearTimeout(el._timer);
  el._timer = setTimeout(_tvHideSpeed, 5000);
}

function _tvToggleSpeed() {
  var video = document.getElementById('tv-video');
  if (!video || video.readyState === 0) return;
  if (_tvSpeedVisible) {
    _tvHideSpeed();
  } else {
    _tvSpeedVisible = true;
    for (var i = 0; i < _tvSpeedOpts.length; i++) {
      if (Math.abs(_tvSpeedOpts[i] - video.playbackRate) < 0.01) {
        _tvSpeedIdx = i;
        break;
      }
    }
    _tvRenderSpeed();
  }
}

// 用 addEventListener 扩展键盘事件（不覆盖已有的 document.onkeydown）
document.addEventListener('keydown', function(e) {
  var k = e.keyCode;
  var video = document.getElementById('tv-video');
  if (!video || video.readyState === 0) return;
  // 菜单键（Context Menu）显示/隐藏速度面板
  if (k === 93 || k === 229 || e.key === 'ContextMenu') {
    if (document.getElementById('play-page').style.display !== 'none') {
      e.preventDefault();
      _tvToggleSpeed();
    }
    return;
  }
  // ← 减速
  if ((k === 37 || e.key === 'ArrowLeft') && _tvSpeedVisible) {
    e.preventDefault();
    _tvSpeedIdx = Math.max(0, _tvSpeedIdx - 1);
    video.playbackRate = _tvSpeedOpts[_tvSpeedIdx];
    _tvRenderSpeed();
    return;
  }
  // → 加速
  if ((k === 39 || e.key === 'ArrowRight') && _tvSpeedVisible) {
    e.preventDefault();
    _tvSpeedIdx = Math.min(_tvSpeedOpts.length - 1, _tvSpeedIdx + 1);
    video.playbackRate = _tvSpeedOpts[_tvSpeedIdx];
    _tvRenderSpeed();
    return;
  }
});
