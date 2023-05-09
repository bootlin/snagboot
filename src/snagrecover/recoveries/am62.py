import usb
import logging
logger = logging.getLogger("snagrecover")
from snagrecover.firmware.firmware import install_firmware
import time

USB_VID = 0x0451
USB_PID = 0x6165
USB_MAX_RETRY = 3

def main():
	dev = usb.core.find(idVendor=USB_VID, idProduct=USB_PID)
	if dev is None:
		raise Exception(f"No USB device with address {USB_VID:x}:{USB_PID:x} was found")
	install_firmware(dev, "tiboot3")
	#USB device should re-enumerate at this point
	retries = 0
	dev = None
	while dev is None:
		if retries >= USB_MAX_RETRY:
			raise Exception("Timeout waiting for USB DFU device!")
		time.sleep(2)
		dev = usb.core.find(idVendor=USB_VID, idProduct=USB_PID)
		retries += 1
	install_firmware(dev, "u-boot")
	install_firmware(dev, "tispl")

