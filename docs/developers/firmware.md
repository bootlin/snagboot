# Supporting new SoCs: firmware handling

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

## Example: AM6x firmware handling

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


