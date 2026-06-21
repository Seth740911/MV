# Via 浏览器调起 VLC 播放电影 — 完整技术交接文档

## 一、项目背景

**目标**：在 ARMv7 Android 4.4.2 电视上，通过 Via 7.1.0 浏览器网页调起 VLC 3.0.13 播放本地电影，实现**变速播放**和**音轨切换**（Via 内嵌 `<video>` 标签在 Android 4.4 不支持这两个功能）。

**环境**：
| 项目 | 值 |
|------|-----|
| 设备 | ARMv7 电视，Android 4.4.2 |
| 浏览器 | Via 7.1.0（系统 WebView，非 Chrome） |
| VLC | VLC-Android-3.0.13-ARMv7 |
| 服务端 | Python 3 `http.server`，端口 8082 |
| 服务器 | Windows，视频在 H:/ I:/ J:/ 盘 |

---

## 二、已验证可用的方案（100% 工作）

### 架构
```
服务端生成 <a href="/tv/vlcgo?url=视频URL">电影名</a>
  → 用户点击
  → 跳转到 /tv/vlcgo（服务端构造 intent URI）
  → 最小化页面 300ms 后自动发射 intent
  → Via 弹确认框 → 用户点确定
  → VLC 启动播放
```

### 可用地址
- **`http://192.168.0.10:8082/tv/simple`** — 极简电影列表页（已验证多部影片播放成功）
- **`http://192.168.0.10:8082/tv/vlcgo?url=<编码URL>`** — VLC 自动发射页
- **`http://192.168.0.10:8082/tv/vlctest?url=/media/I/电影/1.mp4`** — 测试页

### intent URI 唯一可用格式
```
intent://192.168.0.10:8082/media/I/%E7%94%B5%E5%BD%B1/1.mp4#Intent;scheme=http;type=video/*;package=org.videolan.vlc;end
```
**关键**：`scheme=http` 必须有，否则 VLC 不识别。

---

## 三、根因分析：主页面为什么失败

### 3.1 故障现象
主页面 `http://192.168.0.10:8082/tv?js=via` 点击电影选 VLC 后：
- VLC 被调起，但播放错误的地址：`http://192.168.0.10:8082/tv?js=via`（当前页面 URL）
- access.log 显示：`GET /tv%3Fjs=via → 404`（VLC 在请求页面地址而非视频地址）

### 3.2 数据流追踪

**主页面的数据流（6 步）**：
```
步骤1: 用户点击系列标题(.stitle)
步骤2: toggleS() → loadSeries() 发 XHR 请求 /tv/data/movie/0
步骤3: 服务端 _handle_tv_series_data() 生成 HTML 片段：
       <div class="vitem" data-action="play" data-url="/media/H/电影/xxx.mkv">标题</div>
步骤4: JS 收到响应，用 innerHTML 解析并插入 DOM
步骤5: 用户点击 .vitem，click handler 从 e.target 向上查找 data-action="play" 的元素
步骤6: _doAction(el) 读取 el.getAttribute("data-url")，传给 playVid(url)
```

**故障点**：步骤5→步骤6 之间，`data-url` 属性值丢失。

### 3.3 排查过程（逐层排除）

| # | 尝试 | 结果 | 排除原因 |
|---|------|------|---------|
| 1 | intent://host:port/path 不带 scheme | 无反应 | Via 不识别 |
| 2 | intent + scheme=http | VLC 闪现但报错 | VLC 收到页面 URL |
| 3 | 加 S.android.intent.extra.data 传 URL | VLC 收到 `http://play` | Via 忽略了 extra |
| 4 | vlc://host:port/path 自定义 scheme | 无反应 | VLC 不识别 |
| 5 | iframe + location.href 双触发 | 同 #2 | 机制一样 |
| 6 | 创建 /tv/vlctest 纯测试页 | **按钮1 成功** | 证明 intent 格式本身没问题 |
| 7 | 创建 /tv/simple 零 JS 页 | **全部成功** | 证明服务端生成链接没问题 |
| 8 | 在 _launchVlc 加调试 overlay | 显示 url 为空 | 证明 JS 传给 playVid 的 url 就是空的 |
| 9 | 在 _doAction 加 alert 调试 | 未执行到 | 用户已切换到 /tv/simple 测试 |

