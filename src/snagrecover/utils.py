import sys
import re
import usb
import time
import logging
logger = logging.getLogger("snagrecover")

from snagrecover.usb import SnagbootUSBContext

import yaml
import os

USB_RETRIES = 9
USB_INTERVAL = 1

def get_family(soc_model: str) -> str:
        with open(os.path.dirname(__file__) + "/supported_socs.yaml", "r") as file:
                socs = yaml.safe_load(file)
        family = {**socs["tested"], **socs["untested"]}[soc_model]["family"]
        return family

def is_usb_path(usb_addr) -> bool:
	return isinstance(usb_addr, tuple) and isinstance(usb_addr[1], tuple)

def access_error(dev_type: str, dev_addr: str):
	logger.info(f"Device access error: failed to access {dev_type} device {dev_addr}, please check its presence and access rights")
	sys.exit(-1)

def cli_error(error: str):
	logger.info(f"CLI error: {error}")
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
	path_regex = re.compile(r'^(\d+)-(\d+)((\.\d+)*)$')
	match = path_regex.match(path)
	if match is None:
		cli_error(f"failed to parse USB device path {path}")
	groups = match.groups()
	port_numbers = [groups[1]]
	if groups[2] != "":
		port_numbers += groups[2].split(".")[1:]
	# Formatted for usb.core.find
	port_tuple = tuple([int(x) for x in port_numbers])
	return (int(groups[0]), port_tuple)

def find_usb_paths(usb_id: tuple) -> list:
	(vid,pid) = usb_id
	usb_paths = []

	logger.debug(f"Searching for USB device paths matching {prettify_usb_addr((vid,pid))}...")

	SnagbootUSBContext.rescan()
	devices = list(SnagbootUSBContext.find(idVendor=vid, idProduct=pid))

	for dev in devices:
		usb_paths.append((dev.bus, dev.port_numbers))

	return usb_paths

def count_duplicates(lst):
	return len(lst) - len(set(lst))

def usb_addr_to_path(usb_addr: str, find_all=False) -> tuple:
	"""
	parses vid:pid addresses into (vid,pid)
	and bus-port1.port2.[...] into (bus, (port1,port2,...))
	"""

	if ":" in usb_addr:
		usb_id = parse_usb_ids(usb_addr)
		usb_paths = find_usb_paths(usb_id)
		if usb_paths == []:
			return None
		if find_all:
			if count_duplicates(usb_paths) > 0:
				time.sleep(1)

				SnagbootUSBContext.hard_rescan()
				usb_paths = find_usb_paths(usb_id)

				if count_duplicates(usb_paths) > 0:
					logger.error(f"Found {count_duplicates(usb_paths)} duplicate USB paths! {usb_paths}")
					access_error("USB", usb_addr)

			return usb_paths

		if len(usb_paths) > 1:
			logger.error(f"Too many results for address {usb_addr}! {usb_paths}")
			access_error("USB", usb_addr)

		return usb_paths[0]
	else:
		return parse_usb_path(usb_addr)

def prettify_usb_addr(usb_addr) -> str:
	if is_usb_path(usb_addr):
		return f"{usb_addr[0]}-{'.'.join([str(x) for x in usb_addr[1]])}"
	else:
		return f"{usb_addr[0]:04x}:{usb_addr[1]:04x}"

def get_usb(usb_path, error_on_fail=True, retries=USB_RETRIES) -> usb.core.Device:
	pretty_addr = prettify_usb_addr(usb_path)
	SnagbootUSBContext.rescan()

	for i in range(retries + 1):
		SnagbootUSBContext.rescan()
		dev_list = list(SnagbootUSBContext.find(bus=usb_path[0], port_numbers=usb_path[1]))

		nb_devs = len(dev_list)

		if nb_devs == 1:
			dev = dev_list[0]

			try:
				dev.get_active_configuration()
				return dev
			except NotImplementedError:
				return dev
			except usb.core.USBError:
				logger.warning(f"Failed to get configuration descriptor for device at {pretty_addr}!")

		elif nb_devs > 1:
			logger.info(f"Found too many ({nb_devs}) possible results matching {pretty_addr}!")
			logger.warning(f"Too many results for address {pretty_addr}!\{str(dev_list)}")

		logger.info(f"USB retry {i + 1}/{retries}")
		time.sleep(USB_INTERVAL)


	if error_on_fail:
		access_error("USB", pretty_addr)

	return None


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

def get_recovery(soc_family: str):
	if soc_family == "stm32mp1":
		from snagrecover.recoveries.stm32mp1 import main as stm32_recovery
		return stm32_recovery
	elif soc_family == "sama5":
		from snagrecover.recoveries.sama5 import main as sama5_recovery
		return sama5_recovery
	elif soc_family == "imx":
		from snagrecover.recoveries.imx import main as imx_recovery
		return imx_recovery
	elif soc_family == "am335x":
		from snagrecover.recoveries.am335x import main as am335x_recovery
		return am335x_recovery
	elif soc_family == "sunxi":
		from snagrecover.recoveries.sunxi import main as sunxi_recovery
		return sunxi_recovery
	elif soc_family == "am6x":
		from snagrecover.recoveries.am6x import main as am6x_recovery
		return am6x_recovery
	else:
		cli_error(f"unsupported board family {soc_family}")

