import usb
import logging

logger = logging.getLogger("snagrecover")
from snagrecover.firmware.firmware import run_firmware
from snagrecover.utils import get_usb
from snagrecover.config import recovery_config
import time


def send_firmware(dev, firmware):
	run_firmware(dev, firmware)
	# USB device should re-enumerate at this point
	usb.util.dispose_resources(dev)
	# without this delay, USB device will be present but not ready
	time.sleep(1)


def main():
	usb_addr = recovery_config["usb_path"]
	dev = get_usb(usb_addr)

	send_firmware(dev, "tiboot3")
	dev = get_usb(usb_addr)

	send_firmware(dev, "tispl")
	dev = get_usb(usb_addr)
	time.sleep(1)
	run_firmware(dev, "u-boot")

	time.sleep(2)