### 3.4 根因定位

**核心发现**：相同的 intent URI 机制，在 `/tv/simple` 上100%工作，在主页面100%失败。

**根因**：主页面 `tv2_via.js` 的 **JavaScript URL 传递链断裂**。

具体分析：
1. 服务端 `_handle_tv_series_data()` **确实生成了** `data-url="/media/H/..."` 属性（代码行 922 可验证）
2. XHR 响应 HTML 通过 `tmp.innerHTML = x.responseText` 解析为 DOM
3. `.vitem` 元素被 append 到 `.ilist` 容器
4. 用户点击时 click handler 向上查找 `data-action` 元素
5. `_doAction(el)` 调用 `el.getAttribute("data-url")`
6. **但返回值为空**，导致 `playVid("")` → `_launchVlc("")` → VLC 收到页面 URL

**可能的断裂原因**（需进一步确认）：
- **最可能**：`el` 不是 `.vitem` 元素本身，而是其父级（如 `.stitle`），父级没有 `data-url`
- **可能**：`innerHTML` 在 Android 4.4 WebView 中解析中文属性值时出现异常
- **可能**：事件捕获阶段被其他 handler 截获，导致 `_doAction` 收到错误的 `el`

### 3.5 如何确认根因

在 `_doAction` 函数入口加 alert（已添加，但用户未测试）：
```javascript
alert("DEBUG _doAction:\ntag=" + el.tagName + "\ndata-url=" + url + "\ntype=" + typeof url);
```

如果 `tag=DIV` 且 `data-url=null`，说明是 XHR/innerHTML 解析问题。
如果 `tag=DIV` 且 `data-url=` 有值但为空字符串，说明是服务端生成问题。
如果 `tag` 不是 `DIV`，说明 click handler 找错了元素。

---

## 四、已尝试过的所有方案及结果

### 4.1 JS 端构造 intent URI（失败）
```javascript
// tv2_via.js 中 _buildVlcIntent() 构造 intent URI
window.location.href = intentUri;
```
**结果**：VLC 收到页面 URL 而非视频 URL。
**原因**：Via 的 WebView 在解析 intent URI 时，将当前页面 URL 作为 Intent data，忽略了 intent URI 中嵌入的路径。

### 4.2 通过 Intent Extra 传递 URL（失败）
```
intent://play#Intent;scheme=http;S.android.intent.extra.data=ENCODED_VIDEO_URL;...;end
```
**结果**：VLC 收到 `http://play`（dummy host）。
**原因**：Via 不支持 `S.xxx` 格式的 intent extra 参数。

### 4.3 服务端构造 intent URI + 最小化页面（成功）
```
跳转到 /tv/vlcgo?url=视频URL → 服务端构造 intent → 自动发射
```
**结果**：VLC 正确播放。
**但**：从主页 JS 跳转时 URL 参数为空（回到了根因问题）。

### 4.4 纯服务端渲染链接（成功 ✓）
```
/tv/simple 页面，所有 <a href="/tv/vlcgo?url=..."> 由服务端生成
```
**结果**：全部成功，多部影片验证通过。

---

## 五、给下一个开发者的建议

### 5.1 最佳方案：增强 /tv/simple 为主入口

**不要试图修复 tv2_via.js 的 data-url 问题**。直接在已验证成功的 `/tv/simple` 基础上增强。

**需要做的工作**：
1. 加载所有分类（电影/电视剧/动画片/纪录片）的数据
2. 分类标签切换
3. 系列选择（如"007系列"、"漫威系列"）
4. 电影列表显示（标题、年份、海报）
5. 电视剧集数选择
6. 页面美化（暗色主题、卡片布局、适配电视大屏）
7. 键盘/遥控器导航

**技术要点**：
- 所有链接必须用 `<a href="/tv/vlcgo?url=http://192.168.0.10:8082{视频路径}">` 格式
- URL 必须用 **未编码的中文**（如 `/media/I/电影/1.mp4`），由 `urllib.parse.quote()` 统一编码
- 可以用少量 JS 做分类切换（fetch 新 HTML 片段），但**播放链接必须服务端生成**
- 或者全服务端渲染：`/tv/simple?cat=movie&series=0`

