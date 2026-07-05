"""Interactive CLI runner for the Restaurant Agent system.

Run with:  python run.py
"""

import asyncio
import os
import sys

from src.agents.main_agent import main_agent

TIMEOUT_SECONDS = int(os.environ.get("AGENT_TIMEOUT", "90"))


async def run_agent(prompt: str) -> str:
    """Invoke the agent with a timeout wrapper for clear error messages."""
    try:
        result = await asyncio.wait_for(
            main_agent.invoke_async(prompt),
            timeout=TIMEOUT_SECONDS,
        )
    except asyncio.TimeoutError:
        return (
            f"⏱️  Agent timed out after {TIMEOUT_SECONDS}s — "
            "Bedrock API may be unreachable. Check network/VPN/firewall "
            "and that the model is enabled in the Bedrock console."
        )

    # result.message is a dict: {"role": "assistant", "content": [{"text": "..."}, ...]}
    text = ""
    if result.message:
        for block in result.message.get("content", []):
            if "text" in block:
                text += block["text"]
    return text


async def main_async():
    print("══════════════════════════════════════════════")
    print("  🍽️  Restaurant Agent (Strands Agents SDK)")
    print("  Powered by Amazon Bedrock AgentCore")
    print("══════════════════════════════════════════════")
    print()
    print("Examples:")
    print('  "Find me a fine dining restaurant in Tokyo"')
    print('  "Where should I eat in Paris?"')
    print('  "I want casual dining in New York"')
    print()
    print('Type "quit" or "exit" to stop.')
    print()

    while True:
        try:
            user_input = input("👤 You: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n👋 Goodbye!")
            break

        if not user_input:
            continue
        if user_input.lower() in ("quit", "exit", "q"):
            print("👋 Goodbye!")
            break

        try:
            text = await run_agent(user_input)
            print(f"\n🤖 Agent: {text}\n")
        except Exception as err:
            print(f"Error: {type(err).__name__}: {err}")


def main():
    try:
        asyncio.run(main_async())
    except KeyboardInterrupt:
        print("\n👋 Goodbye!")
        sys.exit(0)


if __name__ == "__main__":
    main()
