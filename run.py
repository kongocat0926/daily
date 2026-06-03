from __future__ import annotations

import argparse
from datetime import datetime
from pathlib import Path

from fund_agent.config import load_settings
from fund_agent.data_sources import FundDataClient
from fund_agent.llm import LLMClient
from fund_agent.report import build_report_payload, generate_report
from fund_agent.search import NewsSearchClient
from fund_agent.utils import dump_json, ensure_dir, iso_date


def main() -> None:
    parser = argparse.ArgumentParser(description="Personal fund daily report agent")
    parser.add_argument("--config", default="config.example.yaml", help="Path to YAML config")
    parser.add_argument("--demo", action="store_true", help="Force demo data; useful for first run")
    args = parser.parse_args()

    settings = load_settings(args.config)
    runtime = settings.runtime
    use_demo = args.demo or bool(runtime.get("use_demo_data", False))
    days_lookback = int(runtime.get("days_lookback", 30))

    output_dir = Path(runtime.get("output_dir", "reports"))
    data_dir = Path(runtime.get("data_dir", "data"))
    ensure_dir(output_dir)
    ensure_dir(data_dir)

    data_client = FundDataClient(days_lookback=days_lookback, use_demo_data=use_demo)
    market_data = data_client.fetch_all(settings.funds, settings.indices)

    search_client = NewsSearchClient(settings.raw.get("search", {}))
    queries = search_client.build_queries(settings.funds)
    news_results = search_client.search_all(queries)

    payload = build_report_payload(settings.raw, market_data, news_results)
    today = iso_date(datetime.now())
    dump_json(data_dir / f"fund_report_payload_{today}.json", payload)

    llm = LLMClient(settings.raw.get("llm", {}))
    report_md = generate_report(payload, llm)
    report_path = output_dir / f"fund_report_{today}.md"
    report_path.write_text(report_md, encoding="utf-8")

    print(f"Saved report: {report_path}")
    print(f"Saved payload: {data_dir / f'fund_report_payload_{today}.json'}")


if __name__ == "__main__":
    main()
