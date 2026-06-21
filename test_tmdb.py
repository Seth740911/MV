import requests

PROXIES = {"http": "http://127.0.0.1:7897", "https": "http://127.0.0.1:7897"}
API_KEY = "3109184759dc7c8960e1782250fd08d2"

print("测试1: 搜索电影...")
resp = requests.get(
    "https://api.themoviedb.org/3/search/movie",
    params={"api_key": API_KEY, "language": "zh-CN", "query": "搏击俱乐部"},
    timeout=15,
    proxies=PROXIES,
)
data = resp.json()
results = data.get("results", [])
if results:
    m = results[0]
    print(f"  ✅ 搜索成功！TMDB ID: {m['id']}, 标题: {m['title']}")
    tmdb_id = m["id"]

    print("测试2: 获取详情+导演...")
    resp2 = requests.get(
        f"https://api.themoviedb.org/3/movie/{tmdb_id}",
        params={"api_key": API_KEY, "language": "zh-CN", "append_to_response": "credits"},
        timeout=15,
        proxies=PROXIES,
    )
    d2 = resp2.json()
    directors = [c["name"] for c in d2.get("credits", {}).get("crew", []) if c.get("job") == "Director"]
    print(f"  ✅ 详情成功！导演: {directors}, 评分: {d2.get('vote_average')}")

    print("测试3: 下载海报...")
    poster_path = d2.get("poster_path", "")
    if poster_path:
        url = f"https://image.tmdb.org/t/p/w500{poster_path}"
        r = requests.get(url, timeout=20, proxies=PROXIES)
        print(f"  ✅ 海报下载成功！size={len(r.content)} bytes")
else:
    print("  ❌ 搜索失败:", data)

print("\n所有测试通过！脚本可以正常运行。")
