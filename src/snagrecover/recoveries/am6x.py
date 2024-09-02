import usb
import logging
logger = logging.getLogger("snagrecover")
from snagrecover.firmware.firmware import run_firmware
from snagrecover.utils import get_usb
from snagrecover.config import recovery_config
from snagrecover.protocols import dfu
import time

def send_tiboot3(dev):
	run_firmware(dev, "tiboot3")
	# USB device should re-enumerate at this point
	usb.util.dispose_resources(dev)
	# without this delay, USB device will be present but not ready
	time.sleep(1)


def main():
	usb_addr = recovery_config["usb_path"]
	dev = get_usb(usb_addr)

	send_tiboot3(dev)

	dev = get_usb(usb_addr)

	# Some versions of U-Boot on some devices require tiboot3 to be run twice
	if dfu.search_partid(dev, "bootloader") is not None:
		send_tiboot3(dev)
		dev = get_usb(usb_addr)

	run_firmware(dev, "tispl")
	run_firmware(dev, "u-boot")

	time.sleep(2)

	# For newer versions of U-Boot, only SPL will run from the
	# previous commands and the u-boot firmware should be sent
	# one more time.

	dev = get_usb(usb_addr, error_on_fail=False)
	if dev is not None:
		run_firmware(dev, "u-boot")

