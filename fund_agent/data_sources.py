from __future__ import annotations

import os
from typing import Any, Dict, List

import pandas as pd

from .utils import date_range_lookback, pct, safe_float


def _normalize_fund_code(code: str) -> str:
    code = code.strip()
    if "." in code:
        return code
    return f"{code}.OF"


def _strip_exchange(code: str) -> str:
    return code.split(".")[0]


class FundDataClient:
    """基金数据客户端。

    优先级：
    1. Tushare：更适合基金净值和持仓，但需要 token 和积分权限。
    2. AKShare：免费公开数据，接口偶尔会变，代码做了容错。
    3. Demo：没有网络/没有依赖时用于验证流程。
    """

    def __init__(self, days_lookback: int = 30, use_demo_data: bool = False):
        self.days_lookback = days_lookback
        self.use_demo_data = use_demo_data
        self.tushare_token = os.getenv("TUSHARE_TOKEN", "")

    def fetch_all(self, funds: List[Dict[str, Any]], indices: List[Dict[str, Any]]) -> Dict[str, Any]:
        return {
            "funds": [self.fetch_fund(f) for f in funds],
            "indices": [self.fetch_index(i) for i in indices],
        }

    def fetch_fund(self, fund: Dict[str, Any]) -> Dict[str, Any]:
        if self.use_demo_data:
            return self._demo_fund(fund)

        errors: List[str] = []
        for fetcher in (self._fetch_fund_tushare, self._fetch_fund_akshare):
            try:
                result = fetcher(fund)
                if result.get("latest_nav") is not None:
                    return result
            except Exception as e:  # noqa: BLE001 - 个人脚本保留错误信息即可
                errors.append(f"{fetcher.__name__}: {type(e).__name__}: {e}")

        demo = self._demo_fund(fund)
        demo["source"] = "fallback_demo"
        demo["errors"] = errors
        return demo

    def _fetch_fund_tushare(self, fund: Dict[str, Any]) -> Dict[str, Any]:
        if not self.tushare_token:
            raise RuntimeError("TUSHARE_TOKEN is empty")
        import tushare as ts  # type: ignore

        pro = ts.pro_api(self.tushare_token)
        start_date, end_date = date_range_lookback(self.days_lookback)
        ts_code = _normalize_fund_code(fund["code"])
        nav = pro.fund_nav(ts_code=ts_code, start_date=start_date, end_date=end_date)
        if nav is None or nav.empty:
            raise RuntimeError(f"No Tushare fund_nav data for {ts_code}")

        nav = nav.sort_values("nav_date")
        latest = nav.iloc[-1].to_dict()
        prev = nav.iloc[-2].to_dict() if len(nav) >= 2 else {}
        latest_nav = safe_float(latest.get("unit_nav"))
        prev_nav = safe_float(prev.get("unit_nav"))
        change_1d = pct(latest_nav, prev_nav)

        portfolio = []
        try:
            pf = pro.fund_portfolio(ts_code=ts_code)
            if pf is not None and not pf.empty:
                pf = pf.sort_values(["end_date", "mkv"], ascending=[False, False]).head(10)
                portfolio = pf.to_dict("records")
        except Exception:
            portfolio = []

        return {
            **fund,
            "ts_code": ts_code,
            "source": "tushare",
            "latest_date": latest.get("nav_date"),
            "latest_nav": latest_nav,
            "accum_nav": safe_float(latest.get("accum_nav")),
            "change_1d_pct": change_1d,
            "change_lookback_pct": pct(latest_nav, safe_float(nav.iloc[0].get("unit_nav"))),
            "nav_tail": nav.tail(8).to_dict("records"),
            "portfolio_top10": portfolio,
        }

    def _fetch_fund_akshare(self, fund: Dict[str, Any]) -> Dict[str, Any]:
        import akshare as ak  # type: ignore

        code = _strip_exchange(fund["code"])
        # 常见开放式基金接口：fund_open_fund_info_em(symbol="000001", indicator="单位净值走势")
        df = ak.fund_open_fund_info_em(symbol=code, indicator="单位净值走势")
        if df is None or df.empty:
            raise RuntimeError(f"No AKShare fund_open_fund_info_em data for {code}")

        # 兼容不同版本字段名
        date_col = _first_existing_col(df, ["净值日期", "日期", "nav_date"])
        nav_col = _first_existing_col(df, ["单位净值", "unit_nav", "净值"])
        pct_col = _first_existing_col(df, ["日增长率", "涨跌幅", "change_pct"], required=False)
        if date_col:
            df = df.sort_values(date_col)
        latest = df.iloc[-1].to_dict()
        prev = df.iloc[-2].to_dict() if len(df) >= 2 else {}
        latest_nav = safe_float(latest.get(nav_col))
        prev_nav = safe_float(prev.get(nav_col))
        change_1d = safe_float(latest.get(pct_col)) if pct_col else pct(latest_nav, prev_nav)

        return {
            **fund,
            "ts_code": _normalize_fund_code(fund["code"]),
            "source": "akshare",
            "latest_date": str(latest.get(date_col)) if date_col else None,
            "latest_nav": latest_nav,
            "accum_nav": None,
            "change_1d_pct": change_1d,
            "change_lookback_pct": pct(latest_nav, safe_float(df.iloc[max(0, len(df)-self.days_lookback)].get(nav_col))),
            "nav_tail": df.tail(8).to_dict("records"),
            "portfolio_top10": [],
        }

    def fetch_index(self, index: Dict[str, Any]) -> Dict[str, Any]:
        if self.use_demo_data:
            return self._demo_index(index)
        try:
            import akshare as ak  # type: ignore

            code = index["code"]
            df = ak.stock_zh_index_daily(symbol=code)
            if df is None or df.empty:
                raise RuntimeError(f"No index data for {code}")
            df = df.tail(self.days_lookback).copy()
            latest = df.iloc[-1].to_dict()
            prev = df.iloc[-2].to_dict() if len(df) >= 2 else {}
            latest_close = safe_float(latest.get("close"))
            prev_close = safe_float(prev.get("close"))
            return {
                **index,
                "source": "akshare",
                "latest_date": str(latest.get("date")),
                "latest_close": latest_close,
                "change_1d_pct": pct(latest_close, prev_close),
                "change_lookback_pct": pct(latest_close, safe_float(df.iloc[0].get("close"))),
                "tail": df.tail(8).to_dict("records"),
            }
        except Exception as e:  # noqa: BLE001
            demo = self._demo_index(index)
            demo["source"] = "fallback_demo"
            demo["errors"] = [f"akshare index: {type(e).__name__}: {e}"]
            return demo

    def _demo_fund(self, fund: Dict[str, Any]) -> Dict[str, Any]:
        code_seed = sum(ord(c) for c in fund.get("code", "")) % 17
        latest_nav = round(1.0 + code_seed / 100 + 0.02, 4)
        prev_nav = round(latest_nav / (1 + (code_seed - 8) / 1000), 4)
        return {
            **fund,
            "ts_code": _normalize_fund_code(fund.get("code", "000000.OF")),
            "source": "demo",
            "latest_date": "demo",
            "latest_nav": latest_nav,
            "accum_nav": None,
            "change_1d_pct": pct(latest_nav, prev_nav),
            "change_lookback_pct": round((code_seed - 6) * 0.8, 2),
            "nav_tail": [],
            "portfolio_top10": [],
        }

    def _demo_index(self, index: Dict[str, Any]) -> Dict[str, Any]:
        seed = sum(ord(c) for c in index.get("code", "")) % 19
        return {
            **index,
            "source": "demo",
            "latest_date": "demo",
            "latest_close": round(3000 + seed * 12.3, 2),
            "change_1d_pct": round((seed - 9) / 10, 2),
            "change_lookback_pct": round((seed - 7) * 0.7, 2),
            "tail": [],
        }


def _first_existing_col(df: pd.DataFrame, candidates: List[str], required: bool = True) -> str | None:
    for c in candidates:
        if c in df.columns:
            return c
    if required:
        raise KeyError(f"None of columns exists: {candidates}; actual={list(df.columns)}")
    return None
