import usb
import time
import sys

USB_RETRIES = 5

def usb_error(vid: int, pid: int):
	print(f"Device access error: could not open USB device {vid:04x}:{pid:04x}", file=sys.stderr)
	print("If the device exists, make sure that you have rw access rights to it", file=sys.stderr)
	print("If that is not the case, you can add the following line to your /etc/udev/rules.d/80-snagboot.rules file:\n", file=sys.stderr)
	print("SUBSYSTEM==\"usb\", ATTRS{idVendor}==\"" + f"{vid:04x}" + "\", ATTRS{idProduct}==\"" + f"{pid:04x}" + "\", MODE=\"0660\", GROUP=\"plugdev\"", file=sys.stderr)
	sys.exit(-1)

def cli_error(error: str):
	print(f"CLI error: {error}", file=sys.stderr)
	sys.exit(-1)

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
			usb_error(vid, pid)
		print(f"Retrying USB connection ({retries}/{USB_RETRIES})...")
		time.sleep(2)
		dev = usb.core.find(idVendor = vid, idProduct = pid)
		retries += 1
	try:
		dev.get_active_configuration()
	except usb.core.USBError:
		usb_error(vid, pid)
	return dev
