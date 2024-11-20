# Supporting new SoCs: recovery flow

Now that you have designed a recovery flow for your Snagrecover support, you can
start actually implementing it in the codebase. Three main modules will be
required:

 * protocols/<your_protocol>.py: implementation of USB class protocols such as HID or DFU
 * firmware/fw_<soc_family>.py: parsing, downloading and execution of firmware binaries
 * recoveries/<soc\_family>.py: high-level implementation of the recovery flow

The following section describes the "protocols" modules in more detail.

During the recovery of the target device, Snagrecover will have to communicate
with the ROM code and subsequent boot stages, using a specific USB
communication protocol. These USB protocols often differ from one another, but
they almost always provide the following commands:

 * read a fixed-sized value from a register on the target device
 * write a fixed-sized value to a register on the target device
 * write a variable-size binary blob to the target device's RAM
 * make the target device run code at a specific address in RAM

Snagrecover has an abstract representation of this set of commands, called
["MemoryOps"](../../src/snagrecover/protocols/memory_ops.py). New protocols
should implement this interface if possible. There can be a few
protocol-specific commands that fall out of the scope of this interface, but
basic read, write and run commands should be called through a MemoryOps
instance.

Protocols can sometimes stack on top of each other. For example, i.MX recovery
communicates with the target using the SDP protocol through an HID device. In
cases like these, intermediary protocols which do not communicate directly with
the firmware handling layer do not have to implement the MemoryOps interface.

## Example: implementation of the USB FEL protocol for SUNXI support

```python
import usb
from snagrecover import utils

# Class representing a USB FEL device
class FEL():
	MAX_MSG_LEN = 65536
	...

	# Snagrecover protocol classes often wrap around a USB device
	def __init__(self, dev: usb.core.Device, timeout: int):
		ep_in, ep_out = None, None
		for ep in intf.endpoints():
			# Find FEL-specific endpoints
			...
		self.ep_in = ep_in
		self.ep_out = ep_out
		self.timeout = timeout

	...

	"""
	These methods perform packet transfers defined by the FEL specification.
	They are protocol-specific plumbing, and will not be accessed by the
	upper layers of Snagrecover
	"""
	def aw_exchange(self, length: int, out: bool, packet: bytes = b"") -> bytes:
		...
	def request(self, request: str, response_len: int) -> bytes:
		...
	def message(self, request: str, addr: int, length: int, data: bytes = b"") -> bytes:
		...

	"""
	This is an example of a protocol-specific method which does not fit
	into the MemoryOps interface. It is called directly by the SUNXI
	high-level recovery layer to verify the status of the ROM code.
	"""
	def verify_device(self):
		...

	"""
	The following methods actually implement the MemoryOps interface. They
	will be called by the firmware layer of Snagrecover, through a
	MemoryOps instance.
	"""
	def read32(self, addr: int) -> int:
		data = self.message("FEL_UPLOAD", addr, 4)
		return int.from_bytes(data, "little")

	def write32(self, addr: int, value: int) -> bool:
		packet = value.to_bytes(4, "little")
		nbytes = self.message("FEL_DOWNLOAD", addr, 4, packet)
		return int.from_bytes(nbytes, "little") == 4

	def write_blob(self, blob: bytes, addr: int, offset: int, size: int) ->bool:
		ret = True
		chunk_addr = addr

		for chunk in utils.dnload_iter(blob[offset:offset + size], FEL.MAX_MSG_LEN):
			N = len(chunk)
			nbytes = self.message("FEL_DOWNLOAD", chunk_addr, N, chunk)
			ret &= int.from_bytes(nbytes, "little") == N
			chunk_addr += N

		return ret

	def jump(self, addr: int) -> bool:
		self.message("FEL_RUN", addr, 0)
		return True

```

