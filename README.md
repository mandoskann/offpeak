# OffPeak ⚡

**A Home Energy Autopilot for Alexa+.** OffPeak watches live electricity prices and shifts your EV charging, AC, and appliances to cheap hours on its own, then tells you what it did and what you saved.

Built for the **Alexa+ track** of the [Build, Ship, Shape: Amazon Developer Hackathon](https://amazonappdev2026.devpost.com/).

> 🚧 **In progress.** This repo is being built in public, day by day, through Oct 23, 2026.

---

## What it does (target)
- **Autopilot:** "Alexa, autopilot tonight." It builds a plan from tomorrow's prices and your home profile, then runs it within guardrails you set (EV ready by 7am, never above 78°F).
- **Reacts to spikes on its own:** when prices jump, it pauses the EV, pre-cools the house, and tells you the dollar impact.
- **Bill Detective:** "Am I on the right electricity plan?" It replays your usage against flat, time-of-use, and hourly plans.

## Status
| Day | Milestone | Done |
|---|---|---|
| 1 | MCP server (Streamable HTTP) + live ComEd price tool | ✅ |
| 2 | Price forecast + cheapest-time planner | ✅ |
| 3 | Agent on Amazon Bedrock + Agent Skill | ⬜ |
| 4 | Autopilot + simulated smart home | ⬜ |
| 5 | Simulated Alexa+ voice UI | ⬜ |
| 6 | Bill Detective + replay mode | ⬜ |

## Architecture
```
Simulated Alexa+ (browser, voice) → Agent (Strands + Claude on Amazon Bedrock)
    → OffPeak MCP server (FastMCP, Streamable HTTP, /mcp)
        → ComEd Hourly Pricing API (live 5-minute prices, PJM ComEd zone)
```

## MCP tools
| Tool | What it returns |
|---|---|
| `get_live_price` | Live price (cents/kWh), current-hour average, level (low/normal/high/spike), 30-min trend |
| `get_price_forecast` | Hourly prices from now forward (today's day-ahead + tomorrow's once published ~4:30pm CT), cheapest and priciest hours |
| `find_cheapest_time` | Cheapest time to run a job: one block (dishwasher, dryer) or split across hours (EV), with an optional finish-by deadline and dollar estimate |
| `get_day_prices` | One past day's 24 hourly prices, estimated vs. actual, with peak and low |

Every tool returns a `spoken` field: one short sentence written for a voice assistant to read aloud.

## Setup
Requires Python 3.11+.

```bash
git clone https://github.com/mandoskann/offpeak.git
cd offpeak
python3 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
```

## Run
Start the MCP server (Streamable HTTP at `http://127.0.0.1:8000/mcp`):
```bash
python -m offpeak.server
```

In a second terminal, run the smoke test (connects like an agent would):
```bash
python scripts/test_client.py
```

No network access to ComEd? Run with sample data instead:
```bash
OFFPEAK_OFFLINE=1 python -m offpeak.server
```

Run the tests:
```bash
pytest
```

Inspect it visually with the official MCP Inspector (needs Node.js):
```bash
npx @modelcontextprotocol/inspector
# Transport: Streamable HTTP · URL: http://127.0.0.1:8000/mcp
```

## Data
- **ComEd Hourly Pricing:** public, no key. Real-time 5-minute prices, hourly day-ahead estimates, and settled actuals for ComEd Hourly Pricing customers (PJM ComEd zone). See ComEd's API terms of service.
- Prices are the **supply** portion only (cents/kWh). Delivery charges are separate and don't depend on the time of day.

## License
MIT. See [LICENSE](LICENSE).
