import usb
import time

USB_RETRIES = 5

def int_arg(arg: str) -> int:
	if "x" in arg:
		return int(arg, base=16)
	else:
		return int(arg)

def get_usb(vid: int, pid: int) -> usb.core.Device:
	dev = usb.core.find(idVendor = vid, idProduct = pid)
	retries = 0
	while dev is None:
		if retries >= USB_RETRIES:
			raise Exception(f"Timeout while waiting for USB device {vid:04x}:{pid:04x}")
		print("Retrying USB connection...")
		time.sleep(2)
		dev = usb.core.find(idVendor = vid, idProduct = pid)
		retries += 1
	return dev

		

