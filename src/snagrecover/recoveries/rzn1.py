import logging

logger = logging.getLogger("snagrecover")
from snagrecover.firmware.firmware import run_firmware
from snagrecover.utils import get_usb
from snagrecover.config import recovery_config


def main():
	usb_addr = recovery_config["usb_path"]
	dev = get_usb(usb_addr)

	run_firmware(dev, "u-boot")
