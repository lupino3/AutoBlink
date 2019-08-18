import asyncio
import json
import os
import sys
import time

from azure.iot.device.aio import IoTHubDeviceClient
from blinkpy import blinkpy

IOTHUB_DEVICE_CONNECTION_STRING = os.getenv("IOTHUB_DEVICE_CONNECTION_STRING")
BLINK_USER = os.getenv("BLINK_USER")
BLINK_PASS = os.getenv("BLINK_PASS")
BLINK_NETWORK = os.getenv("BLINK_NETWORK")

async def get_blink_armed_status():
    print("Connecting to Blink")
    blink = blinkpy.Blink(username=BLINK_USER, password=BLINK_PASS)
    blink.start()
    print("Connected to Blink, information fetched.")
    return blink.sync[BLINK_NETWORK].arm

async def main():
    while True:
        # TODO: error handling -- what if Blink is not available or returns a bad value?
        # Need a timeout (wait_for) in addition to dealing with invalid errors.
        blink_task = asyncio.create_task(get_blink_armed_status())
        device_client = IoTHubDeviceClient.create_from_connection_string(IOTHUB_DEVICE_CONNECTION_STRING)
        msg = {
                "active": 1,
                "device": "RaspberryPiAutoBlink",
                "timestamp": time.time(),
                "armed": await blink_task
        }
        serialized_msg = json.dumps(msg)

        print("Sending message: " + serialized_msg)
        await device_client.send_d2c_message(serialized_msg)
        print("Message successfully sent!")

        await asyncio.gather(
                device_client.disconnect(),
                asyncio.sleep(30))


if __name__ == "__main__":
    if not IOTHUB_DEVICE_CONNECTION_STRING:
        print("Please set the environment variable IOTHUB_DEVICE_CONNECTION_STRING")
        sys.exit(1)

    if not BLINK_USER:
        print("Please set the environment variable BLINK_USER")
        sys.exit(1)

    if not BLINK_PASS:
        print("Please set the environment variable BLINK_PASS")
        sys.exit(1)

    if not BLINK_NETWORK:
        print("Please set the environment variable BLINK_NETWORK")
        sys.exit(1)

    asyncio.run(main())
