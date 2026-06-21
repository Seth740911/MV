/* TV2 页面 JavaScript - 独立文件 */

var _focused = null;
var _inPlayer = false;
var _loaded = {};

/* ========== 播放速度控制 ========== */
var _spdList = [0.5, 0.75, 1.0, 1.25, 1.5, 2.0];
var _spdIdx = 2; // 默认1.0x
var _lastOkTime = 0;  // 用于检测双击OK键切换速度
var _spdTipEl = null;

function _cycleSpeed() {
    var v = document.getElementById("vid");
    if (!v || v.readyState < 1) return;
    _spdIdx = (_spdIdx + 1) % _spdList.length;
    var spd = _spdList[_spdIdx];
    v.playbackRate = spd;
    _showSpdTip(spd);
    _updateSpdBtn(spd);
}

function _showSpdTip(spd) {
    if (!_spdTipEl) {
        _spdTipEl = document.createElement("div");
        _spdTipEl.style.cssText = "position:fixed;top:50%;left:50%;transform:translate(-50%,-50%);" +
            "background:rgba(0,0,0,0.85);color:#fff;font-size:42px;padding:24px 48px;" +
            "border-radius:16px;z-index:99999;pointer-events:none;font-weight:bold;" +
            "opacity:0;transition:opacity 0.3s;border:2px solid #e62429;";
        document.body.appendChild(_spdTipEl);
    }
    _spdTipEl.textContent = spd + "x";
    _spdTipEl.style.opacity = "1";
    clearTimeout(_spdTipEl._t);
    _spdTipEl._t = setTimeout(function() { _spdTipEl.style.opacity = "0"; }, 1500);
}

function _updateSpdBtn(spd) {
    var btn = document.getElementById("btn-spd");
    if (btn) btn.textContent = "▶ " + spd + "x";
}

/* ============ 彻底杀死浏览器事件 ============ */
function _killEvent(e) {
    if (!e) return false;
    try { e.preventDefault(); } catch(ex) {}
    try { e.stopPropagation(); } catch(ex) {}
    try { e.stopImmediatePropagation(); } catch(ex) {}
    try { e.returnValue = false; } catch(ex) {}
    try { e.cancelBubble = true; } catch(ex) {}
    return false;
}

/* ============ 分类切换 ============ */
function switchCat(c) {
    var tabs = document.querySelectorAll(".tab");
    var cats = document.querySelectorAll(".cat");
    for (var i = 0; i < tabs.length; i++) {
        var tc = tabs[i].getAttribute("data-cat");
        if (tc === c) { tabs[i].className = "tab active"; } else { tabs[i].className = "tab"; }
    }
    for (var i = 0; i < cats.length; i++) {
        if (cats[i].id === "cat-" + c) { cats[i].className = "cat active"; } else { cats[i].className = "cat"; }
    }
    requestAnimationFrame(function() {
        var items = _getContent();
        if (items.length) _setFocus(items[0]);
    });
}

/* ============ 展开/折叠系列 ============ */
function toggleS(sid, ck, si) {
    var el = document.getElementById("il-" + sid);
    if (!el) return;
    if (el.className.indexOf("open") >= 0) { el.className = "ilist"; return; }
    el.className = "ilist open";
    if (!_loaded[sid]) {
        el.innerHTML = '<div class="loading">加载中...</div>';
        loadSeries(sid, ck, si);
    } else {
        requestAnimationFrame(function() {
            var vitems = el.querySelectorAll(".vitem,.ep");
            if (vitems.length > 0) _setFocus(vitems[0]);
        });
    }
}

/* ============ XHR 按需加载系列影片 ============ */
function loadSeries(sid, ck, si) {
    var x = new XMLHttpRequest();
    x.open("GET", "/tv/data/" + ck + "/" + si, true);
    x.onload = function() {
        var el = document.getElementById("il-" + sid);
        if (!el) return;
        if (x.status === 200) {
            var tmp = document.createElement("div");
            tmp.innerHTML = x.responseText;
            while (tmp.firstChild) { el.appendChild(tmp.firstChild); }
            var loading = el.querySelector(".loading");
            if (loading) el.removeChild(loading);
            _loaded[sid] = 1;
            requestAnimationFrame(function() {
                var vitems = el.querySelectorAll(".vitem,.ep");
                if (vitems.length > 0) _setFocus(vitems[0]);
            });
        } else {
            el.innerHTML = '<div class="loading">加载失败</div>';
        }
    };
    x.onerror = function() {
        var el = document.getElementById("il-" + sid);
        if (el) el.innerHTML = '<div class="loading">网络错误</div>';
    };
    x.send();
}

