import asyncio
import json
import logging
import os
import sys
import time

from azure.iot.device.aio import IoTHubDeviceClient
from blinkpy import blinkpy

IOTHUB_DEVICE_CONNECTION_STRING = os.getenv("IOTHUB_DEVICE_CONNECTION_STRING")
BLINK_USER = os.getenv("BLINK_USER")
BLINK_PASS = os.getenv("BLINK_PASS")
BLINK_NETWORK = os.getenv("BLINK_NETWORK")

def get_blink_armed_status(blink):
    blink.refresh()
    return blink.sync[BLINK_NETWORK].arm

async def send_blink_status(device_client, armed_status, error, error_message, logger):
    msg = {
            "active": 1,
            "device": "RaspberryPiAutoBlink",
            "timestamp": time.time(),
            "armed": armed_status,
            "error": error,
            "error_message": error_message,
    }
    serialized_msg = json.dumps(msg)

    logger.info("Sending message: " + serialized_msg)
    await device_client.send_d2c_message(serialized_msg)
    logger.info("Message successfully sent!")
    await device_client.disconnect()


async def main(logger):
    logger.info("Connecting to IoT Hub")
    device_client = IoTHubDeviceClient.create_from_connection_string(IOTHUB_DEVICE_CONNECTION_STRING)
    logger.info("Connected.")

    # Task to receive cloud-to-device commands.
    c2d_task = asyncio.create_task(device_client.receive_c2d_message())

    logger.info("Connecting to Blink")
    blink = blinkpy.Blink(username=BLINK_USER, password=BLINK_PASS)
    blink.start()
    logger.info("Connected.")

    while True:
        error = False
        error_message = ""
        armed_status = None

        # TODO: error handling -- what if Blink is not available or returns a bad value?
        # Need a timeout (wait_for) in addition to dealing with invalid errors.
        try:
            armed_status = get_blink_armed_status(blink)
        except e:
            logger.exception(e)
            error = True
            error_message = e.message

        await send_blink_status(device_client, armed_status, error, error_message, logger)

        done, pending = await asyncio.wait({c2d_task}, timeout=30)

        if c2d_task in done:
            logger.info("Exiting due to c2d message: " + c2d_task.result().data.decode("utf-8"))
            sys.exit(0)


if __name__ == "__main__":
    logging.basicConfig(format='%(asctime)s %(message)s', datefmt='%m/%d/%Y %I:%M:%S %p')
    mainLogger = logging.getLogger("main")
    mainLogger.setLevel(logging.INFO)

    if not IOTHUB_DEVICE_CONNECTION_STRING:
        mainLogger.error("Please set the environment variable IOTHUB_DEVICE_CONNECTION_STRING")
        sys.exit(1)

    if not BLINK_USER:
        mainLogger.error("Please set the environment variable BLINK_USER")
        sys.exit(1)

    if not BLINK_PASS:
        mainLogger.error("Please set the environment variable BLINK_PASS")
        sys.exit(1)

    if not BLINK_NETWORK:
        mainLogger.error("Please set the environment variable BLINK_NETWORK")
        sys.exit(1)
    
    asyncio.run(main(mainLogger))
