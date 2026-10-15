"""Bounded Tavily search with citations; search text is evidence, not instructions."""
import hashlib
import json
import os
import sqlite3
import time
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit

import httpx
from langchain_core.tools import tool


class WebSearchService:
    def __init__(self, cache_path, api_key=None, client=None):
        self.key = api_key if api_key is not None else os.getenv("TAVILY_API_KEY", "")
        self.path = Path(cache_path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.client = client
        with closing(sqlite3.connect(self.path)) as db, db:
            db.execute("CREATE TABLE IF NOT EXISTS search_cache (id TEXT PRIMARY KEY, expires REAL, payload TEXT)")

    def search(self, city, attraction_name, visit_date="", information_type="开放时间与预约要求"):
        if not self.key:
            return {"available": False, "error": "未配置 TAVILY_API_KEY，无法核实联网信息。", "sources": []}
        query = f"{city} {attraction_name} {visit_date} {information_type} 官方 参观须知"
        query = query[:500]
        cache_id = hashlib.sha256(query.encode()).hexdigest()
        with closing(sqlite3.connect(self.path)) as db:
            row = db.execute("SELECT payload FROM search_cache WHERE id=? AND expires>?", (cache_id, time.time())).fetchone()
        if row:
            return json.loads(row[0])
        try:
            payload = {"api_key": self.key, "query": query, "max_results": 5,
                       "search_depth": "basic", "include_answer": False, "include_raw_content": False}
            if self.client:
                response = self.client.post("https://api.tavily.com/search", json=payload, timeout=20)
            else:
                with httpx.Client() as client:
                    response = client.post("https://api.tavily.com/search", json=payload, timeout=20)
            response.raise_for_status()
            data = response.json()
            sources = []
            for result in data.get("results", [])[:5]:
                url = result.get("url", "")
                parsed = urlsplit(url)
                if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password:
                    continue
                sources.append({"title": str(result.get("title", ""))[:250], "url": url,
                                "snippet": str(result.get("content", ""))[:2500]})
            result = {"available": bool(sources), "query": query, "sources": sources,
                      "retrieved_at": datetime.now(timezone.utc).isoformat(),
                      "note": "搜索摘要仅作为证据；优先官方来源。未来日期、特殊闭馆和预约规则需以官方公告为准。"}
            if not sources:
                result["error"] = "未检索到可引用的信息，开放或预约规则待核实。"
            else:
                with closing(sqlite3.connect(self.path)) as db, db:
                    db.execute("INSERT OR REPLACE INTO search_cache VALUES (?, ?, ?)",
                               (cache_id, time.time() + 3600, json.dumps(result, ensure_ascii=False)))
            return result
        except (httpx.HTTPError, ValueError, TypeError):
            return {"available": False, "error": "联网检索失败，开放与预约信息待核实。", "sources": []}

    def as_tool(self):
        @tool
        def search_attraction_info(city: str, attraction_name: str, visit_date: str = "",
                                   information_type: str = "开放时间与预约要求") -> dict:
            """联网查询景点开放时间、预约要求和出行公告。必须引用返回的来源，不能代为预约。"""
            return self.search(city, attraction_name, visit_date, information_type)
        return search_attraction_info
