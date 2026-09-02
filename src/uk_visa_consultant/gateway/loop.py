"""Gateway — the channel-agnostic conversation loop.

Takes an inbound `Message` (any channel), runs it through the agent, and returns
a reply `Message` on the same channel. This is the single wiring point the
WhatsApp webhook and the email poller both call, so the channels stay thin and
the loop is testable over a LocalAdapter with no network.
"""
from __future__ import annotations

from typing import Any

from uk_visa_consultant.agent import IntakeAgent
from uk_visa_consultant.models import Message


class Gateway:
    def __init__(self, agent: Any | None = None):
        self.agent = agent or IntakeAgent()

    def handle(self, message: Message) -> Message:
        result = self.agent.handle(message)
        return Message(
            id=f"{message.id}_reply",
            client_id=message.client_id,
            channel=message.channel,
            body=result.reply,
        )
