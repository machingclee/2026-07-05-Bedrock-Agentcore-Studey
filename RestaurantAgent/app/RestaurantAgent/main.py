"""AgentCore Runtime entry point — exports the orchestrator agent.

The AgentCore CLI (agentcore deploy) bundles this with esbuild, uploads
as a CodeZip, and wraps it in the HTTP protocol contract (/ping + /invocations).

The orchestrator uses the agents-as-tools pattern:
  User → Main Agent → Restaurant Agent → Restaurant Collaborator
"""
from RestaurantAgent.app.RestaurantAgent.src.agents.main_agent import main_agent as agent
