# OffPeak ⚡

**A Home Energy Autopilot for Alexa+.** OffPeak watches live electricity prices and shifts your EV charging, AC, and appliances to cheap hours on its own, then tells you what it did and what you saved.

Built for the **Alexa+ track** of the [Build, Ship, Shape: Amazon Developer Hackathon](https://amazonappdev2026.devpost.com/).


---

## What it does
- **Autopilot:** "Alexa, autopilot tonight." It builds a plan from tomorrow's prices and your home profile, then runs it within guardrails you set (EV ready by 7am, never above 78°F).
- **Reacts to spikes on its own:** when prices jump, it pauses the EV, pre-cools the house, and tells you the dollar impact.
- **Remembers your home:** EV deadline, target charge, comfort limits, and tonight's plan persist across sessions.
- **Simulated Alexa+ experience:** a browser Echo Show with voice in, spoken answers, and visual cards (price chart, plan timeline, live device tiles).

## Architecture
```
Simulated Alexa+ (browser: voice in/out, Echo Show-style cards)       offpeak/web.py + static/index.html
   │                                   ▲
   ▼                                   │ autopilot announcements
Agent: Strands Agents SDK + Claude (Anthropic API or Amazon Bedrock)   offpeak/agent.py
   system prompt = Agent Skill (skills/offpeak/SKILL.md)
   │  MCP client, Streamable HTTP          Watcher: calls check_for_price_spike
   ▼                                       on its own every few minutes
OffPeak MCP server (FastMCP, MCP spec 2025-11-25+, /mcp)                offpeak/server.py
   price tools ── ComEd Hourly Pricing (live 5-min + day-ahead)        offpeak/comed.py
   planner ────── cheapest block / cheapest split hours + deadline     offpeak/planner.py
   autopilot ──── simulated home, guardrails, plan, spike reaction     offpeak/home.py
                  state persisted to data/home.json
```

## MCP tools
| Tool | What it returns |
|---|---|
| `get_live_price` | Live price (cents/kWh), current-hour average, level (low/normal/high/spike), 30-min trend |
| `get_price_forecast` | Hourly prices from now forward (today's day-ahead + tomorrow's once published ~4:30pm CT), cheapest and priciest hours |
| `find_cheapest_time` | Cheapest time to run a job: one block (dishwasher, dryer) or split across hours (EV), with an optional finish-by deadline and dollar estimate |
| `get_day_prices` | One past day's 24 hourly prices, estimated vs. actual, with peak and low |
| `run_autopilot` | Plans tonight: EV, dishwasher, dryer each in their cheapest hours within the guardrails; saves the plan |
| `get_home_status` | Device states, saved plan, guardrails, recent autopilot actions, total saved |
| `update_settings` | Changes guardrails (EV ready-by hour, target %, comfort limits, spike threshold); persisted |
| `control_device` | Manual start / stop / pause |
| `check_for_price_spike` | If the price crosses the threshold, acts on its own: pauses + reschedules EV, delays dryer, eases thermostat, reports $ saved |
| `start_spike_replay` | Demo mode: replays an evening price spike so you can watch the autopilot react |

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

**The simulated Alexa+ experience** (needs the MCP server running, plus model access, below):
```bash
python -m offpeak.web        # open http://127.0.0.1:8080 in Chrome
```
Click the mic (or press space) and talk, or type. Click **Replay a price spike** to watch the autopilot act on its own.

**Model access.** The agent runs Claude through the Strands Agents SDK, using either provider (one setting in `.env`):
- **Anthropic API** (used for the demo): set `ANTHROPIC_API_KEY=...` and `OFFPEAK_PROVIDER=anthropic`.
- **Amazon Bedrock:** run `aws login` and make sure your account can call a Claude model in us-east-1 (`OFFPEAK_MODEL_ID`). Bedrock was the original target; my new AWS account was blocked from Bedrock before the deadline (see `docs/FRICTION_LOG.md`), so the demo runs on the Anthropic API. Switching back is one line.

Talk to the agent in the terminal instead:
```bash
python -m offpeak.agent                                  # chat
python -m offpeak.agent "when should I charge my car?"   # one question
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

## Agent Skill
[`skills/offpeak/SKILL.md`](skills/offpeak/SKILL.md) is an [Agent Skill](https://agentskills.io) that defines how OffPeak behaves on a voice surface: short spoken answers, which MCP tool fits which question, appliance defaults (EV, dishwasher, dryer), and boundaries. The agent loads it at runtime with the Strands Agent Skills loader (`Skill.from_file`, strict validation) and uses it as its system prompt.

## Data
- **ComEd Hourly Pricing:** public, no key. Real-time 5-minute prices, hourly day-ahead estimates, and settled actuals for ComEd Hourly Pricing customers (PJM ComEd zone). See ComEd's API terms of service.
- Prices are the **supply** portion only (cents/kWh). Delivery charges are separate and don't depend on the time of day.

## License
MIT. See [LICENSE](LICENSE).