/* ============ 统一事件分发 ============ */
function _doAction(el) {
    if (!el) return;
    var a = el.getAttribute("data-action");
    if (!a) return;
    if (a === "switchCat") {
        var c = el.getAttribute("data-cat");
        if (c) switchCat(c);
    } else if (a === "toggle") {
        var sid = el.getAttribute("data-sid");
        var ck = el.getAttribute("data-ck");
        var si = el.getAttribute("data-si");
        if (sid) toggleS(sid, ck, si);
    } else if (a === "play") {
        var url = el.getAttribute("data-url");
        if (url) playVid(url);
    } else if (a === "close-play") {
        stopVid();
    } else if (a === "cycle-spd") {
        _cycleSpeed();
    }
}

/* ============ 播放视频 ============ */
function playVid(url) {
    // APK环境：通过 JS 接口调起原生播放器（VLC）
    if (typeof Android !== "undefined" && Android.playVideo) {
        if (url.charAt(0) === '/') {
            url = location.protocol + '//' + location.host + url;
        }
        Android.playVideo(url);
        return;
    }
    // Via/浏览器环境：内嵌播放
    var pg = document.getElementById("play-page");
    var v = document.getElementById("vid");
    v.controls = false;
    v.disableRemotePlayback = true;
    v.disablePictureInPicture = true;
    v.setAttribute("playsinline", "true");
    v.setAttribute("webkit-playsinline", "true");
    v.setAttribute("x5-video-player-type", "h5");
    v.setAttribute("x5-video-player-fullscreen", "false");
    v.src = url;
    v.load();
    v.volume = 0.3;
    v.muted = false;
    v.playbackRate = _spdList[_spdIdx];
    pg.style.display = "block";
    _inPlayer = true;
    history.pushState({ player: 1 }, "");
    v.blur();
    v.tabIndex = -1;
    v.style.outline = "none";
    v.addEventListener("keydown", function(e) { e.preventDefault(); e.stopPropagation(); return false; }, true);
    v.addEventListener("keyup", function(e) { e.preventDefault(); e.stopPropagation(); return false; }, true);
    v.addEventListener("keypress", function(e) { e.preventDefault(); e.stopPropagation(); return false; }, true);
    document.addEventListener("fullscreenchange", _preventFullscreen, true);
    document.addEventListener("webkitfullscreenchange", _preventFullscreen, true);
    v.play().catch(function() {
        v.muted = true;
        v.play().catch(function() {});
    });
    v.addEventListener('webkitendfullscreen', function() {
        stopVid();
    });
    var _userPaused = false;
    var _origPause = v.pause.bind(v);
    v.pause = function() { _userPaused = true; _origPause(); };
    v.addEventListener('pause', function() {
        if (!_userPaused) {
            setTimeout(function() { if (_inPlayer) stopVid(); }, 300);
        }
        _userPaused = false;
    });
}

function _preventFullscreen(e) {
    e.preventDefault();
    e.stopPropagation();
    if (document.fullscreenElement) document.exitFullscreen();
    if (document.webkitFullscreenElement) document.webkitExitFullscreen();
    return false;
}

/* ============ 停止播放 ============ */
function stopVid() {
    var v = document.getElementById("vid");
    var pg = document.getElementById("play-page");
    v.pause();
    v.src = "";
    v.style.cssText = "";
    pg.style.display = "none";
    pg.style.background = "";
    _inPlayer = false;
}

/* ============ 焦点系统 ============ */
var FOCUS_CLS = 'tv-focused';
function _setFocus(el) {
    if (_focused) {
        var cn = ' ' + _focused.className + ' ';
        cn = cn.replace(/ tv-focused /g, ' ').replace(/  +/g, ' ').trim();
        _focused.className = cn;
    }
    if (el.className.indexOf(FOCUS_CLS) < 0) el.className += ' ' + FOCUS_CLS;
    _focused = el;
    try {
        var rect = el.getBoundingClientRect();
        var scrollY = document.documentElement.scrollTop || document.body.scrollTop || 0;
        var headerH = 54;
        var vh = window.innerHeight || document.documentElement.clientHeight;
        if (rect.top < headerH) {
            window.scrollTo(0, scrollY + rect.top - headerH);
        } else if (rect.bottom > vh) {
            window.scrollTo(0, scrollY + rect.bottom - vh);
        }
    } catch (e) {}
}

function _getTabs() {
    return document.querySelectorAll(".tab");
}

function _getContent() {
    var cs = document.querySelector(".cat.active");
    if (!cs) return [];
    var els = cs.querySelectorAll(".stitle,.vitem,.ep");
    var vis = [];
    for (var i = 0; i < els.length; i++) {
        if (els[i].offsetWidth > 0 && els[i].offsetHeight > 0) vis.push(els[i]);
    }
    return vis;
}

