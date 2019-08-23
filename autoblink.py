import asyncio
import json
import logging
import os
import requests
import sys
import time

from collections import defaultdict

from azure.iot.device.aio import IoTHubDeviceClient
from blinkpy import blinkpy

IOTHUB_DEVICE_CONNECTION_STRING = os.getenv("IOTHUB_DEVICE_CONNECTION_STRING")
BLINK_USER = os.getenv("BLINK_USER")
BLINK_PASS = os.getenv("BLINK_PASS")
BLINK_NETWORK = os.getenv("BLINK_NETWORK")
CONTROLLING_IPS = os.getenv("CONTROLLING_IPS")

class OnHubData:
    def __init__(self, logger):
        self.stations = []
        self.logger = logger

    async def refresh(self):
        # Mimic a browser. Data obtained by converting a request from the browser to
        # cURL format and then converted to requests syntax with https://curl.trillworks.com/
        headers = {
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
            'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/76.0.3809.100 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3',
            'Accept-Encoding': 'gzip, deflate',
            'Accept-Language': 'en-US,en;q=0.9,it;q=0.8',
        }

        self.logger.info("Getting data from OnHub.")
        response = requests.get('http://onhub.here/api/v1/diagnostic-report',
                                headers=headers,
                                verify=False)
        self.logger.info("Refreshed OnHub data.")

        self.stations = self._get_stations(response.content)
        return self

    def _get_stations(self, binary_response_from_onhub):
        # map DHCP hostname to list of station_info
        stations = defaultdict(list)
        capturing = False
        parens_count = 0
        tmp = {}
        for i, raw_line in enumerate(binary_response_from_onhub.split(b"\n")):
            # We are opening a binary file, some lines won't be text and
            # it's ok to ignore them, as the data we care about is in the
            # text portion of the file.
            try:
                line = raw_line.decode("utf-8")
            except:
                continue

            if capturing:
                data = line.strip()
                self.logger.debug("Line %i: -%s-" % ((i+1), data))
                if data.endswith("{"):
                    parens_count += 1
                    self.logger.debug("incremented parens_count to %d" % parens_count)
                    continue
                if data.endswith("}"):
                    parens_count = max(parens_count - 1, 0) # ignore closing station_state_update
                    self.logger.debug("decremented parens_count to %d" % parens_count)

                if parens_count == 0:
                    host = tmp["dhcp_hostname"]
                    self.logger.debug("saving data for %s" % host)
                    self.logger.debug(tmp)
                    capturing = False
                    stations[host].append(tmp)
                elif parens_count == 1 and ":" in data:
                    key, value = data.split(":")
                    value = value.strip().strip('"')
                    if value:
                        self.logger.debug("Adding %s, %s" % (key, value))
                        tmp[key] = value
                    else:
                        self.logger.debug("Empty key/value pair")
                    continue

            if "station_info" in line:
                self.logger.debug("Started capturing at line %d" % (i+1))
                capturing = True
                parens_count = 1
                tmp = {}
                tmp["dhcp_hostname"] = ""

        return stations

    def get_connected_stations(self):
        connected_stations = [name for name, data in self.stations.items()
                if all(d["connected"] == "true" for d in data)]
        return connected_stations

    def get_connected_ips(self):
        ip_addresses = []
        for stations_list in self.stations.values():
            for station in stations_list:
                if "ip_addresses" in station:
                    ip_addresses.append(station["ip_addresses"])
        return ip_addresses

async def get_blink_armed_status(blink, logger):
    logger.info("Refreshing Blink data.")
    blink.refresh()
    logger.info("Blink data refreshed.")
    return blink.sync[BLINK_NETWORK].arm

def set_blink_armed_status(blink, logger, status):
    logger.info("Changing Blink arming status to %s" % status)
    blink.sync[BLINK_NETWORK].arm = status

async def send_blink_status(device_client, armed_status, error, connected_ips, action, logger):
    await device_client.connect()
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

    logger.info("Sending message: " + serialized_msg)
    await device_client.send_d2c_message(serialized_msg)
    logger.info("Message successfully sent!")
    await device_client.disconnect()

async def get_connected_ips(onhub):
    await onhub.refresh()
    return onhub.get_connected_ips()

async def main(logger, blink, onhub):
    mainLogger.info("Connecting to IoT Hub")
    device_client = IoTHubDeviceClient.create_from_connection_string(IOTHUB_DEVICE_CONNECTION_STRING)
    mainLogger.info("Connected.")

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
            armed_status, connected_ips = await asyncio.gather(get_blink_armed_status(blink, logger), get_connected_ips(onhub))
            connected_ips = sorted(connected_ips)
            logger.info("Connected IPs: %s" % connected_ips)
            logger.info("Armed Status: %s" % armed_status)

            connected_ips_set = frozenset(connected_ips)
            logger.info("Controlling IPs: %s" % controlling_ips)
            connected_controlling_ips = sorted(ip for ip in controlling_ips if ip in connected_ips_set)
            logger.info("Connected controlling IPs: %s" % connected_controlling_ips)

            if armed_status == True:
                logger.info("Blink armed, checking if any controlling devices are connected.")
                if connected_controlling_ips:
                    action = "disarm"
                    set_blink_armed_status(blink, logger, False)
                else:
                    logger.info("No controlling devices connected, not disarming")
            elif armed_status == False:
                logger.info("Blink disarmed, checking if no controlling devices are connected.")
                if not connected_controlling_ips:
                    action = "arm"
                    set_blink_armed_status(blink, logger, True)
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

    if not CONTROLLING_IPS:
        mainLogger.error("Please set the environment variable CONTROLLING_IPS")
        sys.exit(1)

    mainLogger.info("Connecting to Blink")
    blink = blinkpy.Blink(username=BLINK_USER, password=BLINK_PASS)
    blink.start()
    mainLogger.info("Connected.")

    onhub = OnHubData(mainLogger)
    controlling_ips = sorted(CONTROLLING_IPS.split(","))
    
    asyncio.run(main(mainLogger, blink, onhub))
