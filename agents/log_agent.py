"""Log Agent: saves every ticket and hands complicated cases to a human."""
from datetime import datetime

from autogen_agentchat.agents import AssistantAgent

from agents.ticket_store import append_ticket, decide_escalation

LOG_SYSTEM_MESSAGE = """You are the Log Agent.
Using the conversation so far, call log_ticket exactly once:
- ticket_id: the Ticket ID given in the task
- fill every other argument from the earlier agents' output
- response: the customer reply text only (without the CONFIDENCE line)
- confidence: the level from the Resolution Agent
- kb_sources: the KB_SOURCES value from the Knowledge Base Agent, or none

After the tool returns, reply with the single word LOGGED. Do not call the tool twice."""


def log_ticket(ticket_id: str, customer_name: str, order_id: str, complaint: str,
               category: str, urgency: str, sentiment: str, summary: str,
               kb_sources: str, response: str, confidence: str) -> str:
    """Save one ticket to the log file and set its status (Resolved or Escalated).

    Call this exactly once per complaint, after the reply has been written.
    """
    status, reason = decide_escalation(
        complaint=complaint,
        urgency=urgency,
        sentiment=sentiment,
        kb_sources=kb_sources,
        confidence=confidence,
    )
    append_ticket({
        "ticket_id": ticket_id,
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "customer_name": customer_name,
        "order_id": order_id,
        "complaint": complaint,
        "category": category,
        "urgency": urgency,
        "sentiment": sentiment,
        "summary": summary,
        "kb_sources": kb_sources,
        "response": response,
        "confidence": confidence,
        "status": status,
        "escalation_reason": reason,
    })
    return f"Ticket {ticket_id} saved. Status: {status}."


def build_log_agent(model_client) -> AssistantAgent:
    return AssistantAgent(
        name="LogAgent",
        model_client=model_client,
        description="Records every ticket in the log file and applies the escalation rules.",
        system_message=LOG_SYSTEM_MESSAGE,
        tools=[log_ticket],
        reflect_on_tool_use=True,
    )
