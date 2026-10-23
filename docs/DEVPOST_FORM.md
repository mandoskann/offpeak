# Devpost form: paste-ready, field by field

=====================================================================
PAGE: PROJECT DETAILS
=====================================================================

----- About the project (paste everything between the lines) -----

## Inspiration
More than 70,000 households around Chicago pay for electricity by the hour through ComEd's Hourly Pricing program, and almost 22,000 of them drive an EV. Their price follows the wholesale power market (PJM), so it moves all day. It can jump several times over on a hot evening, and on a windy morning it can even go below zero. Those customers saved $166 a year on average in 2025, but only by paying attention, and nobody checks a price chart at 6pm before starting the dryer. With AI data centers pulling more power every year, prices are only getting spikier.

I'm a finance and economics student focused on power markets. I wanted to see what happens if your home handles electricity the way a trading desk would: use the cheap hours, avoid the spikes, and never break the rules you set.

## What it does
OffPeak is an agent for Alexa+ that runs your home's electricity on autopilot.

- **"Alexa, autopilot tonight."** It reads ComEd's live and day-ahead prices and schedules the EV, dishwasher, and dryer into their cheapest hours before morning. It respects your rules (car charged to 80% by 7 AM, house never colder than 66°F) and tells you the cost and what you saved versus running everything now.
- **It acts on its own when prices spike.** A watcher checks prices in the background. When power crosses your spike threshold, OffPeak doesn't wait to be asked. It pauses EV charging and moves it so the car is still ready by morning, holds the dryer, eases the thermostat within your comfort limits, and tells you what it did and what it saved.
- **It remembers your home.** Your EV deadline, target charge, comfort limits, and tonight's plan carry across sessions. Say "I need the car by 6 and charge it to 90 percent" once, and every future plan respects it.
- **Short voice answers, detail on screen.** Every tool returns one spoken sentence, and the Echo Show-style screen shows a 24-hour price bar with your devices pinned to the hours they'll run, what each device is doing, and a running savings total.
- Plus quick answers like "What's power costing right now?" and "When should I run the dishwasher?"

## How I built it
- **MCP server (Python, FastMCP).** A self-hosted MCP server over Streamable HTTP with 10 tools: live price, forecast, cheapest-time planner, past-day prices, autopilot, home status, settings, device control, spike check, and spike replay. Each tool returns structured JSON plus a `spoken` field written for voice.
- **Live data.** ComEd's public Hourly Pricing feeds: real-time 5-minute prices, hourly day-ahead estimates, and settled actuals. Before ComEd posts tomorrow's prices (around 4:30pm Central), OffPeak estimates the overnight hours from today's prices and labels them as estimates.
- **Planner.** Finds the cheapest back-to-back block for appliances that have to run in one go, or the cheapest split hours for EV charging, all before a deadline.
- **Agent.** Built on the **Strands Agents SDK**, connected to the MCP server as an MCP client, running Claude. It supports both Amazon Bedrock and the Anthropic API behind one setting.
- **Agent Skill.** `skills/offpeak/SKILL.md`, in agentskills.io format, defines the voice persona, which tool to use when, appliance defaults, autopilot behavior, and boundaries. It's loaded at runtime with the Strands Agent Skills loader under strict validation.
- **Autonomy.** A background watcher calls the `check_for_price_spike` MCP tool on its own. The reaction logic lives in the MCP server, so any Alexa+ client gets the same behavior.
- **State.** The simulated home (devices, rules, plan, action log, savings) is saved to a file. All device changes go through one function, so real devices can replace the simulation later.
- **Simulated Alexa+ experience.** A browser Echo Show with voice in (Web Speech API), voice out (speech synthesis), a listening light bar, and visual cards.
- 25 automated tests cover parsing, planning, the autopilot, saved settings, and the spike reaction.
- I'm a finance student, not a software engineer. I designed the product and directed the build, and wrote the code with Claude as an AI coding assistant, running and testing every piece myself.

## Challenges I ran into
- **Hour-ending vs. hour-starting.** ComEd labels prices by the hour they *end*, and the last hour of the day is labeled "12:00 AM." Getting midnight right across today and tomorrow took careful parsing and tests.
- **Tomorrow's prices don't exist until the afternoon.** In the morning, "charge my car by 7am" could only see today's hours. Now OffPeak estimates tonight from today's prices, says so out loud, and the screen marks those hours as estimates.
- **Voice latency.** Agent Skills normally load through an extra tool call. For voice I load the skill's instructions up front to save a round trip.
- **Not rescheduling into the spike.** My first version moved EV charging into the exact hour that was spiking. The fix keeps the spike window off-limits.
- **Bedrock access.** I planned to run Claude on Amazon Bedrock. I lost access to my original AWS account, and the new account I created was blocked from Bedrock ("Operation not allowed", even for Amazon Nova). Because the agent is provider-agnostic through Strands, I switched to the Anthropic API with one setting. Moving back to Bedrock is the same one-line change.

