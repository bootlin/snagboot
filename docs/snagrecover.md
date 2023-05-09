# Running snagrecover

You can run “snagrecover -h” for a detailed overview of the available options.
The following command line arguments are always required: 

 * -s: SoC model, this must be one of the SoCs supported by snagrecover, run
 	snagrecover --list-socs for a list of supported SoCs
 * -f or -F: Firmware configurations. See (firmware binaries)[docs/fw_binaries]
 	for more information on this.

For SAMA5 and SUNXI SoCs, the USB port address must be passed via the
command line:

 * --port: USB device address vid:pid

When recovering an AM335 SOC via UART using the snagrecover, you have to pass
the --uart flag to the CLI. You can also pass the --baudrate flag in case the
default 115200 baud rate does not fit your device.

The rest of the command line arguments are optional.

