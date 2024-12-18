import usb
import logging
logger = logging.getLogger("snagrecover")
from snagrecover.firmware.firmware import run_firmware
from snagrecover.utils import get_usb
from snagrecover.config import recovery_config
from snagrecover.protocols import dfu
import time

def altmode1_check(dev: usb.core.Device):
	try:
		return 1 in dfu.list_partids(dev)
	except usb.core.USBError:
		logger.warning("USB device is unavailable")

	return False

def main():
	usb_addr = recovery_config["usb_path"]
	dev = get_usb(usb_addr)

	if "fsbl" not in recovery_config["firmware"]:
		logger.warning("No FSBL image given, will attempt to extract it from full boot image")
		run_firmware(dev, "boot", "fsbl")
	else:
		run_firmware(dev, "fsbl")

	time.sleep(0.5)

	dev = get_usb(usb_addr, ready_check=altmode1_check)

	run_firmware(dev, "boot")

