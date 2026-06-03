# ROMA — Recursive Open Meta-Agent

ROMA is the multi-agent AI framework that powers Stock Sentinel's automated analysis pipeline. It runs as a scheduled background job at market close and produces actionable alerts for every holding across all portfolios.

## Agent Pipeline

Each holding is processed sequentially through four specialised agents:

```
PriceAgent → SentimentAgent → ForecastAgent → SynthesizerAgent → Alert
```

| Agent | Role | Source |
|-------|------|--------|
| **PriceAgent** | Fetches 180 days of historical closing prices | Yahoo Finance (yfinance) |
| **SentimentAgent** | Searches social posts about the ticker and scores sentiment | Farcaster (Neynar API) + VADER |
| **ForecastAgent** | Produces a 3-day price forecast from the historical data | Facebook Prophet |
| **SynthesizerAgent** | Combines all outputs into a human-readable report with risk flags | Rule-based logic |

## Execution Flow

1. The **scheduler** triggers `run_root_workflow()` at market close (configurable via `MARKET_CLOSE_HOUR` / `MARKET_CLOSE_MINUTE`).
2. The workflow queries all holdings from the database.
3. For each holding, the four agents run in sequence — each agent's output feeds into the next.
4. The final synthesised report is stored as an **alert** in the database, linked to the holding's portfolio.

## External ROMA Support

The framework supports an optional external ROMA module. If `ROMA_FRAMEWORK_MODULE` is set in `.env`, the system will attempt to import and delegate to it. If unavailable or failing, it falls back to the built-in agent pipeline described above.
