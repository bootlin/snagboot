# Running snagrecover

You can run “snagrecover -h” for a detailed overview of the available options.
The following command line arguments are always required: 

 * `-s soc_model`
   This must be one of the SoCs supported by snagrecover, run
 	snagrecover --list-socs for a list of supported SoCs
 * `-f file` or `-F dict`
    Firmware configurations. See
    [firmware binaries](fw_binaries.md) for more information on this.

If you have changed your ROM code's USB VID/PID, you must specify it using the --rom-usb parameter: 

 * `--rom-usb vid:pid`
   USB device address vid:pid
   e.g. --rom-usb 1111:ffff

When recovering an AM335x SOC via UART using the snagrecover, you have to pass
the --uart flag to the CLI. You can also pass the --baudrate flag in case the
default 115200 baud rate does not fit your device.

The rest of the command line arguments are optional.

Examples:
```bash
snagrecover -s stm32mp15 -f stm32mp15.yaml
snagrecover -s stm32mp15 -F "{'tf-a': {'path': 'binaries/tf-a-stm32.bin'}}" -F "{'fip': {'path': 'binaries/u-boot.stm32'}}"
```

