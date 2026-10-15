"""Check Amap Web API independently of MCP. Never print the API key."""

import argparse
import os
from pathlib import Path

import requests
from dotenv import load_dotenv


def main():
    parser = argparse.ArgumentParser(description="Test Amap key without MCP")
    parser.add_argument("--city", default="杭州")
    parser.add_argument("--keyword", default="西湖")
    args = parser.parse_args()
    load_dotenv(Path(__file__).resolve().parent / ".env", override=False)
    key = os.getenv("AMAP_API_KEY", "").strip()
    if not key or key.startswith("your_"):
        print("[FAIL] 请在 backend/.env 配置真实 AMAP_API_KEY（Web服务类型）。")
        return 2

    print("已读取 AMAP_API_KEY（值隐藏）；直接测试 Web API，不经过 MCP。")
    tests = [
        ("地理编码", "geocode/geo", {"address": args.city, "city": args.city}, "geocodes"),
        ("景点搜索", "place/text", {"keywords": args.keyword, "city": args.city,
                                     "citylimit": "true", "offset": 1, "page": 1}, "pois"),
        ("天气查询", "weather/weatherInfo", {"city": args.city, "extensions": "all"}, "forecasts"),
    ]
    failed = False
    adcode = None
    for label, endpoint, params, field in tests:
        if field == "forecasts":
            if not adcode:
                print("[SKIP] 天气查询: 地理编码未提供城市 adcode。")
                failed = True
                continue
            params = {**params, "city": adcode}
        try:
            response = requests.get("https://restapi.amap.com/v3/" + endpoint,
                                    params={**params, "key": key}, timeout=(5, 10))
            if response.status_code != 200:
                print(f"[FAIL] {label}: HTTP {response.status_code}")
                failed = True
                continue
            data = response.json()
            if not isinstance(data, dict):
                raise ValueError("Unexpected response structure")
            # Only print selected diagnostic fields; never a URL or exception message.
            info = str(data.get("info", "")).replace(key, "[REDACTED]")
            code = str(data.get("infocode", "")).replace(key, "[REDACTED]")
            if str(data.get("status")) != "1":
                print(f"[FAIL] {label}: infocode={code}, info={info}")
                failed = True
                continue
            items = data.get(field) or []
            if field == "geocodes" and items:
                adcode = items[0].get("adcode")
            print(f"[OK] {label}: infocode={code}, info={info}, 返回条目={len(items)}")
            if not items:
                print("     请求成功但结果为空，不能据此确认数据功能正常。")
                failed = True
        except requests.RequestException as exc:
            print(f"[FAIL] {label}: 网络/连接异常 {type(exc).__name__}（敏感详情隐藏）")
            failed = True
        except ValueError:
            print(f"[FAIL] {label}: 响应不是预期 JSON")
            failed = True
    print("测试完成：" + ("存在失败或空结果，请检查上述信息。" if failed else "三个接口均返回有效数据。"))
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
