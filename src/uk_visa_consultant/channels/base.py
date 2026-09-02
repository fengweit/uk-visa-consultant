"""ChannelAdapter — the transport boundary between the agent and the client.

Every inbound channel (WhatsApp, email, local test harness) is normalized into
a canonical `Message`; outbound messages are routed back through the originating
channel. This layer is transport only — zero business logic.

Contract (docs/specs/comms-layer.md):

    receive()    -> list[Message]       pull new inbound messages
    send(Message) -> SendReceipt         route one outbound message
    send_media(path, mime) -> SendReceipt  send a media payload
"""
from __future__ import annotations

from abc import ABC, abstractmethod

from uk_visa_consultant.models import Channel, Message, SendReceipt


class ChannelAdapter(ABC):
    """Abstract adapter. Concrete adapters pin `channel` and implement the trio."""

    channel: Channel

    @abstractmethod
    def receive(self) -> list[Message]:
        """Pull new inbound messages, normalized to the canonical type."""
        raise NotImplementedError

    @abstractmethod
    def send(self, message: Message) -> SendReceipt:
        """Route one outbound message. Failures return ``ok=False`` + ``error``;
        never silently drop (docs/specs/comms-layer.md — "no partial sends")."""
        raise NotImplementedError

    @abstractmethod
    def send_media(self, local_path: str, mime: str, recipient: str | None = None) -> SendReceipt:
        """Send a media payload referenced by ``local_path``.

        ``recipient`` is the channel-specific destination (email address, wa phone
        number, ...). The LocalAdapter ignores it.
        """
        raise NotImplementedError


class ChannelError(Exception):
    """Raised on channel-level violations (e.g. template-vs-freeform)."""
