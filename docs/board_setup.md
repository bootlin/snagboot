# Setting up your board for recovery

Your board should be properly set up to enter the SoC vendor’s specific recovery
mode (more vendor-specific details below). This usually involves setting some
boot fuses, removing some external boot media and/or other board-specific
actions. Referring to your board's user guide can help you find out
what you need to do here.

The board should be connected to your host PC via USB The specific USB port to
use is board-dependent, it is usually the OTG port. We also strongly recommend
that you open a UART connection to the board so that you can monitor the
recovery process as it unfolds. On STM32MP1 discovery kits, the default UART is
often wired to the ST-LINK port.

Once your board is in recovery mode, a new USB device should appear on your host
system. This is the device that snagrecover will communicate with. Below are
some vendor-specific hints for setting up your board for recovery.

## ST STM32MP1

The recovery mode used here is DFU. Connect the USB DRP port to your host PC.
Power your board, making sure that the boot fuses are configured to boot from
DFU. The SoC can also fall back to DFU if all other boot options fail. At this
point, a USB DFU device should appear on your host system.

## Microchip SAMA5

The recovery mode used here is a program called SAM-BA Monitor. Your sama5
device should have a valid SAM-BA Monitor in its ROM code and the
DISABLE\_MONITOR fuse should **NOT** be set, as this would disable SAM-BA
monitor and prevent recovery. Connect the USB device port to your host PC. This
should create a serial port on the host system. If not, you may have to close
some boot control jumpers/switches to make sure the SoC is not booting from one
of the board's NVMs.

## NXP i.MX

Connect your host PC to the USB OTG port and power your board. The SoC’s boot
fuses should be set so that it falls back to Serial Downloader mode. This can be
achieved by setting them to boot from an external memory and removing any
external boot media. An NXP Semiconductors USB device should appear on the host
system.

## Allwinner SUNXI

The secure boot fuse must **NOT** be burned! Snagrecover requires the SoC to be
booting from FEL mode. On some models, this will happen automatically. On
others, further setup is required. We recommend that you check your board
vendor's user guide.

## TI AM62x / TI AM62Ax / TI AM62Px

Connect the USB device port to your host PC. Power your board, making sure that
the SoC is configured to boot from DFU. The SoC can also fall back to DFU if all
other boot options fail. A few seconds after powering the board, a USB DFU
device should appear on your host system. This can take several seconds.

## The special case of TI AM335x devices

During initialization, the ROM code will set up a boot device list and for each
device, will try to perform either a memory boot or a peripheral boot.
Peripheral booting is what interests us for recovering a board. It can be done
over USB, UART or Ethernet. Out of the 3 possible peripheral boot modes,
snagrecover only supports USB mode.

### TI AM335x USB recovery

Connect a USB cable to the port corresponding to the USB0 interface of the SOC.
Make sure that the ROM code is trying to boot from USB. Use your board’s boot
switches and/or other methods to prevent the board from booting from any
non-volatile memories. The host system should detect a new RNDIS Ethernet gadget
which will be registered as a new network interface, such as `ID 0451:6141 Texas
Instruments, Inc. AM335x USB`. Please take care to check that the ROM code has
not booted from any other source!

After registering a network interface with the host system, the board will
periodically send BOOTP boot request  broadcasts. Once the BOOTP exchange is
completed, the board will request a boot file from the TFTP server indicated by
the BOOTP response. The recovery tool performs these exchanges automatically,
but you have to run it in an isolated network namespace. A polling subprocess is
also needed to automatically move the board interface to the special namespace.
We have provided a helper bash script to do this automatically.

**Note:** The new network namespace will be named “snagbootnet”. If you already
have a netns with that name, you should pass a different one to the bash script
using the -n flag and to snagrecover using the --netns option.

Run the provided bash script to setup the network namespace and start the
polling subprocess.

```bash
$ snagrecover --am335x-setup > am335x_usb_setup.sh
$ chmod a+x am335x_usb_setup.sh
$ sudo ./am335x_usb_setup.sh
```

**Note:** If you have changed the ROM code's or SPL's USB VID/PID, you have to
pass the new values to the script using the -s and -r args.

At this point, we recommend that you change your shell prompt, so you do not
forget to log out of the special shell after recovery.

Reset the board and run ip addr. Check that the board interface appears using
`ip link`. Then, run the recovery tool as you would normally (see [running
snagrecover](snagrecover.md)), eg for the Beagle Bone Black:

```bash
snagrecover -s am3358 -f src/snagrecover/templates/am335x-beaglebone-black.yaml
```

Once the recovery is done, exit the recovery shell. This will clean up the
network namespace and udev rules. You can also run:

```bash
sudo am335x_usb_setup.sh -c
```

**Note:** If for some reason, the am335x_usb_setup.sh script exits without
cleaning up the network namespace and polling subprocess, you can run the above
command to remove them.
