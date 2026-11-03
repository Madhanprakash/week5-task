"""Wires the four agents into one AutoGen team and runs a complaint through it."""
import os

from autogen_agentchat.conditions import MaxMessageTermination, TextMentionTermination
from autogen_agentchat.messages import TextMessage
from autogen_agentchat.teams import RoundRobinGroupChat
from autogen_ext.models.openai import OpenAIChatCompletionClient
from dotenv import load_dotenv

from agents.knowledge_agent import build_knowledge_agent
from agents.log_agent import build_log_agent
from agents.query_agent import build_query_agent
from agents.resolution_agent import build_resolution_agent
from agents.ticket_store import next_ticket_id

load_dotenv()


def build_model_client():
    return OpenAIChatCompletionClient(model=os.getenv("OPENAI_MODEL", "gpt-4o-mini"))


def build_team(model_client) -> RoundRobinGroupChat:
    # Round-robin order: Query -> Knowledge -> Resolution -> Log.
    participants = [
        build_query_agent(model_client),
        build_knowledge_agent(model_client),
        build_resolution_agent(model_client),
        build_log_agent(model_client),
    ]
    # Stop once the Log Agent says LOGGED; the message cap is a safety net.
    termination = TextMentionTermination("LOGGED") | MaxMessageTermination(12)
    return RoundRobinGroupChat(participants=participants, termination_condition=termination)


async def run_ticket(customer_name: str, order_id: str, complaint: str, on_message=None) -> dict:
    """Run one complaint through the team.

    on_message(source, content) is called for every agent message as it arrives,
    so the UI can show each step live.
    """
    ticket_id = next_ticket_id()
    task = (
        f"New customer complaint. Ticket ID: {ticket_id}\n"
        f"Customer name: {customer_name.strip() or 'Not given'}\n"
        f"Order ID: {order_id.strip() or 'Not given'}\n"
        f"Complaint: {complaint.strip()}"
    )

    client = build_model_client()
    messages = []
    try:
        team = build_team(client)
        async for event in team.run_stream(task=task):
            if isinstance(event, TextMessage) and event.source != "user":
                messages.append({"source": event.source, "content": event.content})
                if on_message:
                    on_message(event.source, event.content)
    finally:
        await client.close()

    return {"ticket_id": ticket_id, "messages": messages}
