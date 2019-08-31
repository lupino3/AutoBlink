import asyncio
import json
import logging
import os
import sys
import time

from autoblink.onhub import OnHubData
from autoblink.blink import BlinkWrapper

from azure.iot.device.aio import IoTHubDeviceClient

IOTHUB_DEVICE_CONNECTION_STRING = os.getenv("IOTHUB_DEVICE_CONNECTION_STRING")
BLINK_USER = os.getenv("BLINK_USER")
BLINK_PASS = os.getenv("BLINK_PASS")
BLINK_NETWORK = os.getenv("BLINK_NETWORK")
CONTROLLING_IPS = os.getenv("CONTROLLING_IPS")

async def send_blink_status(device_client, armed_status, error, connected_ips, action, logger):
    msg = {
            "active": 1,
            "device": "RaspberryPiAutoBlink",
            "timestamp": time.time(),
            "armed": armed_status,
            "connected_ips": connected_ips,
            "error": error,
            "action": action,
    }
    serialized_msg = json.dumps(msg)

    logger.info("Sending message: %s", serialized_msg)
    await device_client.send_d2c_message(serialized_msg)

async def get_connected_ips(onhub):
    await onhub.refresh()
    return onhub.get_connected_ips()

async def main(logger, blink, onhub, controlling_ips):
    mainLogger.info("Connecting to IoT Hub")
    device_client = IoTHubDeviceClient.create_from_connection_string(IOTHUB_DEVICE_CONNECTION_STRING)
    await device_client.connect()

    # Task to receive cloud-to-device commands.
    c2d_task = asyncio.create_task(device_client.receive_c2d_message())

    while True:
        logger.info("------ Starting new cycle")
        error = None
        armed_status = None
        action = ""

        # TODO: error handling -- what if Blink is not available or returns a bad value?
        # Need a timeout (wait_for) in addition to dealing with invalid errors.
        try:
            armed_status, connected_ips = await asyncio.gather(blink.armed_status(), get_connected_ips(onhub))
            connected_ips = sorted(connected_ips)
            logger.info("Connected IPs: %s", connected_ips)
            logger.info("Armed Status: %s", armed_status)

            connected_ips_set = frozenset(connected_ips)
            logger.info("Controlling IPs: %s", controlling_ips)
            connected_controlling_ips = sorted(ip for ip in controlling_ips if ip in connected_ips_set)
            logger.info("Connected controlling IPs: %s", connected_controlling_ips)

            if armed_status == True:
                if connected_controlling_ips:
                    action = "disarm"
                    blink.set_armed_status(False)
                else:
                    logger.info("No controlling devices connected, not disarming")
            elif armed_status == False:
                if not connected_controlling_ips:
                    action = "arm"
                    blink.set_armed_status(True)
                else:
                    logger.info("Some controlling devices connected, not arming")
        except Exception as e:
            logger.exception(e)
            error = e

        # TODO: Add timeouts to all await statements.
        try:
            await asyncio.wait_for(send_blink_status(device_client, armed_status, error, connected_ips, action, logger), timeout=30.0)
        except asyncio.TimeoutError:
            logger.warning("Could not send message to IoT Hub")

        logger.info("Waiting 30 seconds (or a kill c2d message).")
        done, pending = await asyncio.wait({c2d_task}, timeout=30)

        if c2d_task in done:
            logger.info("Exiting due to c2d message: %s", c2d_task.result().data.decode("utf-8"))
            # TODO: proper clean-up.
            sys.exit(0)


if __name__ == "__main__":
    logging.basicConfig(format='%(asctime)s %(message)s', datefmt='%Y/%m/%d %I:%M:%S %p')
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

    if not CONTROLLING_IPS:
        mainLogger.error("Please set the environment variable CONTROLLING_IPS")
        sys.exit(1)

    blink = BlinkWrapper(BLINK_USER, BLINK_PASS, BLINK_NETWORK, mainLogger)

    onhub = OnHubData(mainLogger)
    controlling_ips = sorted(CONTROLLING_IPS.split(","))
    
    asyncio.run(main(mainLogger, blink, onhub, controlling_ips))
