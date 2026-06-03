# Personal Fund Daily Agent

一个给个人使用的基金日报 Agent：

- 抓取关注基金的净值与近阶段变化
- 抓取常见指数变化
- 用 Perplexity Sonar 做近期新闻/市场检索
- 用任意 OpenAI-compatible LLM 生成 Markdown 日报
- 不做自动下单，不做复杂 UI

> 这不是投资建议工具，只是个人持仓观察和投研整理工具。

## 1. 快速开始

```bash
cd fund_daily_agent
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\\Scripts\\activate
pip install -r requirements.txt
cp .env.example .env
cp config.example.yaml config.yaml
python run.py --config config.yaml --demo
```

成功后会生成：

```text
reports/fund_report_YYYY-MM-DD.md
data/fund_report_payload_YYYY-MM-DD.json
```

## 2. 配置真实 API

编辑 `.env`：

```bash
LLM_API_KEY=你的模型API_KEY
LLM_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
LLM_MODEL=qwen-plus

PERPLEXITY_API_KEY=你的Perplexity API KEY
PERPLEXITY_MODEL=sonar-pro

# 可选，有 Tushare Pro 再填
TUSHARE_TOKEN=
```

DashScope/Qwen 支持 OpenAI-compatible 接口，所以本项目直接用 OpenAI SDK 调用。
DeepSeek/OpenAI/其他兼容接口也可以，只需要改 `LLM_BASE_URL` 和 `LLM_MODEL`。

## 3. 配置你的基金

编辑 `config.yaml`：

```yaml
funds:
  - code: 110022.OF
    name: 易方达消费行业股票
    category: 消费主题
    strategy: 消费行业主题，关注白酒、食品饮料、零售等方向
    holding_note: 我的长期关注基金
    target_weight: 0.10
```

常见代码：

- 开放式基金：`000001.OF`
- 场内 ETF：可以尝试 `512100.SH`，但部分接口可能需要你按 AKShare/Tushare 的可用代码调整

## 4. 正常运行

```bash
python run.py --config config.yaml
```

如果没有配置 LLM，只会生成规则模板版报告。
如果没有配置 Perplexity，只会跳过联网新闻检索。
如果没有 Tushare，则尽量使用 AKShare 免费公开接口。

## 5. 每天自动运行

Linux/macOS crontab 示例：

```bash
0 21 * * * cd /path/to/fund_daily_agent && /path/to/.venv/bin/python run.py --config config.yaml
```

如果你在日本时间晚上 21:00 跑，通常能看到当天多数公开市场信息；开放式基金净值可能滞后，以基金公司公告为准。

## 6. 项目结构

```text
run.py                     # 主入口
config.example.yaml         # 示例配置
.env.example                # API key 示例
fund_agent/config.py         # 配置加载
fund_agent/data_sources.py   # Tushare / AKShare / demo 数据
fund_agent/search.py         # Perplexity 检索
fund_agent/llm.py            # OpenAI-compatible 模型调用
fund_agent/report.py         # 报告生成
reports/                    # 生成 Markdown 日报
data/                       # 保存原始 JSON payload
```

## 7. 设计原则

- LLM 不直接决定买卖，只做信息归因和风险提示
- 结构化数据优先：净值、指数、持仓优先走 AKShare/Tushare
- 联网搜索只补充新闻、政策、事件
- 所有输入保存 JSON，方便以后复盘模型是否胡说
- 先个人日报，再考虑 Telegram/邮件推送

## 8. 后续可扩展

你可以很容易加：

- Telegram/企业微信推送
- 基金估值、同类排名、回撤计算
- 自动记录每日报告观点并回测 1/5/20 日后表现
- 增加 QDII 溢价率检查
- 增加基金公司公告源
