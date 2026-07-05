from bedrock_agentcore.runtime import BedrockAgentCoreApp
from src.agents.main_agent import main_agent

app = BedrockAgentCoreApp()
log = app.logger


@app.entrypoint
async def invoke(payload, context):
    prompt = payload.get("prompt", "")

    async for event in main_agent.stream_async(prompt):
        yield event


if __name__ == "__main__":
    app.run()
