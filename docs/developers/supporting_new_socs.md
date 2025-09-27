# Adding support for a new family of SoCs

First of all, thank you for your interest in contributing to Snagboot!

The codebase is divided into three distinct parts:

 * Snagrecover: downloads and runs U-Boot on a device powered up in USB recovery mode
 * Snagflash: flashes and configures storage devices over a USB gadget exposed by U-Boot
 * Snagfactory: runs snagrecover and snagflash in parallel on groups of devices

The only part of Snagboot which is SoC-specific is Snagrecover. Therefore, when
adding support for a new family of SoCs, your efforts will be exclusively
focused on the recovery aspect of Snagboot.

The following documentation is meant to guide contributors who plan to add
support for a new family of SoCs to Snagboot. It lays out the main steps required
to design and implement such a support and specifies the core rules to follow
when integrating new code to the project.

Implementation of a new SoC family support can be broken down into six steps:

 1. Inventory of SoC models and their USB boot modes
 2. Recovery flow design
 3. Implementation of basic USB communication with the target
 4. Implementation of firmware handling
 5. Implementation of the recovery flow
 6. Documentation of the new support

For each of these steps, an example is given using an existing support.

Once your new support is ready, you can simply open a GitHub pull request. If
more information is required, you can open a GitHub issue or contact us via
email.

## Hardware inventory

