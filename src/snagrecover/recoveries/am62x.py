import usb
import logging
logger = logging.getLogger("snagrecover")
from snagrecover.firmware.firmware import run_firmware
from snagrecover.utils import parse_usb_addr, get_usb
from snagrecover.config import recovery_config
import time

def main():
	usb_addr = recovery_config["rom_usb"]
	dev = get_usb(usb_addr)
	run_firmware(dev, "tiboot3")
	# USB device should re-enumerate at this point
	usb.util.dispose_resources(dev)
	# without this delay, USB device will be present but not ready
	time.sleep(1)
	if "usb" in recovery_config["firmware"]["tiboot3"]:
		usb_addr = parse_usb_addr(recovery_config["firmware"]["tiboot3"]["usb"])

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

