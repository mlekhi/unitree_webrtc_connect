"""
Go2 does the Cha Cha Slide: a sequence of moves (slide left, slide right, criss cross, etc.).
Edit ROBOT_IP below and run from repo root.
"""
import asyncio
import json
import logging
import sys

from unitree_webrtc_connect.webrtc_driver import UnitreeWebRTCConnection, WebRTCConnectionMethod
from unitree_webrtc_connect.constants import RTC_TOPIC, SPORT_CMD

logging.basicConfig(level=logging.FATAL)

# Plug in your Go2's IP address
ROBOT_IP = ""

# Move speed and step duration (tune to match the song if you play it)
STEP_Y = 0.35   # lateral slide
STEP_X = 0.25   # forward/back
STOMP_Y = 0.2   # small step for stomps
BEAT = 0.8      # seconds per move (slower)
PAUSE = 1.0     # seconds to pause between each major step
# Turn 360: yaw rate (rad/s) and how long to hold it to complete one full spin
TURN_Z = 0.5    # yaw rate for "turn it out"
TURN_360_DURATION = 14.0   # ~2*pi/0.5 sec to turn 360°


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


async def run_cha_cha_slide(conn):
    """Sequence: to the left, take it back, one hop, right foot stomp, left foot stomp, cha cha, turn it out."""
    # To the left
    print("To the left!")
    await move(conn, 0, STEP_Y)
    await asyncio.sleep(BEAT * 2)
    await stop(conn)
    await asyncio.sleep(PAUSE)

    # Take it back
    print("Take it back!")
    await move(conn, -STEP_X, 0)
    await asyncio.sleep(BEAT * 2)
    await stop(conn)
    await asyncio.sleep(PAUSE)

    # One hop (Bound = in-place bounce; no forward motion)
    print("One hop!")
    await conn.datachannel.pub_sub.publish_request_new(
        RTC_TOPIC["SPORT_MOD"],
        {"api_id": SPORT_CMD["Bound"], "parameter": {"data": True}},
    )
    await asyncio.sleep(1.5)  # time to land
    await asyncio.sleep(PAUSE)

    # Right foot stomp
    print("Right foot stomp!")
    await move(conn, 0, -STOMP_Y)
    await asyncio.sleep(BEAT)
    await stop(conn)
    await asyncio.sleep(PAUSE)

    # Left foot stomp
    print("Left foot stomp!")
    await move(conn, 0, STOMP_Y)
    await asyncio.sleep(BEAT)
    await stop(conn)
    await asyncio.sleep(PAUSE)

    # Cha cha (WiggleHips)
    print("Cha cha!")
    await conn.datachannel.pub_sub.publish_request_new(
        RTC_TOPIC["SPORT_MOD"],
        {"api_id": SPORT_CMD["WiggleHips"], "parameter": {"data": True}},
    )
    await asyncio.sleep(2.0)
    await asyncio.sleep(PAUSE)

    # Turn it out (360° – hold yaw rate long enough for one full spin)
    print("Turn it out!")
    await move(conn, 0, 0, TURN_Z)
    await asyncio.sleep(TURN_360_DURATION)
    await stop(conn)
    await asyncio.sleep(PAUSE)


async def main():
    conn = None
    try:
        print(f"Connecting to Go2 at {ROBOT_IP}...")
        conn = UnitreeWebRTCConnection(WebRTCConnectionMethod.LocalSTA, ip=ROBOT_IP)
        await conn.connect()

        # Normal mode (required for Move)
        print("Setting motion mode to normal...")
        response = await conn.datachannel.pub_sub.publish_request_new(
            RTC_TOPIC["MOTION_SWITCHER"],
            {"api_id": 1001},
        )
        if response.get("data", {}).get("header", {}).get("status", {}).get("code") == 0:
            data = json.loads(response["data"]["data"])
            current = data.get("name", "?")
            if current != "normal":
                await conn.datachannel.pub_sub.publish_request_new(
                    RTC_TOPIC["MOTION_SWITCHER"],
                    {"api_id": 1002, "parameter": {"name": "normal"}},
                )
                await asyncio.sleep(5)

        print("Cha Cha Slide starting in 2 seconds...")
        await asyncio.sleep(2)

        # Run the sequence 4 times (about 1 minute)
        for i in range(4):
            print(f"--- Round {i + 1}/4 ---")
            await run_cha_cha_slide(conn)

        await stop(conn)
        print("Done! Cha Cha Slide complete.")

    except ValueError as e:
        logging.error(f"Error: {e}")
    finally:
        if conn is not None:
            try:
                await conn.datachannel.pub_sub.publish_request_new(
                    RTC_TOPIC["SPORT_MOD"],
                    {"api_id": SPORT_CMD["StopMove"]},
                )
            except Exception:
                pass


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nProgram interrupted by user")
        sys.exit(0)
