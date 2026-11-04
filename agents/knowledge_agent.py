"""Knowledge Base Agent: finds the relevant company documents."""
from autogen_agentchat.agents import AssistantAgent

from agents.kb_search import search_kb

KNOWLEDGE_SYSTEM_MESSAGE = """You are the Knowledge Base Agent.
Using the category and summary from the Query Agent, call the search_kb tool with a short
query made of the key problem words (not the whole complaint).
Use policy words (for example return, refund, delivery, late, password, login, warranty,
damaged) rather than product names such as "bag" or "book". If the tool returns NO_MATCH,
call it ONE more time with different policy words before giving up.

Then reply in this format:
KB_SOURCES: comma-separated file names returned by the tool, or none
PASSAGES: the most relevant passages, each labelled with its file name.

If the tool returns NO_MATCH, reply with KB_SOURCES: none and say that no matching document
was found. Never invent policy text."""


def build_knowledge_agent(model_client) -> AssistantAgent:
    return AssistantAgent(
        name="KnowledgeAgent",
        model_client=model_client,
        description="Searches the company knowledge base and returns matching passages with file names.",
        system_message=KNOWLEDGE_SYSTEM_MESSAGE,
        tools=[search_kb],
        max_tool_iterations=2,  # allows one retry after NO_MATCH
        reflect_on_tool_use=True,
    )