## Accomplishments that I'm proud of
- The spike moment: the agent notices, acts, explains, and puts a dollar figure on it, with no one asking.
- Rules that hold. Every action respects the EV deadline and comfort limits.
- It runs on real market data. While testing, Chicago power prices went negative, and the screen called it out.
- I built it solo as a finance student.

## What I learned
- How hourly retail pricing passes the wholesale PJM market through to households, why prices sometimes go negative, and why *when* you use power matters as much as *how much*.
- How MCP, Agent Skills, and an agent loop fit together. The skill is the product's judgment and voice; the MCP server is its hands.
- Designing for voice means one sentence out loud and everything else on screen.

## What's next for OffPeak
- Real devices: Alexa smart home control, EV charging APIs, and smart thermostats.
- More utilities and rate plans, starting with other PJM utilities with time-of-use and dynamic rates.
- A "right plan for me?" check that replays a household's real usage against flat, time-of-use, and hourly rates.
- Joining utility peak-rebate events automatically, so cutting usage on stressed days earns money.
- Connecting the MCP server to Alexa+ directly with account linking, and moving the agent onto Amazon Bedrock.

----- end of About the project -----


----- Built with (add each as a tag) -----
python
model-context-protocol
fastmcp
strands-agents
agent-skills
claude
anthropic
amazon-bedrock
fastapi
web-speech-api
comed
pjm


----- "Try it out" links -----
https://github.com/mandoskann/offpeak


----- Image gallery -----
Upload offpeak_thumbnail.png (and any screenshots you like)


----- Video demo link -----
(your YouTube link)


=====================================================================
PAGE: ADDITIONAL INFO
=====================================================================

Upload a File: skip

Submitter Type: Individual
Organization Name: N/A
Submitter Country of Residence: United States
Canada province: N/A

Primary Track: Alexa+

GitHub URL: https://github.com/mandoskann/offpeak

New or existing prior to August 31, 2026: New
(Leave the "existing project" explanation blank)

----- AWS Builder Mini Challenge: Yes -----

----- Which AWS services did you incorporate and how? (paste) -----
OffPeak's agent is built on the Strands Agents SDK, which handles three things at runtime:

1. The agent loop: the Strands Agent decides which MCP tools to call for each request (price checks, planning, the autopilot, settings) and turns the results into short spoken answers.
2. The MCP connection: Strands' MCPClient connects to OffPeak's self-hosted MCP server over Streamable HTTP and loads all 10 tools with their schemas (offpeak/agent.py, offpeak/web.py).
3. Agent Skills: Strands' Agent Skills loader (Skill.from_file with strict validation) loads skills/offpeak/SKILL.md, which defines the agent's voice, tool routing, defaults, and boundaries.

Amazon Bedrock is integrated as a model provider through Strands' BedrockModel (Claude, configurable with OFFPEAK_MODEL_ID). My new AWS account was blocked from Bedrock before the deadline ("Operation not allowed"), so the recorded demo runs Claude through Strands' AnthropicModel. Switching back to Bedrock is one setting in .env. The integration is documented in the README and in docs/FRICTION_LOG.md.

----- Open Source Mini Challenge: No -----


----- [Optional] Feature Requests (paste) -----
1. Hosted Alexa+ MCP test console (Critical): a page where I paste my public /mcp URL and talk to it as Alexa+. That would let me validate the real Alexa+ integration without first building OAuth account linking.

2. Clear Bedrock eligibility status for new accounts (Critical): my new account got "Operation not allowed" for every model with no explanation. A message saying why and for how long, or where to request access, would have kept me on Bedrock.

3. Proactive notifications from MCP servers to Alexa+ (Important): OffPeak's best feature is acting on its own during a price spike. On a real device it needs a way to speak up without being asked.

4. "Always active" option for Strands AgentSkills (Nice-to-have): voice agents with one main skill shouldn't need an extra round trip to activate it.

5. Actionable credentials error in Strands/boto3 (Nice-to-have): suggest `aws login` or a Bedrock API key when no credentials are found.


----- [Optional] Friction Log (URL) -----
https://github.com/mandoskann/offpeak/blob/main/docs/FRICTION_LOG.md


