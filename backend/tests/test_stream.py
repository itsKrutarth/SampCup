import asyncio

from fastapi.testclient import TestClient

from app.api import public
from app.services.events import Broadcaster, event_stream


def test_broadcaster_delivers_to_every_subscriber() -> None:
    async def scenario() -> list:
        hub = Broadcaster(queue_size=1)
        first, second = hub.subscribe(), hub.subscribe()
        assert hub.count == 2
        hub.publish("update", scope="scores")
        hub.publish("update", scope="dropped")  # queue full: dropped, not an error
        await asyncio.sleep(0)
        got = [await first.get(), await second.get()]
        hub.unsubscribe(first)
        assert hub.count == 1
        return got

    assert asyncio.run(scenario()) == [{"event": "update", "data": {"scope": "scores"}}] * 2


def test_event_stream_says_hello_then_relays_and_heartbeats() -> None:
    async def scenario() -> list[str]:
        queue: asyncio.Queue = asyncio.Queue()
        stream = event_stream(queue, heartbeat=0.01)
        chunks = [await anext(stream)]
        chunks.append(await anext(stream))  # nothing queued: heartbeat
        await queue.put({"event": "update", "data": {"scope": "teams"}})
        chunks.append(await anext(stream))
        await stream.aclose()
        return chunks

    hello, beat, message = asyncio.run(scenario())
    assert hello.startswith("retry: 3000\nevent: hello")
    assert beat == ": heartbeat\n\n"
    assert message == 'event: update\ndata: {"scope": "teams"}\n\n'


def test_stream_endpoint_unsubscribes_when_the_client_leaves(
    client: TestClient, monkeypatch
) -> None:
    async def short_stream(queue, heartbeat=15.0):
        yield "event: hello\ndata: {}\n\n"

    monkeypatch.setattr(public.events, "event_stream", short_stream)
    response = client.get("/api/public/stream")
    assert response.headers["content-type"].startswith("text/event-stream")
    assert response.text == "event: hello\ndata: {}\n\n"
    assert public.events.broadcaster.count == 0
