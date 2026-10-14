# OffPeak — Alexa+ Track Build Plan
*Amazon Build, Ship, Shape Hackathon 2026 · solo · working name, rename anytime*

**Hard deadline:** Fri Oct 23, 12:00pm PT = **3:00pm ET**
**Our deadline:** submitted by **Thu Oct 22, 11pm ET**. Fri morning is buffer only.

---

## 1. The concept (final)

**OffPeak is a Home Energy Autopilot for Alexa+: an agent that runs your home's electricity like a trading desk.** It watches live and next-day power prices, *acts* on your (simulated) smart devices, and reports what it did and what you saved.

- **Autopilot (the core):** it reads tomorrow's prices and your home profile, then builds and executes a plan.
  - "Alexa, autopilot tonight." It schedules EV charging into the cheapest hours, pushes the dryer to midnight, and pre-cools the house before a 5pm price spike.
  - Guardrails you set: "EV at 80% by 7am," "never above 78°F," "ask me before anything over $2."
  - It notifies you on its own: "Prices are spiking in an hour. I paused the EV and pre-cooled. You're $1.40 ahead today."
  - **Grid-stress events:** on peak days it can enroll you in your utility's peak-rebate events, so cutting usage earns you money (simulated in the demo).
- **Bill Detective (the impact number):** "Am I on the right electricity plan?" It replays your usage against flat, time-of-use, and hourly-price plans, then gives a yearly dollar answer and drafts the switch request.
- **Stretch, desk mode:** morning grid brief and "why did Western Hub spike?" with an energy/congestion/loss breakdown. Only if Days 1–7 land on time; otherwise it's a post-hackathon portfolio piece.

**The demo "wow":** a price spike hits mid-demo, the agent reacts without being asked, and a card shows exactly what it did and the dollars saved.

### Why this wins on each judging criterion
| Criterion (25% each) | How OffPeak scores |
|---|---|
| **Tech implementation** | Real self-hosted MCP server (spec 2025-11-25, Streamable HTTP), Agent Skill, Bedrock + Strands agent, persistent state |
| **Design** | Voice-first simulated Alexa+ with Echo Show-style cards and price charts; answers are short when spoken and detailed on screen |
| **Potential impact** | A specific, real audience (dynamic-rate customers, EV owners), measurable savings, and a pro mode for energy desks |
| **Quality of idea** | Hits what the judges list as *creative*: multi-step agentic planning, state that persists across sessions, alerts, cards, Agent Skills. It avoids the "single-turn Q&A / API wrapper" trap they call out by name |

### Bonus points we're going after
- **AWS Builder mini-challenge ($5K):** Bedrock (Claude) + Strands SDK, documented in the README and product feedback.
- **Friction log (up to +10%):** a log entry every day, starting Day 1. This is the easiest score boost in the whole hackathon.

---

## 2. Architecture

```
 Browser: Simulated Alexa+ (Echo Show-style)
   mic → Web Speech API → text           text → speech + visual card
                 │                                   ▲
                 ▼                                   │
   Agent (Python, Strands SDK) ── Claude on Amazon Bedrock
   system prompt = Agent Skill (skills/offpeak/SKILL.md)
                 │  MCP client (Streamable HTTP)
                 ▼
   OffPeak MCP server (FastMCP, Python)
     tools: get_live_price · get_tomorrow_prices · get_profile · update_profile
            build_autopilot_plan · execute_plan · get_home_status
            control_device (EV, thermostat, dryer, dishwasher: simulated)
            set_guardrail · savings_report · compare_rate_plans
            (stretch) get_hub_lmp · explain_price_move · morning_brief
     state: SQLite (home profile, guardrails, device states, action log, savings)
     background: price watcher every 5 min → re-plans on spikes → pushes to UI
                 │
                 ▼
   Data: ComEd Hourly Pricing API (public, no key)
         PJM Data Miner via gridstatus (free key)
         EIA API, Henry Hub gas (free key)
```

