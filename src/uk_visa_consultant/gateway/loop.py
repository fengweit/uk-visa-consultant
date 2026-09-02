"""Gateway — the channel-agnostic consultant loop.

Stateful: tracks each client's visa route + accumulated documents and runs the
CaseSupervisor so replies carry real gap feedback ("you still need X"), not just
"received". Works identically over WhatsApp, email, or local messages.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from uk_visa_consultant.agent import IntakeAgent
from uk_visa_consultant.models import Message
from uk_visa_consultant.visas import get_requirement_set
from uk_visa_consultant.workflow.supervisor import CaseSupervisor


def _new_case() -> dict[str, Any]:
    return {"visa_type": None, "documents": [], "name": None}


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


class Gateway:
    def __init__(self, agent: Any | None = None, supervisor: Any | None = None):
        self.agent = agent or IntakeAgent()
        self.supervisor = supervisor or CaseSupervisor()
        self.cases: dict[str, dict[str, Any]] = {}

    def handle(self, message: Message) -> Message:
        result = self.agent.handle(message)
        case = self.cases.setdefault(message.client_id, _new_case())

        for doc in result.documents:
            if doc.type == "passport" and doc.fields.get("full_name"):
                case["name"] = doc.fields["full_name"]
            case["documents"].append(doc)

        if not case["visa_type"]:
            case["visa_type"] = _infer_route(message.body)

        if result.escalation:
            reply = result.reply
        elif case["visa_type"] is None:
            reply = self._ask_route(result)
        elif not case["documents"]:
            reply = self._requirements_intro(case["visa_type"])
        else:
            client = {"id": message.client_id, "name": case["name"],
                      "application_date": datetime.now(timezone.utc).date().isoformat()}
            wr = self.supervisor.run(case["documents"], get_requirement_set(case["visa_type"]), client)
            reply = self._compose_status(wr)

        return Message(id=f"{message.id}_reply", client_id=message.client_id,
                       channel=message.channel, body=reply)

    @staticmethod
    def _ask_route(result) -> str:
        base = result.reply or "Thanks for your message."
        return (base + " Which visa route are you applying for — "
                "visitor, student, worker, or spouse/partner?")

    @staticmethod
    def _requirements_intro(visa_type: str) -> str:
        req = get_requirement_set(visa_type)
        docs = ", ".join(r.name.lower() for r in req.requirements)
        return (f"I can help with your {req.route} application. "
                f"You'll need: {docs}. Attach them here and I'll check each one.")

    @staticmethod
    def _compose_status(wr) -> str:
        gap = wr.gap_report
        if wr.final_state == "delivered":
            return "All your documents are verified — your application package is ready to submit."
        if wr.final_state == "parked":
            return "I've flagged your case for a specialist review — I'll be in touch shortly."
        failing = [i for i in gap.items if i.verdict != "OK"]
        lines = ["I've checked your documents. Still outstanding:"]
        for i in failing:
            lines.append(f"  • {i.req_name}: {i.action or i.verdict.lower()}")
        return "\n".join(lines)
