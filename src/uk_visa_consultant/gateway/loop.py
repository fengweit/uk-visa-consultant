"""Gateway — the channel-agnostic consultant loop.

Stateful: tracks each client's visa route + accumulated documents and runs the
CaseSupervisor so replies carry real gap feedback ("you still need X"), not just
"received". Works identically over WhatsApp, email, or local messages.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import re

from uk_visa_consultant.agent import IntakeAgent
from uk_visa_consultant.evals.output_contract import validate_reply
from uk_visa_consultant.models import Message
from uk_visa_consultant.visas import get_requirement_set
from uk_visa_consultant.workflow.supervisor import CaseSupervisor


def _new_case() -> dict[str, Any]:
    return {"visa_type": None, "documents": [], "name": None, "stay_end": None}


def _infer_route(text: str) -> str | None:
    t = text.lower()
    if "student" in t or "study" in t or "studying" in t or "cas" in t:
        return "student"
    if "spouse" in t or "partner" in t or "family" in t or "married" in t or "marriage" in t:
        return "spouse"
    if "worker" in t or "skilled" in t or "work visa" in t or "cos" in t or "sponsorship" in t:
        return "worker"
    if "visitor" in t or "visit" in t or "tourist" in t or "holiday" in t:
        return "visitor"
    return None


_DATE = re.compile(r"\b(20\d{2})[-/](\d{2})[-/](\d{2})\b")


def _extract_stay_end(text: str) -> str | None:
    """Pull an intended stay-end date from a message ('until 2026-10-05', a range)."""
    matches = _DATE.findall(text)
    if not matches:
        return None
    if len(matches) >= 2 or any(kw in text.lower() for kw in ("until", "depart", "leave", "return")):
        y, m, d = matches[-1]
        return f"{y}-{m}-{d}"
    return None


class Gateway:
    def __init__(self, agent: Any | None = None, supervisor: Any | None = None):
        self.agent = agent or IntakeAgent()
        self.supervisor = supervisor or CaseSupervisor()
        self.cases: dict[str, dict[str, Any]] = {}

    def handle(self, message: Message) -> Message:
        result = self.agent.handle(message)
        key = message.thread_root or message.client_id
        case = self.cases.setdefault(key, _new_case())

        for doc in result.documents:
            if doc.type == "passport" and doc.fields.get("full_name"):
                case["name"] = doc.fields["full_name"]
            case["documents"].append(doc)

        if not case["visa_type"]:
            case["visa_type"] = _infer_route(message.body)
        stay = _extract_stay_end(message.body)
        if stay:
            case["stay_end"] = stay

        if result.escalation:
            reply = result.reply
        elif case["visa_type"] is None:
            reply = self._ask_route(result)
        elif not case["documents"]:
            reply = self._requirements_intro(case["visa_type"])
        else:
            client = {"id": message.client_id, "name": case["name"],
                      "application_date": datetime.now(timezone.utc).date().isoformat(),
                      "stay_end": case.get("stay_end")}
            wr = self.supervisor.run(case["documents"], get_requirement_set(case["visa_type"]), client)
            reply = self._compose_status(wr, result.documents)

        if validate_reply(reply):
            reply = "I'm sorry, I ran into a problem — a specialist will follow up shortly."
        return Message(id=f"{message.id}_reply", client_id=message.client_id,
                       channel=message.channel, body=reply, thread_id=message.thread_id,
                       thread_root=message.thread_root, references=message.references)

    @staticmethod
    def _ask_route(result) -> str:
        base = result.reply or "Thanks for your message."
        return (base + " Which visa route are you applying for — "
                "visitor, student, worker, or spouse/partner?")

    @staticmethod
    def _requirements_intro(visa_type: str) -> str:
        req = get_requirement_set(visa_type)
        docs = ", ".join(r.name.lower() for r in req.requirements)
        return (f"Thanks for getting started. I can help you prepare your {req.route} application. "
                f"We'll work through it together. You'll need: {docs}. "
                "Send one or several files in this thread, and I'll check each one and keep you updated.")

    @staticmethod
    def _compose_status(wr, received_documents=None) -> str:
        gap = wr.gap_report
        received = list(received_documents or [])
        if received:
            labels = sorted({d.type.replace("_", " ") for d in received})
            received_line = "Thanks for sending your " + ", ".join(labels) + ". I've checked " + (
                "it." if len(received) == 1 else "them."
            )
        else:
            received_line = "Thanks for checking in. I've reviewed your application so far."

        if wr.final_state == "delivered":
            return (received_line + " Good news: all required documents are verified, "
                    "and your application package is ready to submit.")
        if wr.final_state == "parked":
            return (received_line + " One item needs a specialist review before we continue. "
                    "I've flagged it, and we'll follow up with you shortly.")

        failing = [i for i in gap.items if i.verdict != "OK"]
        passing = [i for i in gap.items if i.verdict == "OK"]
        lines = [received_line]
        if passing:
            lines.append("You're making good progress. Here's what we still need:")
        else:
            lines.append("I found a few things we need to work through:")
        for i in failing:
            lines.append(f"  • {i.req_name}: {i.action or i.verdict.lower()}")
        lines.append("Send these when you're ready, and I'll check them in this same thread.")
        return "\n".join(lines)
