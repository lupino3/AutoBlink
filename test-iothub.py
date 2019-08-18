import asyncio
import os
import time
from azure.iot.device.aio import IoTHubDeviceClient


async def main():
    # Fetch the connection string from an enviornment variable
    conn_str = os.getenv("IOTHUB_DEVICE_CONNECTION_STRING")

    # Create instance of the device client using the connection string
    device_client = IoTHubDeviceClient.create_from_connection_string(conn_str)

    # Send a single message
    msg = "{'active': 1, 'device': 'RaspberryPiAutoBlink', timestamp: '%s'}" % time.time()
    print("Sending message: " + msg)
    await device_client.send_d2c_message(msg)
    print("Message successfully sent!")

    # finally, disconnect
    await device_client.disconnect()


if __name__ == "__main__":
    asyncio.run(main())
