# Product Feedback

## Which developer tools, APIs, and SDKs I used, and for what
| Tool | Used for |
|---|---|
| **Model Context Protocol** (spec 2025-11-25+, Streamable HTTP) via **FastMCP** (Python) | The self-hosted OffPeak MCP server: 10 tools covering live prices, the planner, the autopilot, and spike handling |
| **Strands Agents SDK** | The agent loop, the MCP client connection to the server, and the Agent Skills loader (`Skill.from_file`, strict validation) |
| **Amazon Bedrock** (Claude) | The planned model provider (`BedrockModel`). Blocked on my new account before the deadline, so the demo runs Claude via the Anthropic API through Strands' `AnthropicModel` |
| **Agent Skills** (agentskills.io format) | `skills/offpeak/SKILL.md`: voice persona, tool routing, defaults, autopilot rules, boundaries |
| **AWS CLI** (`aws login`) | Local credentials for Bedrock |
| **ComEd Hourly Pricing API** (third party, public) | Live 5-minute prices, day-ahead hourly estimates, settled actuals |

## What worked well
- **Strands + MCP.** `MCPClient(url=...)` connected to a Streamable HTTP server in one line, and `list_tools_sync()` turned every MCP tool into an agent tool with its schema intact. This was the smoothest part of the build.
- **Strands Agent Skills.** A built-in, spec-compliant loader with strict validation meant my SKILL.md was checked automatically (name rules, frontmatter). I added a test that fails if the skill stops mentioning a tool.
- **FastMCP.** Typed Python functions with `Annotated[..., Field(...)]` became clean MCP tool schemas, with no hand-written JSON schema.
- **Bedrock in Strands.** A sensible default Claude model ID and a simple `BedrockModel(model_id, region_name)` made the model swappable through one environment variable.
- **The simulated Alexa+ path.** Being allowed to simulate the device let me focus on agent behavior instead of hardware.

## What needs work
- **Which MCP version counts?** The rules say 2025-11-25 "or a later version, once confirmed," but I couldn't find where confirmed versions are listed. My client and server negotiated a newer revision by default. A one-line compatibility statement, or a conformance check, would remove the guesswork.
- **No way to test against real Alexa+ without account linking.** To connect a self-hosted MCP server to Alexa+ you need OAuth account linking, which is a lot for a solo hackathon build. A hosted "Alexa+ MCP test console" where you paste a public `/mcp` URL and talk to it would let developers validate the real integration in minutes.
- **The credentials error is a dead end for beginners.** Strands/boto3 raise `NoCredentialsError: Unable to locate credentials` with no next step. Suggesting `aws login` (or a Bedrock API key) in that message would save new developers real time.
- **New accounts can't use Bedrock, and the error doesn't say why.** After I lost access to my original account, the new account I created passed verification but still got `ValidationException: Operation not allowed` for every model, Claude and Amazon Nova alike. Nothing said what to do or how long it would last. A clear message ("new accounts can call Bedrock after X" or "request access here") would have saved hours. I shipped on the Anthropic API instead.
- **Agent Skills and voice latency.** Progressive disclosure (activate the skill through a tool call) adds a model round trip, which is noticeable on voice. An "always active" option on the AgentSkills plugin would help voice agents. I worked around it by loading the skill's instructions into the system prompt.

## Onboarding (zero to hello world)
- **MCP server:** about 20 minutes to a working Streamable HTTP server with one tool, tested with a FastMCP client. Very fast.
- **Agent on Strands:** about 30 minutes to connect the agent to the MCP server and load the Agent Skill.
- **Bedrock access:** the slowest part, and in the end a blocker. Installing the AWS CLI, signing in, and confirming model access in us-east-1 took longer than writing the agent. A single "zero to Claude on Bedrock" checklist inside the hackathon resources would help.

## Would I build with these again?
**Yes.** MCP plus Strands made it realistic for a solo finance student to build a real agent with ten tools, persistent state, and autonomous behavior in a few days. The pieces fit together cleanly, and Agent Skills gave me a clear place to put the product's judgment and voice. I'd come back for the real Alexa+ integration once it's easier to test.

## Feature requests
| Request | Why it matters for OffPeak | Priority |
|---|---|---|
| Hosted Alexa+ MCP test console (paste an `/mcp` URL, talk to it) | Validate the real Alexa+ integration without building OAuth account linking first | Critical |
| Proactive notifications from MCP servers to Alexa+ | OffPeak's best feature is acting on its own during a price spike; it needs a way to speak up unprompted on a real device | Important |
| "Always active" mode for Strands AgentSkills | Avoids an extra round trip for voice agents with one primary skill | Nice-to-have |
| Actionable credentials error in Strands/boto3 (suggest `aws login`) | Faster onboarding for first-time AWS users | Nice-to-have |
| Clear Bedrock eligibility status for new accounts (instead of "Operation not allowed") | I couldn't run my agent on Bedrock before the deadline and had no idea why or for how long | Critical |
