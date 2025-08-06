import logging

logger = logging.getLogger("snagrecover")
from time import sleep
from snagrecover.firmware.firmware import run_firmware
from snagrecover.utils import get_usb
from snagrecover.config import recovery_config


def main():
	# USB ENUMERATION
	usb_path = recovery_config["usb_path"]
	dev = get_usb(usb_path)

	# Download bootcode
	run_firmware(dev, "bootfiles", "bootcode")

	logger.info("Waiting for bootcode to start...")
	sleep(2)
	dev = get_usb(usb_path)

	# Serve firmwares to bootcode (will also serve firmwares "boot" and "u-boot")
	run_firmware(dev, "bootfiles", "bootcode_firmwares")
