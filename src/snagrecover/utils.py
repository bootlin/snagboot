import sys
import re
import usb
import time

USB_RETRIES = 5
USB_INTERVAL = 1

def access_error(dev_type: str, dev_addr: str):
	print(f"Device access error: failed to access {dev_type} device {dev_addr}, please check its presence and access rights", file=sys.stderr)
	sys.exit(-1)

def cli_error(error: str):
	print(f"CLI error: {error}", file=sys.stderr)
	sys.exit(-1)

def get_usb(vid: int, pid: int):
	dev = usb.core.find(idVendor=vid, idProduct=pid)
	retry = 0
	while dev is None:
		time.sleep(USB_INTERVAL)
		print(f"USB retry {retry}/{USB_RETRIES}")
		if retry >= USB_RETRIES:
			access_error("USB", f"{vid:04x}:{pid:04x}")
		dev = usb.core.find(idVendor=vid, idProduct=pid)
		retry += 1
	try:
		dev.get_active_configuration()
	except usb.core.USBError:
		access_error("USB", f"{vid:04x}:{pid:04x}")
	return dev

def parse_usb(usb_id: str) -> tuple:
	expr = re.compile("([0-9a-fA-F]{1,4}):([0-9a-fA-F]{1,4})")
	m = expr.match(usb_id)
	if m is None:
		cli_error(f"invalid USB ID {usb_id}")
	vid = int(m.group(1), base=16)
	pid = int(m.group(2), base=16)
	return (vid,pid)

def dnload_iter(blob: bytes, chunk_size: int):
	# parse binary blob by chunks of chunk_size bytes
	L = len(blob)
	N = L // chunk_size
	R = L % chunk_size
	for i in range(N):
		yield blob[chunk_size * i:chunk_size * (i + 1)]
	if R > 0:
		yield blob[chunk_size * N:chunk_size * N + R]

