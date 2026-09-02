"""LocalAdapter — in-process channel for driving the core loop end-to-end.

No network: inbound messages are enqueued by the harness, outbound messages and
media are recorded to in-memory lists the harness asserts on.
"""
from __future__ import annotations

from uk_visa_consultant.channels.base import ChannelAdapter
from uk_visa_consultant.models import Attachment, Channel, Message, SendReceipt


class LocalAdapter(ChannelAdapter):
    channel = Channel.LOCAL

    def __init__(self) -> None:
        self._inbox: list[Message] = []
        self._outbox: list[Message] = []
        self._media: list[tuple[str, str]] = []  # (local_path, mime)
        self._seen: set[str] = set()

    # -- harness helpers ---------------------------------------------------
    def enqueue(
        self,
        body: str,
        *,
        client_id: str,
        message_id: str | None = None,
        attachments: list[Attachment] | None = None,
    ) -> Message:
        """Push one inbound message into the queue (test-harness entry point)."""
        mid = message_id or f"local_{len(self._inbox) + 1}_{client_id}"
        message = Message(
            id=mid,
            client_id=client_id,
            channel=Channel.LOCAL,
            body=body,
            attachments=attachments or [],
        )
        self._inbox.append(message)
        return message

    # -- ChannelAdapter ----------------------------------------------------
    def receive(self) -> list[Message]:
        """Drain the queue, deduping by ``Message.id`` (idempotent re-delivery)."""
        out: list[Message] = []
        for message in self._inbox:
            if message.id in self._seen:
                continue
            self._seen.add(message.id)
            out.append(message)
        self._inbox.clear()
        return out

    def send(self, message: Message) -> SendReceipt:
        self._outbox.append(message)
        return SendReceipt(ok=True, external_id=message.id)

    def send_media(self, local_path: str, mime: str, recipient: str | None = None) -> SendReceipt:
        self._media.append((local_path, mime))
        return SendReceipt(ok=True, external_id=None)

    # -- harness observability --------------------------------------------
    @property
    def outbox(self) -> list[Message]:
        return list(self._outbox)

    @property
    def sent_media(self) -> list[tuple[str, str]]:
        return list(self._media)
