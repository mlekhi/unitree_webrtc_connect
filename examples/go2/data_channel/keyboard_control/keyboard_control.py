"""
Control the Go2 with WASD keys. No Enter needed — each keypress moves or stops.
Edit ROBOT_IP below and run from repo root. Requires Unix/macOS for key input.
"""
import asyncio
import json
import logging
import os
import sys

from unitree_webrtc_connect.webrtc_driver import UnitreeWebRTCConnection, WebRTCConnectionMethod
from unitree_webrtc_connect.constants import RTC_TOPIC, SPORT_CMD

logging.basicConfig(level=logging.FATAL)

# Plug in your Go2's IP address
ROBOT_IP = ""

# Move speed (forward/back = x, left/right = y; tune to your liking)
SPEED_X = 0.4
SPEED_Y = 0.35
# Turn test: Move(0,0,z) = yaw rate (rad/s). Higher = faster spin. X to stop early.
TURN_Z = 1.2
TURN_DURATION = 6.0

# Single-key reading on Unix/macOS
try:
    import termios
    import tty
    _HAVE_TERMIOS = True
except ImportError:
    _HAVE_TERMIOS = False

_stdin_fd = None
_old_termios = None


def stdin_setup():
    """Put stdin in cbreak so we get one key per read. Call once at start."""
    global _stdin_fd, _old_termios
    if not _HAVE_TERMIOS or not sys.stdin.isatty():
        return False
    _stdin_fd = sys.stdin.fileno()
    _old_termios = termios.tcgetattr(_stdin_fd)
    tty.setcbreak(_stdin_fd)
    return True


def stdin_restore():
    """Restore terminal. Call on exit."""
    global _old_termios
    if _HAVE_TERMIOS and _stdin_fd is not None and _old_termios is not None:
        termios.tcsetattr(_stdin_fd, termios.TCSADRAIN, _old_termios)


def read_key():
    """Read one keypress; return bytes or None."""
    if not _HAVE_TERMIOS or _stdin_fd is None:
        return None
    try:
        return os.read(_stdin_fd, 1)
    except (BlockingIOError, OSError):
        return None


async def move(conn, x, y, z=0):
    await conn.datachannel.pub_sub.publish_request_new(
        RTC_TOPIC["SPORT_MOD"],
        {"api_id": SPORT_CMD["Move"], "parameter": {"x": x, "y": y, "z": z}},
    )


async def stop(conn):
    await conn.datachannel.pub_sub.publish_request_new(
        RTC_TOPIC["SPORT_MOD"],
        {"api_id": SPORT_CMD["StopMove"]},
    )


async def hop(conn):
    """Jump forward (FrontJump). API also has FrontPounce 1032 / Bound 1304 if you want to try in-place."""
    await conn.datachannel.pub_sub.publish_request_new(
        RTC_TOPIC["SPORT_MOD"],
        {"api_id": SPORT_CMD["FrontJump"], "parameter": {"data": True}},
    )


async def moonwalk(conn):
    """MoonWalk (sport API)."""
    await conn.datachannel.pub_sub.publish_request_new(
        RTC_TOPIC["SPORT_MOD"],
        {"api_id": SPORT_CMD["MoonWalk"], "parameter": {"data": True}},
    )


async def dance1(conn):
    """Dance1 (sport API)."""
    await conn.datachannel.pub_sub.publish_request_new(
        RTC_TOPIC["SPORT_MOD"],
        {"api_id": SPORT_CMD["Dance1"], "parameter": {"data": True}},
    )


async def dance2(conn):
    """Dance2 (sport API)."""
    await conn.datachannel.pub_sub.publish_request_new(
        RTC_TOPIC["SPORT_MOD"],
        {"api_id": SPORT_CMD["Dance2"], "parameter": {"data": True}},
    )


async def turn_test(conn):
    """Turn: Move(0, 0, TURN_Z) for TURN_DURATION. On this API it may only shift; press X to stop."""
    await move(conn, 0, 0, TURN_Z)
    await asyncio.sleep(TURN_DURATION)
    await stop(conn)


async def main():
    if not _HAVE_TERMIOS:
        print("Keyboard control requires Unix/macOS (termios). Run on Mac/Linux.")
        return

    conn = None
    try:
        print(f"Connecting to Go2 at {ROBOT_IP}...")
        conn = UnitreeWebRTCConnection(WebRTCConnectionMethod.LocalSTA, ip=ROBOT_IP)
        await conn.connect()

        print("Setting motion mode to normal...")
        response = await conn.datachannel.pub_sub.publish_request_new(
            RTC_TOPIC["MOTION_SWITCHER"],
            {"api_id": 1001},
        )
        if response.get("data", {}).get("header", {}).get("status", {}).get("code") == 0:
            data = json.loads(response["data"]["data"])
            if data.get("name") != "normal":
                await conn.datachannel.pub_sub.publish_request_new(
                    RTC_TOPIC["MOTION_SWITCHER"],
                    {"api_id": 1002, "parameter": {"name": "normal"}},
                )
                await asyncio.sleep(5)

        print("WASD: move  |  Space: hop  |  P: moonwalk  |  1/2: dance1/dance2  |  T: turn test  |  X: stop  |  Q: quit")
        print("(No Enter — just press keys)")

        if not stdin_setup():
            print("Could not set up terminal for key input.")
            return

        loop = asyncio.get_running_loop()
        quit_event = asyncio.Event()

        def on_key():
            key = read_key()
            if key is None:
                return
            k = key.decode("utf-8", errors="ignore").lower() if key else ""
            # Space can come through as b' ' or as " " after decode
            is_space = k == " " or key == b" "
            if k == "q":
                quit_event.set()
                return
            if is_space:
                print("Hop!", flush=True)
                asyncio.create_task(hop(conn))
                return
            if k == "x":
                asyncio.create_task(stop(conn))
                return
            if k == "p":
                asyncio.create_task(moonwalk(conn))
                return
            if k == "1":
                asyncio.create_task(dance1(conn))
                return
            if k == "2":
                asyncio.create_task(dance2(conn))
                return
            if k == "t":
                asyncio.create_task(turn_test(conn))
                return
            if k == "w":
                asyncio.create_task(move(conn, SPEED_X, 0))
            elif k == "s":
                asyncio.create_task(move(conn, -SPEED_X, 0))
            elif k == "a":
                asyncio.create_task(move(conn, 0, SPEED_Y))
            elif k == "d":
                asyncio.create_task(move(conn, 0, -SPEED_Y))

        loop.add_reader(sys.stdin.fileno(), on_key)
        try:
            await quit_event.wait()
        finally:
            loop.remove_reader(sys.stdin.fileno())

    except ValueError as e:
        logging.error(f"Error: {e}")
    finally:
        stdin_restore()
        if conn is not None:
            try:
                await stop(conn)
            except Exception:
                pass
        print("Bye.")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nBye.")
        sys.exit(0)
