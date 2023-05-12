# Setting up your board for recovery

Your board should be properly set up to enter the SoC vendor’s specific recovery
mode (more vendor-specific details below). This usually involves setting some
boot fuses, removing some external boot media and/or other board-specific
actions. Referring to your board's user guide can help you find out
what you need to do here. 

The board should be connected to your host PC via USB (except for the special
case of AM335 UART recovery). The specific USB port to use is board-dependent,
it is usually the OTG port. We also strongly recommend that you open a UART
connection to the board so that you can monitor the recovery process as it
unfolds. On STM32MP15 discovery kits, the default UART is often connected to the
ST-LINK port.

Once your board is in recovery mode, you should see a new USB device appear on
your host system. This is the device that snagrecover will talk to. Below are
some vendor specific hints for setting up your board for recovery.

## ST STM32MP15

The recovery mode used here is DFU. Connect the USB DRP port to your host PC.
Power your board, making sure that the boot fuses are configured to boot from
DFU. The SoC can also fall back to DFU if all other boot options fail. At this
point, you should see a USB DFU device appear on your host system.

## Microchip SAMA5

The recovery mode used here is a program called SAM-BA Monitor. Your sama5
device should have a valid SAM-BA Monitor in its ROM code and the
DISABLE\_MONITOR fuse should **NOT** be set, as this would disable SAM-BA
monitor and prevent recovery. Connect the USB device port to your host PC. This
should create a serial port on the host system. If not, you may have to close
some boot control jumpers/switches to make sure the SoC is not booting from one
of the board NVMs.

## NXP i.MX

The SoC’s boot fuses should be set so that it falls back to serial downloader
mode. This can be achieved by setting them to boot from an external memory and
removing any external boot media. You will see that the SoC entered serial
downloader mode successfully when an NXP Semiconductors USB device appears on
the host system.  Connect your host PC to the USB OTG port.

## Allwinner SUNXI

The secure boot fuse must **NOT** be burned! Snagrecover requires the SoC to be
booting from FEL mode. On some models, this will happen automatically. On
others, further setup is required. We recommend that you check your board's user
guide.

## TI AM62x
The SoC should be put in DFU mode. This can sometimes take a few seconds after
the board has been powered on. Connect the USB device port to your host PC.
Power your board, making sure that the SoC is configured to boot from DFU. The
SoC can also fall back to DFU if all other boot options fail. A few seconds
after powering the board, you should see a USB DFU device appear on your host
system.

## The special case of TI AM335x devices

The ROM code sets up a boot device list and for each device, will try to perform
either a memory boot or a peripheral boot. If it fails, it will loop around and
try another device. Peripheral booting is what interests us for performing a
device recovery. It can be done over USB, UART or Ethernet. Out of the 3
possible peripheral boot modes, snagrecover supports UART mode, and USB mode.
UART is much simpler to setup but is very slow and for this reason is only
supported by snagrecover, not snagflash. 

### TI AM335x UART recovery

Connect a UART to the board, open a serial port and make sure that the ROM code
boots in UART mode. If that’s the case, it should regularly ping the serial
console which will result in the character “C” being displayed.

As an example, here is the procedure for the Beaglebone black wireless board : 

1. remove all connectors and make sure that the sd card slot is empty
2. set up the UART cable on the serial header (GND:J1 RX: J4 TX: J5).
3. hold the S2 button and plug the power cable in. This will change the boot
	sequence so that the board doesn’t try to boot from eMMC.
4. open a serial port and press the reset button. You should get pings in your
	console

### TI AM335x USB recovery

Connect a USB cable to the port corresponding to the USB0 interface of the SOC.
Make sure that the ROM code is trying to boot from USB. Use your board’s boot
switches and/or other methods to prevent the board from booting from any
non-volatile memories. The host system should detect a new RNDIS Ethernet gadget
which will be registered as a new network interface. Please take care to check
that the ROM code has not booted from any other source! 

Once the USB device has appeared, note its device id and vendor id, we will
refer to those as ROMUSB\_PID and ROMUSB\_VID respectively. You should also note
the usb product and vendor ids of the USB ethernet gadget in SPL, which you can
find in your SPL’s configuration. We will refer to those as SPLUSB\_PID and
SPLUSB\_VID.

After registering a network interface with the host system, the board will
periodically send BOOTP boot request  broadcasts. Once the BOOTP exchange is
completed, the board will request a boot file from the TFTP server indicated by
the BOOTP response. The recovery tool performs these exchanges automatically
but, you have to run it in a new and isolated network namespace. A polling
subprocess is also needed to move the board interface to the special
namespace.  We have provided a helper bash script to do this automatically.

**Note:** The new network namespace will be named “recoverynet”. If you already
have a netns with that name, you should pass a different one to the bash script
using the -n flag and to snagrecover using the --netns option.

Run the provided bash script to setup the network namespace and start the
polling subprocess.

```bash 
$ cd snagboot 
$ chmod a+x scripts/am335_usb_setup.sh 

$ sudo scripts/am335_usb_setup.sh -r ROMUSB_VID:ROMUSB_PID \
-s SPLUSB_VID:SPLUSB_PID
```

At this point, we recommend that you change your shell prompt, so you do not 
forget to log out of the new shell after recovery.

Reset the board and run ip addr. Check that the board interface appears. Then,
run the recovery tool as you would normally (see [running
snagrecover](snagrecover)). 

e.g. snagrecover -s am335 -f recovery/templates/beaglebone_black.yaml 

Finally, exit the recovery shell. This will cleanup the network namespace and
udev rules. You can also run:  

```bash 
sudo scripts/am335_usb_setup.sh -c 
```

**Note:** If for some reason, the am335_usb_setup.sh script exits without
cleaning up the network namespace, you can run the above command
to remove them.
