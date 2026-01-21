import sys
import os
import platform
import re
import usb
import time
from dataclasses import astuple
import struct
import logging
import errno

logger = logging.getLogger("snagrecover")

from snagrecover.usb import SnagbootUSBContext

import yaml
import importlib.resources

import lzma
import bz2
import gzip

USB_RETRIES = 9
USB_INTERVAL = 1


def get_compression_method(path: str) -> str:
	path_head, ext = os.path.splitext(path)

	if ext in [".xz", ".bz2", ".gz"]:
		return ext[1:]

	return None


def get_bmap_path(path: str):
	comp = get_compression_method(path)

	if comp is not None:
		path_head, _ = os.path.splitext(path)
		return path_head + ".bmap"
	else:
		return path + ".bmap"


def open_compressed_file(path: str, mode):
	comp = get_compression_method(path)

	if comp == "xz":
		file = lzma.open(path, mode)
	elif comp == "bz2":
		file = bz2.open(path, mode)
	elif comp == "gz":
		file = gzip.open(path, mode)
	else:
		return open(path, mode)

	logger.info(f"Opening {path} with on-the-fly decompression")

	return file


def get_supported_socs():
	yaml_text = (
		importlib.resources.files("snagrecover")
		.joinpath("supported_socs.yaml")
		.read_text()
	)

	return yaml.safe_load(yaml_text)


def get_soc_aliases(socs: dict):
	all_socs = {**socs["tested"], **socs["untested"]}
	aliases = {}

	for model in all_socs:
		for alias in all_socs[model].get("aliases", []):
			if alias in aliases:
				logger.warning(
					f"SoC alias {alias} appears more than once in the list of supported SoCs!"
				)

			aliases[alias] = model

	return aliases


def resolve_soc_model(soc_model: str):
	"""
	Checks if an SoC model is supported by snagrecover. If a matching alias
	is found, resolves it.
	"""
	socs = get_supported_socs()

	if soc_model not in {**socs["tested"], **socs["untested"]}:
		# Look for an matching alias
		aliases = get_soc_aliases(socs)
		if soc_model in aliases:
			logger.info(f"SoC model {soc_model} is an alias for {aliases[soc_model]}")
			return aliases[soc_model]

		cli_error(
			f"unsupported soc model {soc_model}, supported socs: \n" + yaml.dump(socs)
		)

	return soc_model


def get_family(soc_model: str) -> str:
	socs = get_supported_socs()
	family = {**socs["tested"], **socs["untested"]}[soc_model]["family"]
	return family


def is_usb_path(usb_addr) -> bool:
	return isinstance(usb_addr, tuple) and isinstance(usb_addr[1], tuple)


def access_error(dev_type: str, dev_addr: str, log_err: bool = True):
	if log_err:
		logger.error(
			f"Device access error: failed to access {dev_type} device {dev_addr}, please check its presence and access rights"
		)

	sys.exit(-1)


def cli_error(error: str):
	logger.error(f"CLI error: {error}")
	sys.exit(-1)


def parse_usb_ids(usb_id: str) -> tuple:
	expr = re.compile("([0-9a-fA-F]{1,4}):([0-9a-fA-F]{1,4})")
	m = expr.match(usb_id)
	if m is None:
		cli_error(f"invalid USB ID {usb_id}")
	vid = int(m.group(1), base=16)
	pid = int(m.group(2), base=16)
	return (vid, pid)


def parse_usb_path(path: str) -> tuple:
	path_regex = re.compile(r"^(\d+)-(\d+)((\.\d+)*)$")
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
	(vid, pid) = usb_id
	usb_paths = []

	logger.debug(
		f"Searching for USB device paths matching {prettify_usb_addr((vid, pid))}..."
	)

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
					logger.error(
						f"Found {count_duplicates(usb_paths)} duplicate USB paths! {usb_paths}"
					)
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


def active_cfg_check(dev: usb.core.Device):
	try:
		dev.get_active_configuration()
	except NotImplementedError:
		return True
	except usb.core.USBError:
		logger.warning(
			f"Failed to get configuration descriptor for device at {prettify_usb_addr((dev.bus, dev.port_numbers))}!"
		)
		return False

	return True