### Data sources (verified)
- **ComEd Hourly Pricing API:** public, no auth. It has a 5-minute price feed and a current-hour average, plus next-day estimated prices that post around 4:30pm Central. This is the backbone of home mode.
- **PJM via `gridstatus`:** hub LMPs (real-time 5-min, real-time hourly, day-ahead) with energy/congestion/loss components, and load forecasts. Requires a **free PJM API key** (register at apiportal.pjm.com and set it as `PJM_API_KEY`).
- **EIA API:** Henry Hub natural gas spot prices. Requires a free key.

---

## 3. Day-by-day

Weekdays are ~2–4 hrs, weekend days are heavy. Each day ends with a **demoable checkpoint** and a **friction log entry**.

### Day 1 · Wed Oct 14 — Setup + hello-world MCP
- [ ] Sign up for the PJM API portal and the EIA API (key approval can lag, so do this **first**)
- [ ] Create the GitHub repo `offpeak` (public, MIT license, with the license visible in the About section)
- [ ] Set up a Python venv: `fastmcp`, `gridstatus`, `httpx`, `strands-agents`, `boto3`
- [ ] Build an MCP server with one tool, `get_live_price` (ComEd current hour), running over Streamable HTTP
- [ ] Test it in MCP Inspector
- [ ] Start `FRICTION_LOG.md` and `PRODUCT_FEEDBACK.md`
- **Checkpoint:** Inspector shows the tool, and calling it returns today's real price.

### Day 2 · Thu Oct 15 — Data layer
- [ ] ComEd tools: live 5-min, last 24h, tomorrow's estimates
- [ ] PJM tools: hub LMP (Western Hub, ComEd zone, Dominion), with day-ahead and real-time, plus energy/congestion/loss
- [ ] PJM load vs forecast, and EIA Henry Hub
- [ ] Add caching so we don't hammer the APIs
- **Checkpoint:** every tool returns clean, small JSON in Inspector.

### Day 3 · Fri Oct 16 — Agent brain
- [ ] Write the Agent Skill `skills/offpeak/SKILL.md`: persona, voice style (short spoken answers), which tool fits which question, safety notes
- [ ] Build a Strands agent on Bedrock (Claude) that connects to the MCP server
- [ ] Get a terminal chat loop working end to end
- **Checkpoint:** you type "what's power costing right now and is that high?" and get a good answer.

### Day 4 · Sat Oct 17 (heavy) — The Autopilot
- [ ] SQLite store: home profile (EV battery kWh, charger kW, thermostat, appliances) + guardrails
- [ ] Simulated smart home: EV charger, thermostat (with a simple house temperature model), dryer, dishwasher, each with on/off state
- [ ] `build_autopilot_plan`: picks the cheapest hours within your guardrails (EV ready by 7am, temp limits, $ approval limit)
- [ ] `execute_plan` + action log, plus savings vs. a "no autopilot" baseline
- [ ] Price watcher loop: detects a spike, re-plans (pause EV, pre-cool), and pushes a notification
- **Checkpoint:** "Autopilot tonight" produces a plan, devices change state, and a fake spike triggers a re-plan on its own.

### Day 5 · Sun Oct 18 (heavy) — Simulated Alexa+ experience
- [ ] Web app (FastAPI + one HTML page): mic button, Alexa-style listening ring, spoken replies
- [ ] Echo Show-style cards: price now (color coded), tonight's plan timeline, 24h price chart, live device tiles, "what I did + $ saved"
- [ ] Proactive notifications pop up live in the UI when the autopilot acts
- [ ] Stretch: expose the chart as an **MCP Apps** view (judges list this as creative)
- **Checkpoint:** a full voice conversation in the browser.

