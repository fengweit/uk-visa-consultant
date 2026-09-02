"""Client identity resolution across channels.

A client may appear on both WhatsApp (phone) and email. This resolver maps a
channel handle back to one stable ``client_id``.

Rule (docs/specs/comms-layer.md): a phone and an email are linked **only on
explicit confirmation** — never on name similarity. Unlinked handles stay as
separate ``client_id`` s until ``link()`` is called.
"""
from __future__ import annotations

from uk_visa_consultant.models import Client, Contact


def _normalize_phone(phone: str) -> str:
    """Strip whitespace/separators; keep a leading '+' if present."""
    return phone.strip()


def _normalize_email(email: str) -> str:
    return email.strip().lower()


class IdentityResolver:
    """Mints and resolves ``client_id`` from phone/email with explicit linking."""

    def __init__(self) -> None:
        self._clients: dict[str, Client] = {}
        self._phone_to_client: dict[str, str] = {}
        self._email_to_client: dict[str, str] = {}
        self._counter = 0

    # -- minting -----------------------------------------------------------
    def _mint(self) -> str:
        self._counter += 1
        return f"c_{self._counter:04d}"

    # -- resolution --------------------------------------------------------
    def resolve_phone(self, phone: str) -> str:
        phone = _normalize_phone(phone)
        existing = self._phone_to_client.get(phone)
        if existing:
            return existing
        cid = self._mint()
        self._phone_to_client[phone] = cid
        self._clients[cid] = Client(id=cid, contact=Contact(phone=phone))
        return cid

    def resolve_email(self, email: str) -> str:
        email = _normalize_email(email)
        existing = self._email_to_client.get(email)
        if existing:
            return existing
        cid = self._mint()
        self._email_to_client[email] = cid
        self._clients[cid] = Client(id=cid, contact=Contact(email=email))
        return cid

    # -- explicit linking --------------------------------------------------
    def link(self, phone: str | None = None, email: str | None = None) -> str:
        """Explicitly assert ``phone`` and ``email`` belong to one client.

        Any client ids already associated with either handle are merged into a
        single canonical id (the smallest id, for determinism). Returns the
        canonical client_id.
        """
        phone = _normalize_phone(phone) if phone else None
        email = _normalize_email(email) if email else None

        involved: set[str] = set()
        if phone and phone in self._phone_to_client:
            involved.add(self._phone_to_client[phone])
        if email and email in self._email_to_client:
            involved.add(self._email_to_client[email])

        canonical = min(involved) if involved else self._mint()

        # Rewrite every handle that pointed at an involved id to canonical.
        for p, cid in list(self._phone_to_client.items()):
            if cid in involved:
                self._phone_to_client[p] = canonical
        for e, cid in list(self._email_to_client.items()):
            if cid in involved:
                self._email_to_client[e] = canonical

        if phone:
            self._phone_to_client[phone] = canonical
        if email:
            self._email_to_client[email] = canonical

        # Merge contact records.
        contact = Contact()
        for cid in involved | {canonical}:
            client = self._clients.get(cid)
            if client:
                contact.phone = contact.phone or client.contact.phone
                contact.email = contact.email or client.contact.email
        if phone:
            contact.phone = phone
        if email:
            contact.email = email
        self._clients[canonical] = Client(id=canonical, contact=contact)

        for cid in involved:
            if cid != canonical:
                self._clients.pop(cid, None)

        return canonical

    # -- reverse lookup ----------------------------------------------------
    def client(self, client_id: str) -> Client | None:
        return self._clients.get(client_id)

    def email_for_client(self, client_id: str) -> str | None:
        client = self._clients.get(client_id)
        return client.contact.email if client else None

    def phone_for_client(self, client_id: str) -> str | None:
        client = self._clients.get(client_id)
        return client.contact.phone if client else None
