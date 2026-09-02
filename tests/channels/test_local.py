"""LocalAdapter tests: round-trip receive -> send + idempotent dedup."""
from uk_visa_consultant.channels.local import LocalAdapter
from uk_visa_consultant.models import Channel, Message


def test_round_trip_receive_send():
    adapter = LocalAdapter()
    adapter.enqueue("here is my passport", client_id="c_0021")

    inbound = adapter.receive()
    assert len(inbound) == 1
    message = inbound[0]
    assert message.channel is Channel.LOCAL
    assert message.client_id == "c_0021"
    assert message.body == "here is my passport"

    # outbound goes back through the same adapter; harness observes the queue
    reply = Message(id="m_reply", client_id="c_0021", channel=Channel.LOCAL, body="thanks")
    receipt = adapter.send(reply)
    assert receipt.ok
    assert receipt.external_id == "m_reply"
    assert adapter.outbox == [reply]


def test_send_media_records_path():
    adapter = LocalAdapter()
    receipt = adapter.send_media("/data/uploads/c_0021/passport.jpg", "image/jpeg")
    assert receipt.ok
    assert adapter.sent_media == [("/data/uploads/c_0021/passport.jpg", "image/jpeg")]


def test_receive_dedups_by_id():
    adapter = LocalAdapter()
    adapter.enqueue("hi", client_id="c_1", message_id="dup_1")
    adapter.enqueue("hi again", client_id="c_1", message_id="dup_1")  # duplicate id

    inbound = adapter.receive()
    assert len(inbound) == 1
    assert inbound[0].id == "dup_1"

    # queue is drained; a second receive sees nothing
    assert adapter.receive() == []
