from __future__ import annotations

import os
from typing import Any, Dict, List

import requests


class NewsSearchClient:
    def __init__(self, config: Dict[str, Any]):
        self.config = config or {}
        self.api_key = os.getenv(self.config.get("api_key_env", "PERPLEXITY_API_KEY"), "")
        self.model = os.getenv(self.config.get("model_env", "PERPLEXITY_MODEL"), "sonar-pro")
        self.max_queries = int(self.config.get("max_queries_per_run", 6))
        self.days_recent = int(self.config.get("days_recent", 7))

    def build_queries(self, funds: List[Dict[str, Any]]) -> List[str]:
        queries: List[str] = []
        queries.extend(self.config.get("market_queries", []))
        for f in funds:
            name = f.get("name", "")
            category = f.get("category", "")
            strategy = f.get("strategy", "")
            q = f"{name} {category} {strategy} 最近{self.days_recent}天 最新消息 基金 影响"
            queries.append(q.strip())
        return [q for q in queries if q][: self.max_queries]

    def search_all(self, queries: List[str]) -> List[Dict[str, Any]]:
        results: List[Dict[str, Any]] = []
        for q in queries[: self.max_queries]:
            results.append(self.search(q))
        return results

    def search(self, query: str) -> Dict[str, Any]:
        if not self.api_key:
            return {
                "query": query,
                "provider": "none",
                "answer": "未配置 PERPLEXITY_API_KEY，跳过联网新闻检索。",
                "citations": [],
                "search_results": [],
            }

        payload = {
            "model": self.model,
            "messages": [
                {
                    "role": "system",
                    "content": "你是金融新闻检索助手。只总结与基金投资相关的事实，保留来源，不给确定性买卖建议。",
                },
                {
                    "role": "user",
                    "content": (
                        f"请检索并总结：{query}\n"
                        "要求：1) 优先最近信息；2) 列出关键事实；3) 说明可能影响的基金类型；"
                        "4) 不要编造数据；5) 用中文输出。"
                    ),
                },
            ],
            "temperature": 0.2,
            "web_search_options": {"search_context_size": "medium"},
        }
        try:
            r = requests.post(
                "https://api.perplexity.ai/chat/completions",
                headers={"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"},
                json=payload,
                timeout=60,
            )
            r.raise_for_status()
            data = r.json()
            msg = data.get("choices", [{}])[0].get("message", {})
            return {
                "query": query,
                "provider": "perplexity",
                "model": self.model,
                "answer": msg.get("content", ""),
                "citations": data.get("citations", []) or msg.get("citations", []),
                "search_results": data.get("search_results", []),
            }
        except Exception as e:  # noqa: BLE001
            return {
                "query": query,
                "provider": "perplexity_error",
                "answer": "",
                "citations": [],
                "search_results": [],
                "error": f"{type(e).__name__}: {e}",
            }