### Day 6 · Mon Oct 19 — Bill Detective + replay
- [ ] `compare_rate_plans`: replay a year of usage (sample household profile, or your own Green Button export) against flat, time-of-use, and hourly-price plans, giving a yearly $ answer
- [ ] Draft the "switch my plan" request as a card
- [ ] Grid-stress / peak-rebate event flow (simulated): "Tomorrow is a peak event, want me to earn the rebate?"
- [ ] **Replay mode:** run the autopilot on a real past spike day so the demo is dramatic even if live prices are flat (late October usually is)
- [ ] Stretch only if ahead: desk mode (`explain_price_move`, `morning_brief`)
- **Checkpoint:** Bill Detective gives a believable yearly savings number, and replay mode shows the autopilot reacting to a real spike.

### Day 7 · Tue Oct 20 — Deploy + harden
- [ ] Deploy the MCP server + web app (AWS App Runner, with Render as the fallback). Set a **billing alarm** first.
- [ ] Error handling for when an API is down (the agent says so instead of crashing)
- [ ] A few basic tests, plus a README with setup and run steps (this is required)
- **Checkpoint:** a public URL works from your phone.

### Day 8 · Wed Oct 21 — Polish + paperwork
- [ ] UI polish, faster responses, better spoken phrasing
- [ ] Finish product feedback (all five required questions, per tool) and clean up the friction log
- [ ] Write the Devpost text: problem, who it's for, how it works, what's next
- [ ] Optional: a feature-requests section

### Day 9 · Thu Oct 22 — Demo video + SUBMIT
- [ ] Script (below), then record, then edit. **Under 3:00.** No copyrighted music, no Alexa logo.
- [ ] Upload to YouTube as public or unlisted
- [ ] Submit on Devpost: Alexa+ track + AWS Builder mini-challenge
- **Target: submitted by 11pm ET.**

### Day 10 · Fri Oct 23 — Buffer only
- Fix only what's broken. Final edits close at **3:00pm ET**.

---

## 4. Demo video outline (≤ 3:00)
1. **0:00–0:20 The hook.** Power prices can jump 10x in an hour, and data centers are making the grid tighter every year. Nobody checks a website at 6pm. Your home should trade for you.
2. **0:20–1:10 Autopilot.** "Alexa, autopilot tonight" → plan card → devices switch state → "EV ready by 7, about $X cheaper."
3. **1:10–1:45 The wow.** A spike hits (replay mode). The agent acts on its own: pauses the EV, pre-cools, and pushes a notification with the $ impact.
4. **1:45–2:20 Bill Detective.** "Am I on the right plan?" → "You'd save $X a year on hourly pricing. Want me to draft the switch?"
5. **2:20–3:00 Memory + architecture.** New session remembers guardrails. MCP server + Agent Skill + Bedrock, and who this serves.

---

## 5. How we work each session
- You run the commands. When something breaks, **paste the full error** to me.
- I write the code and explain each file in 2–3 lines so you can talk about it in the video and to judges.
- At the end of each session, add **one friction log entry**: what you tried, expected vs. actual, severity, workaround, and a suggestion.
- Commit to GitHub at every checkpoint.
- **Never commit API keys.** They go in `.env`, and `.env` goes in `.gitignore`.

## 6. Risks and fallbacks
| Risk | Fallback |
|---|---|
| PJM key is slow to arrive | Autopilot and Bill Detective run entirely on ComEd prices (no key needed). PJM is only for the desk-mode stretch. |
| Live prices are flat and boring during the demo | Replay mode with a historical spike day |
| Judges wonder "is it really controlling devices?" | Be upfront: devices are simulated, and the device layer is one swappable module (Alexa smart home / real APIs are the next step) |
| Bedrock throttling or cost | Use a smaller Claude model for routine turns |
| Deploy pain on Day 7 | Render, or record the demo locally (judges don't have to test live) |
| Falling behind | Cut in this order: desk mode → MCP Apps view → peak-rebate flow → Bill Detective "draft switch" card. **Never cut the autopilot, the spike moment, the video, or the friction log.** |
