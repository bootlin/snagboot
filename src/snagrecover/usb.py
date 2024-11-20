import usb
import platform
import weakref
import gc
import importlib
import sys

class SnagbootUSBContext():
	"""
	This class manages USB device objects instanciated by calling
	usb.core.find(). It makes sure that all previous USB devices are
	unreferenced when a rescan is issued.

	This is necessary to dodge a bug in some versions of libusb for
	Windows, where two different root hubs are assigned the same bus
	number. This can happen when a reenumeration is issued on an existing
	libusb context. By returning only weak references to USB device
	objects, we can ensure that the underlying libusb context is destroyed
	and recreated every time an enumeration is performed.
	"""

	devices = []

	def hard_rescan():
		# delete what should be the last references to the underlying libusb context
		if __class__.devices != []:
			__class__.devices.clear()

			gc.collect()

			"""
			In some cases, a cache entry for the
			usb.backend.libusb1 module can prevent garbage
			collection of the libusb context.
			"""
			importlib.invalidate_caches()
			if "usb.backend.libusb1" in sys.modules:
				importlib.reload(usb.backend.libusb1)

		__class__.devices = list(usb.core.find(find_all=True))
		if platform.system() == "Windows":
			__class__.check_for_libusb_bug()

	def rescan():
		__class__.devices.clear()
		__class__.devices = list(usb.core.find(find_all=True))
		if platform.system() == "Windows":
			__class__.check_for_libusb_bug()

	def check_for_libusb_bug(retry=1):
		"""
		sanity check: some versions of libusb on Windows sometime allocate the same bus number
		to two different root hubs. Check if this has happened and try to fix it if
		it has.
		"""
		root_hubs = [dev for dev in __class__.devices if dev.parent is None]
		bus_numbers = set([dev.bus for dev in root_hubs])
		if len(root_hubs) > len(bus_numbers):
			if retry == 0:
				raise ValueError("libusb bug detected! Two root hubs were assigned the same bus number! Please update libusb to a newer version and replace the dll provided by the 'libusb' Python package!")

			__class__.hard_rescan()
			__class__.check_for_libusb_bug(retry=0)

	def find(**args):
		for dev in __class__.devices:
			tests = (hasattr(dev, key) and val == getattr(dev, key) for key, val in args.items())
			if all(tests):
				yield weakref.proxy(dev)

