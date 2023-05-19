import usb
import logging
logger = logging.getLogger("snagrecover")
from snagrecover.firmware.firmware import run_firmware
from snagrecover.utils import get_usb,parse_usb
from snagrecover.config import recovery_config
import time

def main():
	usb_vid = recovery_config["rom_usb"][0]
	usb_pid = recovery_config["rom_usb"][1]
	dev = get_usb(usb_vid, usb_pid)
	run_firmware(dev, "tiboot3")
	# USB device should re-enumerate at this point
	usb.util.dispose_resources(dev)
	# without this delay, USB device will be present but not ready
	time.sleep(1)
	if "usb" in recovery_config["firmware"]["tiboot3"]:
		(usb_vid,usb_pid) = parse_usb(recovery_config["firmware"]["tiboot3"]["usb"])
	dev = get_usb(usb_vid, usb_pid)
	run_firmware(dev, "u-boot")
	run_firmware(dev, "tispl")

