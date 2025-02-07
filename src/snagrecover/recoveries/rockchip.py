import usb
import logging
logger = logging.getLogger("snagrecover")
from snagrecover.firmware.firmware import run_firmware
from snagrecover.utils import get_usb
from snagrecover.utils import cli_error
from snagrecover.config import recovery_config
import time


def main():
	usb_addr = recovery_config["usb_path"]
	dev = get_usb(usb_addr)

	# Blob made with boot_merger
	if "xpl" in recovery_config["firmware"]:
		try:
			run_firmware(dev, "xpl")
			usb.util.dispose_resources(dev)
		except Exception as e:
			cli_error(f"Failed to run firmware: {e}")

	# u-boot binaries.
	elif "code471" in recovery_config["firmware"] and "code472" in recovery_config["firmware"]:
		try:
			run_firmware(dev, "code471")
			usb.util.dispose_resources(dev)
		except Exception as e:
			cli_error(f"Failed to run code471 firmware: {e}")
		if "delay" in recovery_config["firmware"]["code471"]:
			delay = recovery_config["firmware"]["code471"]["delay"]
			logger.info(f"Sleeping {delay}ms")
			time.sleep(delay / 1000)
		try:
			run_firmware(dev, "code472")
			usb.util.dispose_resources(dev)
		except Exception as e:
			cli_error(f"Failed to run code472 firmware: {e}")
		if "delay" in recovery_config["firmware"]["code472"]:
			delay = recovery_config["firmware"]["code472"]["delay"]
			logger.info(f"Sleeping {delay}ms")
			time.sleep(delay / 1000)
	else:
		cli_error(("Missing xpl or "
                    "code471 (*_ddr_*.bin' or 'mkimage-in-simple-bin.mkimage-u-boot-tpl') / "
                    "code472 ('*_usbplug_*.bin' or 'mkimage-in-simple-bin.mkimage-u-boot-spl')"
                    "binary configuration."))

	if "u-boot-fit" in recovery_config["firmware"]:
		try:
			dev = get_usb(usb_addr)
			run_firmware(dev, "u-boot-fit")
		except Exception as e:
			cli_error(f"Failed to load u-boot.itb: {e}")
