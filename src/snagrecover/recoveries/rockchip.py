import usb
import logging
logger = logging.getLogger("snagrecover")
from snagrecover.firmware.firmware import run_firmware
from snagrecover.utils import get_usb
from snagrecover.config import recovery_config
from snagrecover.protocols import dfu
import sys
import time

def main():
	usb_addr = recovery_config["usb_path"]
	dev = get_usb(usb_addr)

	logger.debug(f"Rockchip usb dev {usb_addr}")

	# Blob made with boot_merger
	if "xpl" in recovery_config["firmware"]:
		try:
			run_firmware(dev, "xpl")
			usb.util.dispose_resources(dev)
		except Exception as e:
			logger.error(f"Failed to run firmware: {e}")
			sys.exit(-1)
	# u-boot binaries.
	elif "code471" in recovery_config["firmware"] and "code472" in recovery_config["firmware"]:
		try:
			run_firmware(dev, "code471")
			usb.util.dispose_resources(dev)
		except Exception as e:
			logger.error(f"Failed to run code471 firmware: {e}")
			sys.exit(-1)
		if "delay" in recovery_config["firmware"]["code471"]:
			delay = recovery_config["firmware"]["code471"]["delay"]
			logger.info(f"Sleeping {delay}ms")
			time.sleep(delay / 1000)
		try:
			run_firmware(dev, "code472")
			usb.util.dispose_resources(dev)
		except Exception as e:
			logger.error(f"Failed to run code472 firmware: {e}")
			sys.exit(-1)
		if "delay" in recovery_config["firmware"]["code472"]:
			delay = recovery_config["firmware"]["code472"]["delay"]
			logger.info(f"Sleeping {delay}ms")
			time.sleep(delay / 1000)
	else:
		logger.error("Missing code471/code472 binary configuration")
		sys.exit(-1)


	if "u-boot-fit" in recovery_config["firmware"]:
		dev = get_usb(usb_addr)
		id = dfu.search_partid(dev, "u-boot.itb")
		if id is None:
			logger.error("Missing u-boot.itb DFU partition")
		dfu_cmd = dfu.DFU(dev, stm32=False)
		dfu_cmd.get_status()
		with open(recovery_config["firmware"]["u-boot-fit"]["path"], "rb") as fd:
			blob = fd.read()
			try:
				dfu_cmd.download_and_run(blob, id, 0, len(blob))
				dfu_cmd.get_status()
				dfu_cmd.detach(id)
			except Exception as e:
				logger.error(f"Failed to load u-boot.itb: {e}")
				sys.exit(-1)
