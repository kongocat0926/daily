from __future__ import annotations

import os
from typing import Any, Dict, List


class NewsSearchClient:
    def __init__(self, config: Dict[str, Any]):
        self.config = config or {}
        self.provider = str(self.config.get("provider", "gemini")).lower()
        self.api_key = os.getenv(self.config.get("api_key_env", "GEMINI_API_KEY"), "")
        self.model = os.getenv(self.config.get("model_env", "GEMINI_SEARCH_MODEL"), "gemini-3.5-flash")
        self.max_queries = int(self.config.get("max_queries_per_run", 6))
        self.days_recent = int(self.config.get("days_recent", 7))

    def build_queries(self, funds: List[Dict[str, Any]]) -> List[str]:
        queries: List[str] = []
        queries.extend(self.config.get("market_queries", []))

        for f in funds:
            name = f.get("name", "")
            category = f.get("category", "")
            strategy = f.get("strategy", "")
            q = (
                f"{name} {category} {strategy} "
                f"最近{self.days_recent}天 最新消息 基金 影响 "
                "基金经理 基金公司 重仓行业 政策 市场风格"
            )
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
                "answer": "未配置 GEMINI_API_KEY，跳过联网新闻检索。",
                "citations": [],
                "search_results": [],
            }

        if self.provider == "gemini":
            return self._search_gemini(query)

        return {
            "query": query,
            "provider": "unsupported",
            "answer": f"不支持的搜索 provider：{self.provider}",
            "citations": [],
            "search_results": [],
        }

    def _search_gemini(self, query: str) -> Dict[str, Any]:
        try:
            from google import genai
            from google.genai import types

            client = genai.Client(api_key=self.api_key)

            grounding_tool = types.Tool(
                google_search=types.GoogleSearch()
            )

            config = types.GenerateContentConfig(
                tools=[grounding_tool],
                temperature=0.2,
            )

            prompt = (
                "你是金融新闻检索助手。请联网检索并总结与基金投资相关的事实。\n"
                "要求：\n"
                "1. 优先最近7天信息，其次是最近30天的重要背景信息；\n"
                "2. 只总结事实，不编造数据；\n"
                "3. 明确说明可能影响的基金类型，例如宽基、红利、科技、消费、医药、债基、QDII；\n"
                "4. 区分利好、利空、中性、不确定；\n"
                "5. 不给确定性买卖建议；\n"
                "6. 中文输出；\n"
                "7. 如果搜索结果不足，直接说信息不足。\n\n"
                f"检索主题：{query}"
            )

            response = client.models.generate_content(
                model=self.model,
                contents=prompt,
                config=config,
            )

            citations, search_results, web_queries = self._extract_gemini_grounding(response)

            return {
                "query": query,
                "provider": "gemini",
                "model": self.model,
                "answer": getattr(response, "text", "") or "",
                "citations": citations,
                "search_results": search_results,
                "web_search_queries": web_queries,
            }

        except Exception as e:  # noqa: BLE001
            return {
                "query": query,
                "provider": "gemini_error",
                "model": self.model,
                "answer": "",
                "citations": [],
                "search_results": [],
                "error": f"{type(e).__name__}: {e}",
            }

    def _extract_gemini_grounding(self, response: Any) -> tuple[List[Any], List[Any], List[str]]:
        citations: List[Any] = []
        search_results: List[Any] = []
        web_queries: List[str] = []

        try:
            candidates = getattr(response, "candidates", None) or []
            if not candidates:
                return citations, search_results, web_queries

            candidate = candidates[0]
            grounding_metadata = getattr(candidate, "grounding_metadata", None)
            if not grounding_metadata:
                return citations, search_results, web_queries

            web_queries = list(getattr(grounding_metadata, "web_search_queries", None) or [])

            chunks = getattr(grounding_metadata, "grounding_chunks", None) or []
            for chunk in chunks:
                web = getattr(chunk, "web", None)
                if not web:
                    continue

                title = getattr(web, "title", None)
                uri = getattr(web, "uri", None)

                item = {
                    "title": title,
                    "url": uri,
                }

                if uri:
                    citations.append(uri)
                    search_results.append(item)

        except Exception:
            pass

        return citations, search_results, web_queries