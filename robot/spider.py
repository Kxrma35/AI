import argparse
import asyncio
import json
import math
import os
import sys
import time
from urllib.parse import quote

from websockets.asyncio.client import connect
from websockets.exceptions import ConnectionClosed

LEGS = 6
NEUTRAL = 90
TICK = 1 / 30
MAX_SPEED = 240
DEMO_STATES = ["idle", "listening", "thinking", "speaking", "alert", "offline"]


def idle(t, i):
    return 6 * math.sin(2 * math.pi * t / 5 + i * 0.5)


def listening(t, i):
    if i % 3 == 0:
        return 35 + 3 * math.sin(2 * math.pi * t / 1.5 + i)
    return 8


def thinking(t, i):
    return 25 * math.sin(2 * math.pi * t / 1.2 - i)


def speaking(t, i):
    return 4 + 12 * abs(math.sin(2 * math.pi * t / 0.6 + i * 0.4))


def alert(t, i):
    if t < 0.4:
        return 50
    return 30 + 20 * math.sin(2 * math.pi * t / 0.35 + i * 0.6)


def offline(t, i):
    return -40


GESTURES = {
    "idle": idle,
    "listening": listening,
    "thinking": thinking,
    "speaking": speaking,
    "alert": alert,
    "offline": offline,
}


def target_angle(state, leg, t):
    offset = GESTURES[state](t, leg)
    # Right side servos are mounted mirrored
    angle = NEUTRAL + offset if leg < LEGS // 2 else NEUTRAL - offset
    return max(0, min(180, angle))


class SimServos:
    def __init__(self):
        self.angles = [NEUTRAL] * LEGS
        self._last_print = 0

    def set(self, leg, angle):
        self.angles[leg] = angle

    def refresh(self):
        now = time.monotonic()
        if now - self._last_print >= 0.5:
            self._last_print = now
            print("legs " + " ".join(f"{a:5.1f}" for a in self.angles))


class HardwareServos:
    def __init__(self):
        from adafruit_servokit import ServoKit

        self.kit = ServoKit(channels=16)
        self.angles = [NEUTRAL] * LEGS
        for leg in range(LEGS):
            self.kit.servo[leg].set_pulse_width_range(500, 2500)
            self.kit.servo[leg].angle = NEUTRAL

    def set(self, leg, angle):
        self.angles[leg] = angle
        self.kit.servo[leg].angle = angle

    def refresh(self):
        pass

    def release(self):
        for leg in range(LEGS):
            self.kit.servo[leg].angle = None


async def animate(servos, state):
    start = time.monotonic()
    step = MAX_SPEED * TICK
    while True:
        t = time.monotonic() - start
        for leg in range(LEGS):
            current = servos.angles[leg]
            delta = target_angle(state, leg, t) - current
            servos.set(leg, current + max(-step, min(step, delta)))
        servos.refresh()
        await asyncio.sleep(TICK)


class Spider:
    def __init__(self, servos):
        self.servos = servos
        self.state = None
        self.task = None

    def set_state(self, state):
        if state not in GESTURES or state == self.state:
            return
        self.state = state
        print(f"state: {state}")
        if self.task:
            self.task.cancel()
        self.task = asyncio.create_task(animate(self.servos, state))


async def follow_joestar(spider, url):
    delay = 1
    while True:
        try:
            async with connect(url) as ws:
                print("connected to JOESTAR")
                delay = 1
                async for raw in ws:
                    spider.set_state(json.loads(raw).get("state"))
        except (OSError, ConnectionClosed) as exc:
            print(f"link lost: {exc}")
        spider.set_state("offline")
        await asyncio.sleep(delay)
        delay = min(delay * 2, 15)


async def run_demo(spider, seconds):
    while True:
        for state in DEMO_STATES:
            spider.set_state(state)
            await asyncio.sleep(seconds)


async def main(args):
    servos = SimServos() if args.sim else HardwareServos()
    spider = Spider(servos)
    spider.set_state("offline")
    try:
        if args.demo:
            await run_demo(spider, args.demo_seconds)
        else:
            token = os.getenv("ROBOT_TOKEN")
            if not token:
                sys.exit("ROBOT_TOKEN is not set")
            url = f"ws://{args.host}/robot/ws?token={quote(token)}"
            await follow_joestar(spider, url)
    finally:
        if spider.task:
            spider.task.cancel()
        if not args.sim:
            servos.release()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="JOESTAR desk spider")
    parser.add_argument("--host", default=os.getenv("JOESTAR_HOST", "127.0.0.1:8000"))
    parser.add_argument("--sim", action="store_true", help="print servo angles instead of driving hardware")
    parser.add_argument("--demo", action="store_true", help="cycle through every state without a JOESTAR link")
    parser.add_argument("--demo-seconds", type=float, default=4)
    try:
        asyncio.run(main(parser.parse_args()))
    except KeyboardInterrupt:
        pass
