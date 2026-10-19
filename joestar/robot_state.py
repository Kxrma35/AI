import asyncio

IDLE = "idle"


class StateHub:
    # Tracks JOESTAR's current state and fans changes out to connected robots
    def __init__(self):
        self.state = IDLE
        self._queues = set()
        self._revert = None

    def set(self, state, hold=None):
        if self._revert:
            self._revert.cancel()
            self._revert = None
        self._publish(state)
        if hold and state != IDLE:
            loop = asyncio.get_running_loop()
            self._revert = loop.call_later(hold, self._publish, IDLE)

    def _publish(self, state):
        self.state = state
        for queue in self._queues:
            try:
                queue.put_nowait(state)
            except asyncio.QueueFull:
                pass

    def subscribe(self):
        queue = asyncio.Queue(maxsize=16)
        self._queues.add(queue)
        return queue

    def unsubscribe(self, queue):
        self._queues.discard(queue)


def speech_seconds(text):
    # Rough spoken length so the robot returns to idle when the voice ends
    return max(2.0, len(text) / 14)


hub = StateHub()