function _nav(dir) {
    if (dir === "left" || dir === "right") {
        var tabs = _getTabs();
        var ti = -1;
        for (var i = 0; i < tabs.length; i++) {
            if (tabs[i].className.indexOf("active") >= 0) { ti = i; break; }
        }
        if (dir === "left" && ti > 0) {
            switchCat(tabs[ti - 1].getAttribute("data-cat"));
            _setFocus(tabs[ti - 1]);
            return;
        }
        if (dir === "right" && ti < tabs.length - 1) {
            switchCat(tabs[ti + 1].getAttribute("data-cat"));
            _setFocus(tabs[ti + 1]);
            return;
        }
    }
    if (dir === "down" && _focused && _focused.className.indexOf("tab") >= 0) {
        var c = _getContent();
        if (c.length) _setFocus(c[0]);
        return;
    }
    if (dir === "up" && _focused && _focused.className.indexOf("tab") < 0) {
        var c = _getContent();
        var idx = -1;
        for (var i = 0; i < c.length; i++) { if (c[i] === _focused) { idx = i; break; } }
        if (idx === 0) { var tabs = _getTabs(); if (tabs.length) _setFocus(tabs[0]); return; }
    }
    var c = _getContent();
    if (!c.length) return;
    var idx = -1;
    for (var i = 0; i < c.length; i++) { if (c[i] === _focused) { idx = i; break; } }
    if (idx < 0) { _setFocus(c[0]); return; }
    if (dir === "up" && idx > 0) _setFocus(c[idx - 1]);
    else if (dir === "down" && idx < c.length - 1) _setFocus(c[idx + 1]);
}

/* ============ 键盘事件处理 ============ */
function _onKey(e) {
    try {
        var k = e.keyCode || e.which || 0;
        var pg = document.getElementById("play-page");
        var v = document.getElementById("vid");
        var isPlayerVisible = pg && pg.style.display !== "none";

        if (_inPlayer && isPlayerVisible) {
            var now = Date.now();
            if ((k === 13 || k === 32) && (now - _lastOkTime < 500)) {
                _lastOkTime = 0;
                _cycleSpeed();
                return _killEvent(e);
            }
            if (k === 13 || k === 32) {
                _lastOkTime = now;
                if (!v || v.readyState < 1) { stopVid(); }
                else if (v.paused) { try { v.play(); } catch(ex) { v.muted = true; v.play(); } }
                else { v.pause(); }
                return _killEvent(e);
            }
            if (k === 4 || k === 27) { stopVid(); return _killEvent(e); }
            if (k === 37) {
                if (v && v.readyState >= 1) v.currentTime = Math.max(0, v.currentTime - 10);
                return _killEvent(e);
            }
            if (k === 39) {
                if (v && v.readyState >= 1) v.currentTime = Math.min(v.duration || 0, v.currentTime + 10);
                return _killEvent(e);
            }
            if (k === 38) {
                if (v) v.volume = Math.min(1, v.volume + 0.1);
                return _killEvent(e);
            }
            if (k === 40) {
                if (v) v.volume = Math.max(0, v.volume - 0.1);
                return _killEvent(e);
            }
            return _killEvent(e);
        }

        // 列表状态：导航
        if (k === 38) { _nav("up"); return _killEvent(e); }
        if (k === 40) { _nav("down"); return _killEvent(e); }
        if (k === 37) { _nav("left"); return _killEvent(e); }
        if (k === 39) { _nav("right"); return _killEvent(e); }
        if (k === 13 || k === 32) {
            if (_focused) { _doAction(_focused); }
            return _killEvent(e);
        }
        if (k === 4 || k === 27) { return _killEvent(e); }
    } catch (err) { }
    return true;
}

/* ============ 事件监听（捕获阶段） ============ */
document.addEventListener("keydown", _onKey, true);
document.addEventListener("keydown", _killEvent, true);
document.addEventListener("keyup", _killEvent, true);
document.addEventListener("keypress", _killEvent, true);

/* ============ 点击事件 ============ */
document.addEventListener("click", function(e) {
    var t = e.target;
    while (t && t !== document) {
        if (t.getAttribute("data-action")) { _setFocus(t); _doAction(t); break; }
        t = t.parentNode;
    }
}, true);

/* ============ popstate：拦截浏览器返回 ============ */
for (var _i = 0; _i < 5; _i++) {
    history.pushState({ page: "tv2", idx: _i }, "");
}

window.addEventListener("popstate", function(e) {
    history.pushState({ page: "tv2", restored: 1 }, "");
    if (_inPlayer) {
        stopVid();
    }
});

/* ============ 初始化 ============ */
requestAnimationFrame(function() {
    var items = _getContent();
    if (items.length) _setFocus(items[0]);
});
