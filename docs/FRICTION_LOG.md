# Friction Log

One entry per real snag. Format follows the hackathon's friction log fields: task, steps, expected vs. actual, severity, workaround, suggestion.

Severity: 🔴 Blocker · 🟠 Major · 🟡 Minor · ⚪ Papercut

---

### 1. Which MCP protocol version does the Alexa+ track actually want?
- **Date:** Oct 14, 2026 (Day 1)
- **Tool:** Alexa+ track requirements / MCP Python SDK (FastMCP 4.1)
- **Task:** Make sure the server meets the "MCP spec 2025-11-25 over Streamable HTTP" requirement.
- **Steps:** Built a FastMCP server, connected with the FastMCP client, printed the negotiated protocol version.
- **Expected:** A clear way to confirm the server is compliant with 2025-11-25.
- **Actual:** Client and server negotiated `2026-07-28` by default. The rules say "2025-11-25 (or a later version, once confirmed)," but I couldn't find where "confirmed" later versions are listed, so it's unclear whether the default is fine or whether I should pin the older version.
- **Severity:** 🟡 Minor
- **Workaround:** Kept the default, since MCP negotiates down when a client asks for 2025-11-25. Documented the version in the README.
- **Suggestion:** Publish a short compatibility note for the Alexa+ track listing accepted protocol versions, plus a one-command conformance check (e.g. an Inspector preset) that confirms a server is Alexa+-ready.

### 2. FastMCP client attribute from older examples returns nothing
- **Date:** Oct 14, 2026 (Day 1)
- **Tool:** FastMCP 4.1 (Python)
- **Task:** Print server name and protocol version from a test client.
- **Steps:** Followed an older example using `client.initialize_result.serverInfo`.
- **Expected:** Server info object.
- **Actual:** `AttributeError: 'NoneType' object has no attribute 'serverInfo'`. The connection itself worked fine.
- **Severity:** ⚪ Papercut
- **Workaround:** Used `client.server_info` and `client.protocol_version` instead.
- **Suggestion:** Hackathon resources could link to version-pinned quickstarts so participants don't mix examples across FastMCP major versions.

### 3. "Unable to locate credentials" with no next step
- **Date:** Oct 14, 2026
- **Tool:** Strands Agents SDK + Amazon Bedrock (boto3)
- **Task:** Run the agent against Claude on Bedrock for the first time.
- **Steps:** Installed `strands-agents` and `boto3`, built a `BedrockModel`, asked the agent a question.
- **Expected:** Either a response, or an error telling me how to authenticate.
- **Actual:** `NoCredentialsError: Unable to locate credentials`. As a first-time AWS developer I didn't know whether to install the AWS CLI, create access keys, or something else.
- **Severity:** 🟠 Major (blocked the agent until resolved)
- **Workaround:** Installed the AWS CLI with Homebrew and used `aws login` (browser-based console credentials).
- **Suggestion:** Have Strands' `BedrockModel` catch this and suggest `aws login`, or a Bedrock API key via `AWS_BEARER_TOKEN_BEDROCK`. Link a "zero to Claude on Bedrock" checklist from the hackathon resources.

### 4. Losing account access cut off Bedrock entirely
- **Date:** Oct 22, 2026
- **Tool:** AWS account sign-in / Amazon Bedrock
- **Task:** Sign in with `aws login` to get credentials for Bedrock.
- **Steps:** Ran `aws login`, got sent to the browser sign-in, couldn't remember the root password, and the reset flow didn't work for me.
- **Expected:** A recovery path that gets a developer back to building within minutes.
- **Actual:** No way to reach Bedrock the day before the deadline.
- **Severity:** 🔴 Blocker (for the Bedrock path)
- **Workaround:** Made the agent provider-agnostic. Strands' `AnthropicModel` serves as a fallback behind one environment variable (`OFFPEAK_PROVIDER`).
- **Suggestion:** Surface account-recovery troubleshooting directly in the `aws login` browser flow, and mention Bedrock API keys as a fast credential option in hackathon onboarding.

### 5. Agent Skills progressive disclosure adds latency on voice
- **Date:** Oct 14, 2026
- **Tool:** Strands Agents SDK, `AgentSkills` plugin
- **Task:** Give a voice agent its Agent Skill.
- **Steps:** Read the AgentSkills plugin: it injects skill metadata into the system prompt, and the model calls a `skills` tool to load full instructions.
- **Expected:** A way to mark one skill as always active.
- **Actual:** Activation takes an extra model round trip on every new conversation. That's noticeable when someone is waiting for a voice answer.
- **Severity:** 🟡 Minor
- **Workaround:** Loaded the skill with `Skill.from_file(strict=True)` and put its instructions in the system prompt directly.
- **Suggestion:** Add an `always_active=[...]` option to `AgentSkills` that inlines the chosen skills' instructions.

### 6. Hard to test a self-hosted MCP server against real Alexa+
- **Date:** Oct 22, 2026
- **Tool:** Alexa+ (MCP add-on path)
- **Task:** Try OffPeak's MCP server on actual Alexa+.
- **Steps:** Reviewed what's needed: a public HTTPS `/mcp` endpoint plus OAuth account linking.
- **Expected:** A lightweight way to point Alexa+ (or a test console) at an MCP URL during development.
- **Actual:** Building the OAuth issuer was out of scope for a solo build with no Alexa+ device, so I used the allowed simulated-experience path.
- **Severity:** 🟠 Major
- **Workaround:** Built a browser Echo Show simulation that uses the same MCP server and agent.
- **Suggestion:** A hosted Alexa+ MCP test console, and a dev mode that skips account linking for a developer's own account.

---

<!-- Template: copy for each new entry
### N. Title
- **Date:**
- **Tool:**
- **Task:**
- **Steps:**
- **Expected:**
- **Actual:**
- **Severity:**
- **Workaround:**
- **Suggestion:**
-->