----- [Optional] Project Testing Link -----
https://github.com/mandoskann/offpeak#setup

----- Testing instructions (paste) -----
Everything runs locally; see the README. In short:
1. pip install -r requirements.txt
2. python -m offpeak.server   (MCP server at http://127.0.0.1:8000/mcp)
3. python -m offpeak.web      (open http://127.0.0.1:8080 in Chrome)
"Play a price spike" works with no model credentials. The voice agent needs ANTHROPIC_API_KEY and OFFPEAK_PROVIDER=anthropic in .env, or `aws login` with Bedrock access to Claude. `pytest` runs all 25 tests offline. No login is needed for the app itself.


----- Feedback Question 1: tools, APIs, SDKs and what for (paste) -----
- MCP (spec 2025-11-25+, Streamable HTTP) with FastMCP in Python: the self-hosted OffPeak MCP server with 10 tools for live prices, planning, the autopilot, and spike handling.
- Strands Agents SDK: the agent loop, the MCP client connection, and the Agent Skills loader.
- Agent Skills (agentskills.io format): skills/offpeak/SKILL.md defines OffPeak's voice, tool routing, defaults, and boundaries.
- Amazon Bedrock (Claude via Strands BedrockModel): the planned model provider. Blocked on my new account before the deadline, so the demo runs Claude through Strands' AnthropicModel.
- AWS CLI (aws login): local credentials for Bedrock.
- ComEd Hourly Pricing API (public, third party): live 5-minute prices, day-ahead hourly prices, and settled actuals.


----- Feedback Question 2: what worked well (paste) -----
- Strands + MCP: MCPClient(url=...) connected to my Streamable HTTP server in one line, and list_tools_sync() turned every MCP tool into an agent tool with its schema intact. The smoothest part of the build.
- Strands Agent Skills: a built-in loader with strict validation checked my SKILL.md automatically. I added a test that fails if the skill stops mentioning a tool.
- FastMCP: typed Python functions with Annotated[..., Field(...)] became clean MCP tool schemas with no hand-written JSON.
- Bedrock in Strands: BedrockModel(model_id, region_name) with a sensible default made the model swappable through one environment variable.
- The simulated Alexa+ path: being allowed to simulate the device let me focus on agent behavior instead of hardware.


----- Feedback Question 3: what needs work (paste) -----
- Which MCP version counts: the rules say 2025-11-25 "or a later version, once confirmed," but I couldn't find where confirmed versions are listed. My client and server negotiated a newer version by default.
- Testing against real Alexa+: connecting a self-hosted MCP server needs OAuth account linking, which is a lot for a solo build. A hosted test console would help a lot.
- Credentials error: Strands/boto3 raise "NoCredentialsError: Unable to locate credentials" with no next step. Suggesting aws login would save beginners real time.
- New-account Bedrock block: my new account passed verification but got "ValidationException: Operation not allowed" for every model, Claude and Amazon Nova alike, with no reason or timeline. I had to ship on the Anthropic API.
- Agent Skills on voice: activating a skill through a tool call adds a model round trip, noticeable on voice. I worked around it by loading the skill into the system prompt.


----- Feedback Question 4: onboarding, zero to hello world (paste) -----
- MCP server: about 20 minutes to a working Streamable HTTP server with one tool, tested with a FastMCP client. Very fast.
- Strands agent: about 30 minutes to connect the agent to the MCP server and load the Agent Skill.
- Bedrock: the slowest part, and in the end a blocker. Installing the AWS CLI, signing in, and getting model access took longer than writing the agent, and the new-account restriction stopped me. A single "zero to Claude on Bedrock" checklist in the hackathon resources would help.


----- Feedback Question 5: would you build with these again? (paste) -----
Yes. MCP plus Strands made it realistic for a solo finance student to build a real agent with ten tools, saved state, and autonomous behavior in a few days. The pieces fit together cleanly, and Agent Skills gave me a clear place to put the product's judgment and voice. I'd come back for the real Alexa+ integration once it's easier to test, and I'd like to run it on Bedrock once my account is sorted.


----- Checkboxes -----
Check all three (age of majority, eligible jurisdiction, not an employee of the sponsors).


----- Which AI tools have you leveraged? (paste) -----
Claude (Anthropic) as an AI coding assistant to write and debug the code, which I directed, ran, and tested myself. At runtime, the agent runs Claude through the Strands Agents SDK.

Level of learning: pick the highest option that's true for you (e.g. "Significant").
Gained AI value for your career: Yes.
