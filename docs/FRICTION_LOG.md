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
