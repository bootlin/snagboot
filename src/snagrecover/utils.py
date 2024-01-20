import sys
import re
import usb
import time
import functools

USB_RETRIES = 5
USB_INTERVAL = 1


def is_usb_path(usb_addr) -> bool:
	return isinstance(usb_addr, tuple) and isinstance(usb_addr[1], tuple)

def access_error(dev_type: str, dev_addr: str):
	print(f"Device access error: failed to access {dev_type} device {dev_addr}, please check its presence and access rights", file=sys.stderr)
	sys.exit(-1)

def cli_error(error: str):
	print(f"CLI error: {error}", file=sys.stderr)
	sys.exit(-1)

def parse_usb_ids(usb_id: str) -> tuple:
	expr = re.compile("([0-9a-fA-F]{1,4}):([0-9a-fA-F]{1,4})")
	m = expr.match(usb_id)
	if m is None:
		cli_error(f"invalid USB ID {usb_id}")
	vid = int(m.group(1), base=16)
	pid = int(m.group(2), base=16)
	return (vid,pid)

def parse_usb_path(path: str) -> tuple:
	path_regex = re.compile('^(\d+)-(\d+)((\.\d+)*)$')
	match = path_regex.match(path)
	if match is None:
		cli_error(f"failed to parse USB device path {path}")
	groups = match.groups()
	port_numbers = groups[1]
	if groups[2] != "":
		port_numbers = [port_numbers] + groups[2].split(".")[1:]
	# Formatted for usb.core.find
	port_tuple = tuple([int(x) for x in port_numbers])
	return (int(groups[0]), port_tuple)

def parse_usb_addr(usb_addr: str) -> tuple:
	"""
	parses vid:pid addresses into (vid,pid)
	and bus-port1.port2.[...] into (bus, (port1,port2,...))
	"""
	if ":" in usb_addr:
		return parse_usb_ids(usb_addr)
	else:
		return parse_usb_path(usb_addr)

def prettify_usb_addr(usb_addr) -> str:
	if is_usb_path(usb_addr):
		return f"{usb_addr[0]}-{'.'.join([str(x) for x in usb_addr[1]])}"
	else:
		return f"{usb_addr[0]:04x}:{usb_addr[1]:04x}"

def get_usb(addr, error_on_fail=True) -> usb.core.Device:
	if is_usb_path(addr):
		# bus-port1.port2.(...)
		find_usb = functools.partial(usb.core.find,
					bus=addr[0],
					port_numbers=addr[1])
	else:
		# vid:pid
		find_usb = functools.partial(usb.core.find,
					idVendor=addr[0],
					idProduct=addr[1])

	pretty_addr = prettify_usb_addr(addr)
	dev = find_usb()
	retry = 0
	while dev is None:
		time.sleep(USB_INTERVAL)
		print(f"USB retry {retry}/{USB_RETRIES}")
		if retry >= USB_RETRIES:
			if error_on_fail:
				access_error("USB", pretty_addr)
			return None
		dev = find_usb()
		retry += 1

	try:
		dev.get_active_configuration()
	except usb.core.USBError:
		if error_on_fail:
			access_error("USB", pretty_addr)
		return None

	return dev

def reset_usb(dev: usb.core.Device) -> None:
        try:
                dev.reset()
        except usb.core.USBError:
                pass

def dnload_iter(blob: bytes, chunk_size: int):
	# parse binary blob by chunks of chunk_size bytes
	L = len(blob)
	N = L // chunk_size
	R = L % chunk_size
	for i in range(N):
		yield blob[chunk_size * i:chunk_size * (i + 1)]
	if R > 0:
		yield blob[chunk_size * N:chunk_size * N + R]