Snagrecover supports a precisely defined set of SoC models. These are all
listed in [supported_socs.yaml](https://github.com/bootlin/snagboot/blob/main/src/snagrecover/supported_socs.yaml).
Models are grouped into SoC families. These are groups of devices that support
similar recovery flows.

When adding a new SoC family support, you should begin by making a list of all
the SoC models that you wish to include in the support.

Then, for each model in your list, procure the SoC's technical reference manual
or other relevant documentation and read the section which describes the USB
boot mode. Confirm that all SoC models in your list have similar USB boot
procedures. If this is not the case, you will have to separate the list into
multiple groups, with each group having its own separate support.

Your list of SoC models defines a Snagrecover SoC family. At this point, you
should choose a suitable name for it and add the SoC models to the
[supported_socs.yaml](https://github.com/bootlin/snagboot/blob/main/src/snagrecover/supported_socs.yaml) file.

The next step is to procure a set of boards that will allow you to test
Snagrecover on your SoC family. At least one tested SoC model is required for a
family to be added to Snagrecover. If some of your SoC models have special
quirks or particularities, it is recommended that you test them as well.

### Example: the "imx" SoC family

Here is a nonexhaustive list of i.MX SoCs supported by Snagrecover:

imx28, imx53, imx6q, imx6ull, imx7d, imx8mm, imx8qm, imx8qxp, imx91, imx93,
imx6d, imx6sl, imx6sll, ...

All of these devices are able to boot in USB recovery mode by exposing an HID
gadget to the host machine. A vendor-specific variety of the SDP protocol is
used over this HID layer to download and run code in internal RAM.

## Recovery flow design

Once you've specified an SoC family, the next step is to design a recovery flow
for it.

The goal of Snagrecover is to go from USB recovery mode to a U-Boot CLI.
Different SoC families use different methods to achieve this. Recovery flows are
what allow the Snagrecover codebase to maintain a minimum level of coherency
despite these differences. Recovery flows are basically an list of firmware that
should be downloaded and executed on the target device to achieve full recovery.

For example, here is a very simple recovery flow:

```
1. get USB recovery device exposed by ROM code
2. download and run U-Boot SPL in internal SRAM, to initialize external RAM
3. get USB recovery device exposed by SPL
4. download and run U-Boot proper in external RAM
```

Designing a recovery flow is the trickiest part of any Snagrecover support, as
it must follow several constraints:

 * No non-volatile storage devices must be modified or relied upon.
 * The target device must be uniquely identifiable from its bus and port
   numbers, which are reported by libusb. This is to allow parallel recovery
   of multiple devices which use the same USB vid:pid. It can become tricky
   if you must access the USB device through a higher-level system driver such
   as hidraw.
 * Only the USB link should be used to communicate with the target
 * Specific details of firmware handling and communication protocols must be
   delegated to the "firmware" and "protocols" layers of Snagrecover (these will be
   covered in more detail later on).

If you reference existing recovery tools to design your recovery flow, make
sure to respect the terms of the original codebase's license. All code
contributed to Snagboot must fall under a GPLv2-compatible license.

### Example: Recovery flow for SAMA5 SoCs

1. Get USB device exposed by ROM code, using bus and port numbers
2. Get the corresponding serial port device (SAMA5 ROM codes enumerate as serial ports)
3. Check the board ID by reading the CIDR register
4. Download and run the "lowlevel" firmware, to initialize the clock tree
5. Download and run the "extram" firmware, to initialize the external RAM
6. Write to the AXMIX\_REMAP register to remap ROM addresses to SRAM0
7. Download and run U-Boot proper.
8. Close the serial port.

## Supporting new SoCs: recovery flow

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
["MemoryOps"](https://github.com/bootlin/snagboot/blob/main/src/snagrecover/protocols/memory_ops.py). New protocols
should implement this interface if possible. There can be a few
protocol-specific commands that fall out of the scope of this interface, but
basic read, write and run commands should be called through a MemoryOps
instance.

Protocols can sometimes stack on top of each other. For example, i.MX recovery
communicates with the target using the SDP protocol through an HID device. In
cases like these, intermediary protocols which do not communicate directly with
the firmware handling layer do not have to implement the MemoryOps interface.

### Example: implementation of the USB FEL protocol for SUNXI support

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

## Firmware handling

A central feature of recovery flows is the ability to run precompiled firmware
on the target device. These firmware can play various roles, for example:

 * Initializing external RAM
 * Initializing the clock tree
 * Configuring ARM execution levels

It is important to identify precisely what firmware are required by your
recovery flow, what is their composition and role, and how users can compile
them. The final firmware to be run on the target is U-Boot proper, which marks
the end of the recovery process.

Each SoC family in Snagrecover must implement a firmware-handling backend,
which is called by the recovery layer using the "run\_firmware()" function. This
function takes the following parameters:

 * port: a USB or protocol-specific device, used for communicating with the target
 * fw\_name: a unique name identifying a firmware in the recovery flow
 * subfw\_name: specifies a firmware sub-component for cases where a single
   firmware image has multiple stages that need to be downloaded and run
   separately.

The run\_firmware() function will load the firmware binary from the filesystem
using the path specified in the user's firmware configuration file. It will then
pass control to a backend specific to the SoC family.

This backend will then be responsible for downloading and running the firmware
binary on the target.

### Example: AM6x firmware handling

```python
"""
The fw_blob parameter holds the firmware binary read from the filesystem.
"""
def am6x_run(dev, fw_name: str, fw_blob: bytes):
	# find DFU altsetting corresponding to firmware
	if fw_name == "tiboot3":
		partname = "bootloader"
	elif fw_name == "tispl":
		partname = "tispl.bin"
	elif fw_name == "u-boot":
		partname = "u-boot.img"
	else:
		cli_error(f"unsupported firmware {fw_name}")

	"""
	DFU is one of the rare supported protocols which does not fit the
	MemoryOps interface, since it merges write and run commands together
	and does not allow downloading blobs at arbitrary memory locations.
	"""
	partid = dfu.search_partid(port, partname)
	if partif is None and partprefix == "@Partition3":
		partprefix = "@SSBL"
		partid = dfu.search_partid(port, partprefix, match_prefix)

	if partid is None:
		raise Exception(f"No DFU altsetting found with iInterface=...

	"""
	Here, the USB device is wrapped in a DFU protocol object.
	The protocol layer will handle the low-level communication details.
	"""
	dfu_cmd = dfu.DFU(port)
	dfu_cmd.download_and_run(fw_blob, partid, offset=0, size_len(fw_blob))
	return None
```


## Implementing the recovery flow

Now that you have a fully functional firmware-handling backend, you can
implement the actual recovery flow. This should be simpler than the previous
steps, since all of the necessary building blocks are now available.

Each SoC family has an associated recovery module at recoveries/<soc_family>.py.
This module contains a main() function which is called by the Snagrecover CLI.
Create a similar module for you SoC family and add a main function to it.  In
the [utils](../../src/snagrecover/utils.py) module, there is a function called
get_recovery(). Modify this function to add your SoC family.

Your main recovery function will be called without any parameters. All the
information you could require should be available through the immutable
"recovery_config" dictionary, which contains the arguments passed to the
Snagrecover CLI.

```python
from snagrecover.config import recovery_config

print(recovery_config)
```

This dictionary should at least contain the following information:

 * usb\_path: path which uniquely identifies a physical USB port
 * soc\_model
 * soc\_family
 * firmware: Dictionary containing the parsed firmware configuration provided by
   the user. This should mostly be accessed by your firmware backend.

Your main recovery function should mostly consist of:

 * fetching the USB recovery device for each stage
 * calling run\_firmware() for each of the firmware stages

Fetching USB device instances should **only** be done using the get\_usb()
function provided by the [utils](https://github.com/bootlin/snagboot/blob/main/src/snagrecover/utils.py) module. An
important libusb bug workaround depends on this rule being followed. This means
that the usb.core.find() and usb.utils.find\_descriptors() functions should
never be called by new Snagboot code.

### Example: AM6x recovery module

```python
def send_tiboot3(dev):
	run_firmware(dev, "tiboot3")
	# USB device should re-enumerate at this point
	usb.util.dispose_resources(dev)
	# without this delay, USB device will be present but not ready
	time.sleep(1)


def main():
	usb_addr = recovery_config["usb_path"]
	dev = get_usb(usb_addr)

	send_tiboot3(dev)

	dev = get_usb(usb_addr)

	# Some versions of U-Boot on some devices require tiboot3 to be run twice
	if dfu.search_partid(dev, "bootloader") is not None:
		send_tiboot3(dev)
		dev = get_usb(usb_addr)

	run_firmware(dev, "tispl")
	run_firmware(dev, "u-boot")

	time.sleep(2)

	# For newer versions of U-Boot, only SPL will run from the
	# previous commands and the u-boot firmware should be sent
	# one more time.

	dev = get_usb(usb_addr, error_on_fail=False)
	if dev is not None:
		run_firmware(dev, "u-boot")

```

## Supporting new SoCs: Documenting your new support

Once your new SoC support is fully functional, the last step is to document it
in the same way as the existing SoC supports.

Update the [README](https://github.com/bootlin/snagboot/blob/main/README.md) to mention that your SoC family is supported.

Add a section for your SoC family in:

[Setting up your device for recovery](https://github.com/bootlin/snagboot/blob/main/docs/snagrecover.md/#setting-up-your-device-for-recovery).

and in:

[Preparing recovery firmware](https://github.com/bootlin/snagboot/blob/main/docs/snagrecover.md/#preparing-recovery-firmware).

If there are any quirks and pitfalls that users should watch out for when
recovering your SoCs, you can mention them in
[troubleshooting.md](https://github.com/bootlin/snagboot/blob/main/docs/troubleshooting.md).