def permissions_check(dev: usb.core.Device) -> bool:
	"""
	Checks if a device has the device file access rights to be accessed.
	"""
	try:
		dev.get_active_configuration()
	except usb.core.USBError as e:
		if e.errno == errno.EACCES:  # device access error
			return False
	return True


def get_usb(
	usb_path, error_on_fail=True, retries=USB_RETRIES, ready_check=active_cfg_check
) -> usb.core.Device:
	pretty_addr = prettify_usb_addr(usb_path)
	SnagbootUSBContext.rescan()

	dev = None

	log_access_error = True
	for i in range(retries + 1):
		if i > 0:
			logger.info(f"USB retry {i}/{retries}")

		SnagbootUSBContext.rescan()
		dev_list = list(
			SnagbootUSBContext.find(bus=usb_path[0], port_numbers=usb_path[1])
		)

		nb_devs = len(dev_list)

		if nb_devs == 1:
			dev = dev_list[0]

			if ready_check(dev):
				return dev

		elif nb_devs > 1:
			logger.info(
				f"Found too many ({nb_devs}) possible results matching {pretty_addr}!"
			)
			logger.warning(
				f"Too many results for address {pretty_addr}! {str(dev_list)}"
			)

		time.sleep(USB_INTERVAL)

	if dev is not None and permissions_check(dev):
		logger.error(
			f"USB Device was found at address {pretty_addr} but can't be accessed because of a device file access rights issue."
		)
		if platform.system() == "Linux":
			logger.error(
				"Please check your udev config (refer to https://snagboot.readthedocs.io/en/latest/installing/#installation-on-linux)."
			)
			logger.error("The following udev rule grants access to the USB device:")
			logger.error(
				f'SUBSYSTEM=="usb", ATTRS{{idVendor}}=="{dev.idVendor:04x}", ATTRS{{idProduct}}=="{dev.idProduct:04x}", MODE="0660", TAG+="uaccess"'
			)
		elif platform.system() == "Windows":
			logger.error(
				f"Please check that the 'libusb-win32' driver is bound to this USB device ID: {dev.idVendor:04x}:{dev.idProduct:04x}"
			)
			logger.error(
				"This is usually done with the Zadig tool, please check the Snagboot installation guide (https://snagboot.readthedocs.io/en/latest/installing/#installation-on-windows-10-or-11) for more information."
			)
		# Don't log 'access_error' generic error message's
		log_access_error = False

	if error_on_fail:
		access_error("USB", pretty_addr, log_access_error)

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
		yield blob[chunk_size * i : chunk_size * (i + 1)]
	if R > 0:
		yield blob[chunk_size * N : chunk_size * N + R]


def get_recovery(soc_family: str):
	if soc_family == "stm32mp":
		from snagrecover.recoveries.stm32mp import main as stm32_recovery

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
	elif soc_family == "am62lx":
		from snagrecover.recoveries.am62lx import main as am62lx_recovery

		return am62lx_recovery
	elif soc_family == "zynqmp":
		from snagrecover.recoveries.zynqmp import main as zynqmp_recovery

		return zynqmp_recovery
	elif soc_family == "keembay":
		from snagrecover.recoveries.keembay import main as keembay_recovery

		return keembay_recovery
	elif soc_family == "bcm":
		from snagrecover.recoveries.bcm import main as bcm_recovery

		return bcm_recovery
	elif soc_family == "amlogic":
		from snagrecover.recoveries.amlogic import main as amlogic_recovery

		return amlogic_recovery
	else:
		cli_error(f"unsupported board family {soc_family}")


class BinFileHeader:
	"""
	Generic class representing a packed C struct embedded in a bytearray.
	"""

	fmt = ""
	class_size = 0
	offset = 0

	@classmethod
	def read(cls, data, offset=0):
		obj = cls(*struct.unpack(cls.fmt, data[offset : offset + cls.class_size]))
		obj.offset = offset

		return obj

	@classmethod
	def write(cls, self, data):
		offset = self.offset
		data[offset : offset + cls.class_size] = struct.pack(cls.fmt, *astuple(self))
