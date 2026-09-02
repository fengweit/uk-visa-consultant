"""Channel layer: WhatsApp / Email / Local adapters over a canonical Message."""
from uk_visa_consultant.channels.base import ChannelAdapter, ChannelError
from uk_visa_consultant.channels.email import EmailAdapter, parse_email
from uk_visa_consultant.channels.identity import IdentityResolver
from uk_visa_consultant.channels.local import LocalAdapter
from uk_visa_consultant.channels.whatsapp import (
    SignatureVerificationError,
    TemplateWindowError,
    WhatsAppAdapter,
    verify_signature,
)

__all__ = [
    "ChannelAdapter",
    "ChannelError",
    "EmailAdapter",
    "IdentityResolver",
    "LocalAdapter",
    "SignatureVerificationError",
    "TemplateWindowError",
    "WhatsAppAdapter",
    "parse_email",
    "verify_signature",
]
