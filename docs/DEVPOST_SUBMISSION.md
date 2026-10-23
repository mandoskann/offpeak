# OffPeak: Devpost submission text

Copy each section into the matching Devpost field.

---

## Project name
OffPeak

## Elevator pitch
A home energy autopilot for Alexa+. It watches live electricity prices and moves your EV charging, dryer, and heating out of price spikes on its own, then tells you what it saved.

## Track and challenges
- **Primary track:** Alexa+
- **Mini challenges:** none

---

## About the project

### Inspiration
More than 70,000 households in the Chicago area pay for electricity by the hour through ComEd's Hourly Pricing program, and almost 22,000 of them drive an EV. Their price moves every hour with the wholesale power market (PJM), and on a hot evening it can jump several times over in minutes. Those customers saved $166 a year on average in 2025, but only by paying attention. Nobody checks a price chart at 6pm before starting the dryer. AI data centers are tightening the grid every year, so prices are only getting spikier.

I'm a finance and economics student focused on power markets, and I wanted to see what happens if your home trades electricity the way a trading desk would: buy the cheap hours, avoid the spikes, and never break the rules you set.

### What it does
OffPeak is an agent for Alexa+ that runs your home's electricity on autopilot.

- **"Alexa, autopilot tonight."** It reads ComEd's live and day-ahead prices and schedules the EV, dishwasher, and dryer into their cheapest hours. It respects your guardrails: car charged to 80% by 7 AM, house never colder than 66°F. Then it tells you the cost and how much you saved versus running everything now.
- **It acts on its own when prices spike.** A watcher checks prices in the background. When power crosses your spike threshold, OffPeak doesn't wait to be asked. It pauses EV charging and reschedules it so the car is still ready by morning, holds the dryer, eases the thermostat within your comfort limits, and announces what it did and the dollars avoided.
- **It remembers your home.** Your EV deadline, target charge, comfort limits, and tonight's plan persist across sessions. Say "I need the car by 6 and charge it to 90 percent" once, and every future plan respects it.
- **Plain voice answers, rich screen.** Every tool returns a one-sentence spoken answer, and the Echo Show-style screen shows the detail: a 24-hour price chart, the plan timeline, live device tiles, and a running savings total.
- Plus quick answers: "What's power costing right now?", "When should I run the dishwasher?", "What happened with prices yesterday?"

### How I built it
- **MCP server (Python, FastMCP).** A self-hosted MCP server over Streamable HTTP with 10 tools: live price, forecast, cheapest-time planner, past-day prices, autopilot, home status, settings, device control, spike check, and spike replay. Each tool returns structured JSON plus a `spoken` field written for voice.
- **Live data.** ComEd's public Hourly Pricing feeds: real-time 5-minute prices, hourly day-ahead estimates, and settled actuals. A forward curve stitches the rest of today with tomorrow's prices once ComEd publishes them around 4:30pm Central.
- **Planner.** Finds the cheapest contiguous block for appliances that must run in one go, or the cheapest split hours for EV charging, all before a deadline.
- **Agent.** The Strands Agents SDK running Claude, connected to the MCP server as an MCP client. It supports both Amazon Bedrock and the Anthropic API behind one setting. The demo runs on the Anthropic API (see Challenges).
- **Agent Skill.** `skills/offpeak/SKILL.md`, in agentskills.io format, defines the voice persona, tool routing, appliance defaults, autopilot behavior, and boundaries. It's loaded at runtime with Strands' Agent Skills loader under strict validation.
- **Autonomy.** A background watcher calls the `check_for_price_spike` MCP tool on its own. The reaction logic lives in the MCP server, so any Alexa+ client gets the same behavior.
- **State.** The simulated home (devices, guardrails, plan, action log, savings) persists to a JSON file. Device changes all go through one function, so a real integration can replace the simulation later.
- **Simulated Alexa+ experience.** A browser Echo Show with voice in (Web Speech API), voice out (speech synthesis), a light bar, and visual cards.
- 23 automated tests cover parsing, planning, autopilot, persistence, and the spike reaction.

### Challenges I ran into
- **Hour-ending vs. hour-starting.** ComEd labels prices by the hour they *end*, and the last hour of the day is labeled "12:00 AM." Getting midnight right across today and tomorrow took careful parsing and tests.
- **Tomorrow's prices don't exist until about 4:30pm Central.** Before that, "charge my car by 7am" can only see daytime hours. Instead of quietly giving a bad answer, OffPeak says tomorrow's prices aren't out yet and that overnight will likely be cheaper.
- **Voice latency.** Agent Skills normally load on demand through an extra tool call. For a voice surface I loaded the skill's instructions up front to save a round trip.
- **Not rescheduling into the spike.** My first version moved EV charging into the very hour that was spiking. The fix excludes the spike window from rescheduling.
- **Bedrock access.** I planned to run Claude on Amazon Bedrock. I lost access to my original AWS account, and the new account I created the day before the deadline was blocked from Bedrock ("Operation not allowed", even for Amazon Nova). Because the agent is provider-agnostic, I switched to the Anthropic API by changing one setting. Moving back to Bedrock is the same one-line change.

### Accomplishments I'm proud of
- The spike moment: the agent notices, acts, explains, and quantifies, with no one asking.
- Guardrails that hold. Every action respects the EV deadline and comfort limits.
- I built it solo, as a finance student, on real market data.

### What I learned
- How retail hourly pricing passes the wholesale PJM market through to households, and why *when* you use power matters as much as *how much*.
- How MCP, Agent Skills, and an agent loop fit together. The skill is the product's personality and judgment; the MCP server is its hands.
- Designing for voice means one sentence out loud, with everything else on screen.

### What's next for OffPeak
- Real devices: Alexa smart home control, EV APIs (charging schedules), and smart thermostats.
- More utilities and rate plans: time-of-use and dynamic rates outside ComEd, starting with other PJM utilities.
- Bill Detective: replay a household's actual usage against flat, time-of-use, and hourly plans to show which rate saves the most.
- Grid events: automatically join utility peak-rebate events so cutting usage on stressed days earns money.
- Hook the MCP server into Alexa+ directly with account linking, and move the agent onto Amazon Bedrock once account access is sorted.

## Built with
python, model-context-protocol, fastmcp, strands-agents, claude, anthropic-api, agent-skills, fastapi, web-speech-api, comed-hourly-pricing, pjm

## Try it out
- GitHub: https://github.com/mandoskann/offpeak
- Demo video: *(YouTube link)*

## Testing instructions (for judges)
See the README. In short: `pip install -r requirements.txt`, run `python -m offpeak.server`, then `python -m offpeak.web` and open http://127.0.0.1:8080 in Chrome. **Replay a price spike** works without any model credentials. The voice agent needs `ANTHROPIC_API_KEY` and `OFFPEAK_PROVIDER=anthropic` in `.env` (or `aws login` with Bedrock access to Claude). `pytest` runs the tests offline.

## Sources for numbers above
- ComEd press release, Sept 24, 2026: more than 70,000 residential customers enrolled; average $166 annual supply savings in 2025; almost 22,000 participants with EVs or plug-in hybrids.
