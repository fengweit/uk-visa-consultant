"""Identity resolution: phone/email -> client_id with explicit linking only."""
from uk_visa_consultant.channels.identity import IdentityResolver


def test_phone_and_email_are_separate_until_linked():
    r = IdentityResolver()
    phone_id = r.resolve_phone("+44 7700 900123")
    email_id = r.resolve_email("Client@Example.com")

    assert phone_id != email_id


def test_no_silent_merge_on_name_similarity():
    r = IdentityResolver()
    # Two different emails — no name involved — stay separate (never auto-merged).
    a = r.resolve_email("john.smith@example.com")
    b = r.resolve_email("john.smith@example.org")
    assert a != b


def test_explicit_link_merges_to_one_client_id():
    r = IdentityResolver()
    phone_id = r.resolve_phone("+447700900123")
    email_id = r.resolve_email("client@example.com")
    assert phone_id != email_id

    linked = r.link(phone="+447700900123", email="client@example.com")

    # canonical id is deterministic (smallest); both handles now resolve to it
    assert linked == phone_id
    assert r.resolve_phone("+447700900123") == linked
    assert r.resolve_email("client@example.com") == linked


def test_resolution_is_stable_and_case_insensitive():
    r = IdentityResolver()
    first = r.resolve_email("Client@Example.com")
    second = r.resolve_email("client@example.com")
    assert first == second


def test_reverse_lookup_after_link():
    r = IdentityResolver()
    r.link(phone="+447700900123", email="client@example.com")
    client = r.client("c_0001")
    assert client is not None
    assert client.contact.phone == "+447700900123"
    assert client.contact.email == "client@example.com"
    assert r.email_for_client("c_0001") == "client@example.com"
    assert r.phone_for_client("c_0001") == "+447700900123"
