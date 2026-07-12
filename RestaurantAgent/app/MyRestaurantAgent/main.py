import os
import logging
from fastapi import FastAPI, Request
from fastapi.responses import StreamingResponse, JSONResponse
from ag_ui_strands import StrandsAgent
from ag_ui_strands.config import StrandsAgentConfig
from ag_ui.core import RunAgentInput
from ag_ui.encoder import EventEncoder

# ═══════════════════════════════════════════════════════════════════════
# Lightweight module-level code — env vars only, no network I/O.
# The heavy imports and agent construction are deferred to _build_agent()
# so the runtime initializes within the 30 s window.
# ═══════════════════════════════════════════════════════════════════════

REGION = os.getenv("AWS_REGION", "us-east-1")
MEMORY_ID = os.getenv("MEMORY_RESTAURANTMEMORY_ID", os.getenv("MEMORY_ID", ""))

logger = logging.getLogger(__name__)
app = FastAPI()

# ── Lazy agent singleton ────────────────────────────────────────────────
_agui_agent = None
_retrieval_config = None


def _get_retrieval_config() -> dict:
    """Build retrieval_config dynamically from the Memory's actual strategies.

    ``retrieve_memories`` namespace_path prefix matching only works at
    complete path-segment boundaries, so we must use the full strategy ID
    (e.g. ``user_facts-hjzEEY65uj``), not just the name.  We query the
    Memory once per cold start and cache the result.
    """
    global _retrieval_config
    if _retrieval_config is not None:
        return _retrieval_config

    from bedrock_agentcore.memory import MemoryClient
    from bedrock_agentcore.memory.integrations.strands.config import (
        RetrievalConfig,
    )

    client = MemoryClient(region_name=REGION)
    strategies = client.get_memory_strategies(MEMORY_ID)
    print("Retrieved strategies from Memory:", strategies)

    # Per-strategy overrides — keyed by strategy "name" from agentcore.json
    overrides: dict[str, dict] = {
        "user_facts":               dict(top_k=10, relevance_score=0.25),
        "conversation_summaries":   dict(top_k=5,  relevance_score=0.4),
    }
    defaults = dict(top_k=5, relevance_score=0.3)

    _retrieval_config = {}
    for s in strategies:

        name = s["name"]
        opts = overrides.get(name, defaults)
        template = s["namespaceTemplates"][0]
        _retrieval_config[template] = RetrievalConfig(
            top_k=opts["top_k"],
            relevance_score=opts["relevance_score"],
            strategy_id=s["strategyId"],
        )
    return _retrieval_config


async def session_manager_provider(input_data: RunAgentInput):
    """Called once per request — actor_id and session_id are dynamic.

    ``actor_id`` answers "who is talking" and should come from auth
    (JWT claim, API key).  ``session_id`` scopes the memory partition
    within that actor.  Together with ``memory_id`` they form the
    three-part address ``(memory_id, actor_id, session_id)``.
    """
    from bedrock_agentcore.memory.integrations.strands.session_manager import (
        AgentCoreMemorySessionManager,
    )
    from bedrock_agentcore.memory.integrations.strands.config import (
        AgentCoreMemoryConfig,
    )

    thread_id = input_data.thread_id or "default"

    # Resolve actor_id from forwardedProps (set by the frontend) or
    # from the JWT authorizer claims once available.
    forwarded = input_data.forwarded_props or {}
    logger.info("forwardedProps: %s", forwarded)
    actor_id = forwarded.get("userId") or "anonymous"

    return AgentCoreMemorySessionManager(
        agentcore_memory_config=AgentCoreMemoryConfig(
            memory_id=MEMORY_ID,
            actor_id=actor_id,       # per-user — dynamic
            session_id=thread_id,    # per-conversation — dynamic
            retrieval_config=_get_retrieval_config(),
            batch_size=10,
        ),
        region_name=REGION,
    )


def _build_agent():
    """Deferred agent construction — runs on first request."""
    from src.agents.main_agent import main_agent

    return StrandsAgent(
        agent=main_agent,
        name="restaurant_agent",
        description=(
            "Find restaurants for a user based on city and fine-dining preference. "
            "Handles determining city and dining preference, then returns matching "
            "restaurant recommendations."
        ),
        config=StrandsAgentConfig(
            session_manager_provider=session_manager_provider,
        ),
    )


def _get_agent():
    global _agui_agent
    if _agui_agent is None:
        _agui_agent = _build_agent()
    return _agui_agent


@app.post("/invocations")
async def invocations(input_data: dict, request: Request):
    accept_header = request.headers.get("accept")
    encoder = EventEncoder(accept=accept_header)

    async def event_generator():
        run_input = RunAgentInput(**input_data)
        async for event in _get_agent().run(run_input):
            yield encoder.encode(event)

    return StreamingResponse(
        event_generator(),
        media_type=encoder.get_content_type(),
    )


@app.get("/ping")
async def ping():
    return JSONResponse({"status": "Healthy"})


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8080)
