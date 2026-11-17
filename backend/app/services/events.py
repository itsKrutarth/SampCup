"""Server-Sent Events: tell open pages that something changed, so they refetch."""

import asyncio
import contextlib
import json
import threading
from collections.abc import AsyncIterator
from typing import Any

Message = dict[str, Any]


class Broadcaster:
    def __init__(self, queue_size: int = 100) -> None:
        self.queue_size = queue_size
        self._subscribers: set[tuple[asyncio.AbstractEventLoop, asyncio.Queue[Message]]] = set()
        self._lock = threading.Lock()

    def subscribe(self) -> asyncio.Queue[Message]:
        queue: asyncio.Queue[Message] = asyncio.Queue(self.queue_size)
        with self._lock:
            self._subscribers.add((asyncio.get_running_loop(), queue))
        return queue

    def unsubscribe(self, queue: asyncio.Queue[Message]) -> None:
        with self._lock:
            self._subscribers = {s for s in self._subscribers if s[1] is not queue}

    @property
    def count(self) -> int:
        return len(self._subscribers)

    def publish(self, event: str, **data: Any) -> None:
        """Safe to call from any thread (FastAPI runs sync routes in a thread pool)."""
        message = {"event": event, "data": data}
        with self._lock:
            subscribers = list(self._subscribers)
        for loop, queue in subscribers:
            loop.call_soon_threadsafe(_offer, queue, message)


def _offer(queue: asyncio.Queue[Message], message: Message) -> None:
    # A stalled client misses this hint; it refetches everything when it reconnects.
    with contextlib.suppress(asyncio.QueueFull):
        queue.put_nowait(message)


async def event_stream(
    queue: asyncio.Queue[Message], heartbeat: float = 15.0
) -> AsyncIterator[str]:
    yield "retry: 3000\nevent: hello\ndata: {}\n\n"
    while True:
        try:
            message = await asyncio.wait_for(queue.get(), heartbeat)
        except TimeoutError:
            yield ": heartbeat\n\n"
            continue
        yield f"event: {message['event']}\ndata: {json.dumps(message['data'])}\n\n"


broadcaster = Broadcaster()