### 5.2 链接生成代码模板
```python
import urllib.parse

# 生成 vlcgo 链接（在 _handle_simple_vlc_page 中）
video_url = self._tv_media_url(spath, media_file)  # 返回 /media/H/电影/xxx.mkv
abs_url = 'http://192.168.0.10:8082' + video_url
vlcgo = '/tv/vlcgo?url=' + urllib.parse.quote(abs_url, safe='')

# HTML 中使用
html = '<a href="{}" style="...">电影名</a>'.format(vlcgo)
```

### 5.3 绝对不要做的事

| 禁止事项 | 原因 |
|---------|------|
| 在 JS 里构造 intent URI | Via 的 WebView 会吞掉 URL，VLC 收到页面地址 |
| 用 JS 拼接 URL 传给 vlcgo | data-url 在主页面有 bug，传空值 |
| 省略 `scheme=http` | VLC 不识别 |
| 对中文路径预编码后再 quote | 双重编码，VLC 无法解析 |
| 修改 tv2.js | APK 原生播放页面，不能动 |
| 用 `location.assign()` 触发 intent | Via 不响应，必须用 `location.href =` |

### 5.4 验证方法

1. 重启服务器：`cd G:\AI\MV; python server.py`
2. 电视 Via 打开：`http://192.168.0.10:8082/tv/simple`
3. 点击任何电影 → Via 弹"允许打开 VLC?" → 确定 → VLC 播放
4. 检查 access.log 应看到 `GET /media/H/...mkv HTTP/1.1 → 206`

---

## 六、核心文件清单

| 文件 | 状态 | 说明 |
|------|------|------|
| `server.py` | **核心** | 所有路由和渲染逻辑 |
| `tv2_via.js` | **有问题** | 主页 JS，data-url 传递链断裂 |
| `tv2.js` | **勿动** | APK 原生播放页面 |
| `data/movie-data.js` | 数据 | 90000+ 行，所有电影信息 |
| `data/movie-index.js` | 数据 | 分类索引 |
| `data/tv-data.js` | 数据 | 电视剧 |
| `data/anime-data.js` | 数据 | 动画片 |
| `data/doc-data.js` | 数据 | 纪录片 |

## 七、server.py 关键方法位置

| 方法 | 行号 | 作用 | 状态 |
|------|------|------|------|
| `_handle_simple_vlc_page()` | ~642 | 极简电影列表页 | **需增强** |
| `_handle_vlc_go()` | ~712 | VLC 自动发射页 | 完成，勿动 |
| `_handle_vlc_test()` | ~760 | 测试页 | 完成，勿动 |
| `_handle_tv2_page()` | ~813 | 主页面 HTML 模板 | 完成，勿动 |
| `_handle_tv_series_data()` | ~893 | XHR 影片列表片段 | 完成，有 data-url bug |
| `_tv_media_url()` | ~243 | 生成视频 HTTP URL | 完成 |
| `_tv_parse_data()` | ~209 | 解析 data/*.js 文件 | 完成 |

## 八、调试经验总结

### 8.1 排除法的核心思路
```
1. 先确认最小可行路径（/tv/vlctest 的按钮1）→ intent 格式没问题
2. 扩大范围测试（/tv/simple 的真实电影）→ 服务端生成没问题
3. 对比失败场景（主页 JS）→ 定位问题在 JS 层
4. 逐步加 alert/日志追踪数据流 → 缩小断裂点
```

### 8.2 关键调试手段
- **access.log 分析**：通过 VLC 的请求 URL 判断它收到了什么
- **服务端测试页**：/tv/vlctest 提供 3 种 intent 格式对比
- **JS alert 调试**：在 _launchVlc 入口显示 URL 值
- **最小化页面**：/tv/simple 零 JS，排除所有干扰

### 8.3 Via 浏览器的特殊行为
- intent URI 必须用 `location.href =`，`location.assign()` 无效
- 必须有 `scheme=http`，否则不触发 intent 解析
- 不支持 `S.xxx` 格式的 intent extra
- intent URI 的 host+path 会被忽略，VLC 收到的是页面 URL
- **只有服务端生成的 <a href> 链接能可靠传递正确的 URL**
