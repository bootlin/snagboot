# Running snagrecover

You can run “snagrecover -h” for a detailed overview of the available options.
The following command line arguments are always required:

 * `-s soc_model`
   This must be one of the SoCs supported by snagrecover, run
 	snagrecover --list-socs for a list of supported SoCs
 * `-f file` or `-F dict`
	Firmware configurations. See [firmware binaries](fw_binaries.md) for more
	information on this.

If you have changed your ROM code's USB VID/PID (this usually isn't the case),
you must specify it using the --rom-usb parameter:

 * `--rom-usb vid:pid`
   USB device address vid:pid or bus-port1.port2.[...]
   e.g. --rom-usb 1111:ffff
   e.g. --rom-usb 3-1.2

If you do not want to rely on vid:pid addresses, you can instead use bus-ports
addresses to specify USB devices in a more stable way.The bus-ports address of a
USB device can be found in sysfs :

`/sys/bus/usb/devices/...`.

When recovering an AM335x SOC via UART using the snagrecover, you have to pass
the --uart flag to the CLI. You can also pass the --baudrate flag in case the
default 115200 baud rate does not fit your device.

The rest of the command line arguments are optional.

Examples:
```bash
snagrecover -s stm32mp15 -f stm32mp15.yaml
snagrecover -s stm32mp15 -F "{'tf-a': {'path': 'binaries/tf-a-stm32.bin'}}" -F "{'fip': {'path': 'binaries/u-boot.stm32'}}"
```

