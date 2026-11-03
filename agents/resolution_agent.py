"""Resolution Agent: writes the customer-facing reply."""
from autogen_agentchat.agents import AssistantAgent

RESOLUTION_SYSTEM_MESSAGE = """You are the Resolution Agent. Write a polite, clear reply to the customer
using ONLY facts from the passages the Knowledge Base Agent found.

Rules:
- Do not invent policies, timelines, prices or links.
- If no passages were found, say honestly that you could not find the answer in our policies,
  that a specialist will follow up, and set confidence to Low.
- Keep the reply under 150 words and address the customer by first name if it is known.

Format:
Write the customer reply first. Then, on the last line, write:
CONFIDENCE: High, Medium or Low

High = the passages directly answer the question.
Medium = the passages partly answer it.
Low = they do not answer it."""


def build_resolution_agent(model_client) -> AssistantAgent:
    return AssistantAgent(
        name="ResolutionAgent",
        model_client=model_client,
        description="Writes a customer reply grounded only in the retrieved passages.",
        system_message=RESOLUTION_SYSTEM_MESSAGE,
    )
