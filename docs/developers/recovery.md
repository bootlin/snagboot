# Supporting new SoCs: implementing the recovery flow

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
function provided by the [utils](../../src/snagrecover/utils.py) module. An
important libusb bug workaround depends on this rule being followed. This means
that the usb.core.find() and usb.utils.find\_descriptors() functions should
never be called by new Snagboot code.

## Example: AM6x recovery module

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

