"""Intake agent: Message → Intent → route → AgentResult.

This is the first agent layer — it wires intent recognition to the intake
(document-parsing) path. Gap analysis, assembly, and the delivery loop plug in
behind it as later modules.
"""
from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from uk_visa_consultant.intents.intent import IntentRecognizer
from uk_visa_consultant.models import Document, Message
from uk_visa_consultant.parsing.pipeline import intake


class AgentResult(BaseModel):
    intent: str
    action: str  # parse_document | request_document | answer_query | escalate | general | status
    documents: list[Document] = Field(default_factory=list)
    reply: str = ""
    escalation: bool = False
    needs_clarification: bool = False


class IntakeAgent:
    def __init__(self, llm: Any | None = None, recognizer: IntentRecognizer | None = None):
        self.llm = llm
        self.recognizer = recognizer or IntentRecognizer(llm)

    def handle(self, message: Message) -> AgentResult:
        intent = self.recognizer.recognize(message.body)

        if intent.intent == "escalate_human":
            return AgentResult(
                intent=intent.intent, action="escalate", escalation=True,
                reply="I've flagged this for a specialist — we'll be in touch shortly.",
            )

        if intent.intent == "submit_document":
            if not message.attachments:
                return AgentResult(
                    intent=intent.intent, action="request_document",
                    reply="Got it — please attach the document so I can check it.",
                    needs_clarification=intent.needs_clarification,
                )
            docs = [intake(a.local_path, a.mime, llm=self.llm) for a in message.attachments]
            types = ", ".join(sorted({d.type for d in docs}))
            return AgentResult(
                intent=intent.intent, action="parse_document", documents=docs,
                reply=f"Received and checked your document(s): {types}.",
            )

        if intent.intent == "document_query":
            return AgentResult(intent=intent.intent, action="answer_query", reply=self._docs_reply())

        if intent.intent == "gap_question":
            return AgentResult(
                intent=intent.intent, action="explain_gap",
                reply="Let me check what's outstanding on your case and I'll explain exactly what to fix.",
            )

        if intent.intent == "status_check":
            return AgentResult(
                intent=intent.intent, action="status",
                reply="Your case is being assembled — I'll flag anything outstanding.",
            )

        # schedule / general
        return AgentResult(
            intent=intent.intent, action="general",
            reply="Thanks — I've logged that. Anything else I can help with?",
            needs_clarification=intent.needs_clarification,
        )

    @staticmethod
    def _docs_reply() -> str:
        return (
            "Typical documents: passport, proof of funds (recent bank statements), "
            "evidence of employment or income, accommodation, and English/TB certificates "
            "where required. Attach any of these and I'll check it against your route."
        )
