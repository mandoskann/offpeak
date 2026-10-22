"""OffPeak agent: Claude on Amazon Bedrock, driven by the OffPeak Agent Skill,
calling the OffPeak MCP server over Streamable HTTP.

    Person (text now, voice on Day 5)
        -> Strands agent (Claude on Amazon Bedrock)
             system prompt = skills/offpeak/SKILL.md (Agent Skill)
        -> MCP client (Streamable HTTP)
        -> OffPeak MCP server (live ComEd prices + planner)

Run (with the MCP server already running in another terminal):
    python -m offpeak.agent                    # chat in the terminal
    python -m offpeak.agent "when should I charge my car?"   # one question

Needs AWS credentials (run `aws login`) and Bedrock access to a Claude model.
"""

from __future__ import annotations

import os
import sys
import time
from pathlib import Path

from dotenv import load_dotenv
from strands import Agent
from strands.models import BedrockModel
from strands.tools.mcp import MCPClient
from strands.vended_plugins.skills import Skill

from offpeak import comed

load_dotenv()

ROOT = Path(__file__).resolve().parent.parent
SKILL_DIR = ROOT / "skills" / "offpeak"

MCP_URL = os.getenv("OFFPEAK_URL", "http://127.0.0.1:8000/mcp")
MODEL_ID = os.getenv("OFFPEAK_MODEL_ID", "global.anthropic.claude-sonnet-4-6")
REGION = os.getenv("AWS_REGION", "us-east-1")


def load_skill() -> Skill:
    """Load and validate the OffPeak Agent Skill (agentskills.io format)."""
    return Skill.from_file(SKILL_DIR, strict=True)


def system_prompt(skill: Skill) -> str:
    # The skill is always relevant to this agent, so its full instructions go
    # straight into the system prompt (no extra "activate skill" round trip,
    # which matters for voice latency).
    return f"<skill name=\"{skill.name}\">\n{skill.instructions}\n</skill>"


def with_clock(text: str) -> str:
    """Prefix the message with the current Chicago time so 'tonight' makes sense."""
    stamp = comed.now().strftime("%A %I:%M %p Central").replace(" 0", " ")
    return f"[Current time: {stamp}]\n{text}"


def tools_used(agent: Agent, since: int) -> list[str]:
    """Names of MCP tools the agent called since message index `since`."""
    names = []
    for msg in agent.messages[since:]:
        for block in msg.get("content", []):
            if "toolUse" in block:
                names.append(block["toolUse"]["name"])
    return names


def provider() -> str:
    """'bedrock' (default) or 'anthropic'. Auto-picks Anthropic if only that key is set."""
    choice = os.getenv("OFFPEAK_PROVIDER", "").strip().lower()
    if choice in {"bedrock", "anthropic"}:
        return choice
    return "anthropic" if os.getenv("ANTHROPIC_API_KEY") and not os.getenv("AWS_PROFILE") else "bedrock"


def build_model():
    if provider() == "anthropic":
        from strands.models.anthropic import AnthropicModel

        return AnthropicModel(
            model_id=os.getenv("OFFPEAK_ANTHROPIC_MODEL", "claude-sonnet-4-6"),
            max_tokens=600,
            params={"temperature": 0.3},
        )
    return BedrockModel(model_id=MODEL_ID, region_name=REGION, temperature=0.3, max_tokens=600)


def model_label() -> str:
    if provider() == "anthropic":
        return f"Anthropic API · {os.getenv('OFFPEAK_ANTHROPIC_MODEL', 'claude-sonnet-4-6')}"
    return f"Amazon Bedrock · {MODEL_ID}"


def tool_results(agent: Agent, since: int) -> list[dict]:
    """[{name, data}] for each tool the agent called since `since`, data parsed from JSON."""
    import json

    names, out = {}, []
    for msg in agent.messages[since:]:
        for block in msg.get("content", []):
            if "toolUse" in block:
                names[block["toolUse"]["toolUseId"]] = block["toolUse"]["name"]
            elif "toolResult" in block:
                res = block["toolResult"]
                data = None
                for item in res.get("content", []):
                    if "json" in item:
                        data = item["json"]
                    elif "text" in item and data is None:
                        try:
                            data = json.loads(item["text"])
                        except (ValueError, TypeError):
                            pass
                out.append({"name": names.get(res.get("toolUseId"), "?"), "data": data})
    return out


def build_agent(mcp: MCPClient) -> Agent:
    skill = load_skill()
    model = build_model()
    return Agent(
        name="OffPeak",
        model=model,
        system_prompt=system_prompt(skill),
        tools=mcp.list_tools_sync(),
        callback_handler=None,  # we print the final answer ourselves
    )


def ask(agent: Agent, text: str) -> tuple[str, list[str], float]:
    start_idx = len(agent.messages)
    t0 = time.perf_counter()
    result = agent(with_clock(text))
    elapsed = time.perf_counter() - t0
    return str(result).strip(), tools_used(agent, start_idx), elapsed


def main() -> None:
    mcp = MCPClient(url=MCP_URL)
    try:
        mcp.start()
    except Exception as exc:
        sys.exit(f"Couldn't connect to the OffPeak MCP server at {MCP_URL}.\n"
                 f"Start it first with: python -m offpeak.server\n({exc})")

    try:
        agent = build_agent(mcp)
        print(f"OffPeak agent ready · {model_label()} · {len(agent.tool_names)} tools · MCP {MCP_URL}")

        one_shot = " ".join(sys.argv[1:]).strip()
        questions = [one_shot] if one_shot else None

        while True:
            if questions is not None:
                if not questions:
                    break
                text = questions.pop(0)
                print(f"\nyou: {text}")
            else:
                try:
                    text = input("\nyou: ").strip()
                except (EOFError, KeyboardInterrupt):
                    break
                if text.lower() in {"", "quit", "exit", "bye"}:
                    break

            try:
                answer, used, secs = ask(agent, text)
            except Exception as exc:
                print(f"\n[error] {type(exc).__name__}: {exc}")
                print("Check your model credentials: `aws sts get-caller-identity` for Bedrock, or ANTHROPIC_API_KEY in .env.")
                continue
            print(f"offpeak: {answer}")
            print(f"   ↳ tools: {', '.join(used) or 'none'} · {secs:.1f}s")
    finally:
        mcp.stop(None, None, None)


if __name__ == "__main__":
    main()
