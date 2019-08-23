from blinkpy import blinkpy

class BlinkWrapper:
    def __init__(self, username, password, network, logger):
        self._logger = logger
        self._network = network
        self._logger.info("Connecting to Blink")
        self._blink = blinkpy.Blink(username, password)
        self._blink.start()

    def set_armed_status(self, status):
        self._logger.info("Changing Blink arming status to %s", status)
        self._blink.sync[self._network].arm = status

    async def armed_status(self):
        self._logger.info("Refreshing Blink data.")
        self._blink.refresh()
        return self._blink.sync[self._network].arm

