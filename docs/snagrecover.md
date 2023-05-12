# Running snagrecover

You can run “snagrecover -h” for a detailed overview of the available options.
The following command line arguments are always required: 

 * -s: SoC model, this must be one of the SoCs supported by snagrecover, run
 	snagrecover --list-socs for a list of supported SoCs
 * -f or -F: Firmware configurations. See
    [firmware binaries](fw_binaries.md) for more information on this.

For SAMA5 and SUNXI SoCs, the USB port address must be passed via the
command line:

 * --port: USB device address vid:pid

When recovering an AM335 SOC via UART using the snagrecover, you have to pass
the --uart flag to the CLI. You can also pass the --baudrate flag in case the
default 115200 baud rate does not fit your device.

The rest of the command line arguments are optional.

Examples:
```bash
snagrecover -s stm32mp15 -f stm32mp15.yaml -p 0483:df11
snagrecover -s stm32mp15 -F "{'tf-a': {'path': 'binaries/tf-a-stm32.bin'}}" -F "{'fip': {'path': 'binaries/u-boot.stm32'}}" -p 0483:df11
```

