# Recovering

## Setting up your device for recovery

Your board should be properly set up to enter the SoC vendor’s specific recovery
mode (more vendor-specific details below). This usually involves setting some
boot fuses, removing some external boot media and/or other board-specific
actions. Referring to your board's user guide can help you find out
what you need to do here.

The board should be connected to your host PC via USB (except for the special
case of AM335x UART recovery). The specific USB port to use is board-dependent,
it is usually the OTG port. We also strongly recommend that you open a UART
connection to the board so that you can monitor the recovery process as it
unfolds. On STM32MP1 discovery kits, the default UART is often wired to the
ST-LINK port.

Once your board is in recovery mode, a new USB device should appear on your host
system. This is the device that snagrecover will communicate with. Below are
some vendor-specific hints for setting up your board for recovery.

### ST STM32MP1

The recovery mode used here is DFU. Connect the USB DRP port to your host PC.
Power your board, making sure that the boot fuses are configured to boot from
DFU. The SoC can also fall back to DFU if all other boot options fail. At this
point, a USB DFU device should appear on your host system.

### Microchip SAMA5

The recovery mode used here is a program called SAM-BA Monitor. Your sama5
device should have a valid SAM-BA Monitor in its ROM code and the
DISABLE\_MONITOR fuse should **NOT** be set, as this would disable SAM-BA
monitor and prevent recovery. Connect the USB device port to your host PC. This
should create a serial port on the host system. If not, you may have to close
some boot control jumpers/switches to make sure the SoC is not booting from one
of the board's NVMs.

### NXP i.MX

Connect your host PC to the USB OTG port and power your board. The SoC’s boot
fuses should be set so that it falls back to Serial Downloader mode. This can be
achieved by setting them to boot from an external memory and removing any
external boot media. An NXP Semiconductors USB device should appear on the host
system.

### Allwinner SUNXI

The secure boot fuse must **NOT** be burned! Snagrecover requires the SoC to be
booting from FEL mode. On some models, this will happen automatically. On
others, further setup is required. We recommend that you check your board
vendor's user guide.

### TI AM62x/AM62Ax/AM62Px/AM62Lx/AM62Dx/AM64x/AM654x

Connect the USB device port to your host PC. Power your board, making sure that
the SoC is configured to boot from DFU. The SoC can also fall back to DFU if all
other boot options fail. A few seconds after powering the board, a USB DFU
device should appear on your host system. This can take several seconds.

### Intel Keembay

Intel Keembay boards have a recovery mode that can be accessed by setting
the boot switch to the recovery position. The exact location and configuration
of the boot switch varies by board model, so refer to your board's documentation
for specific instructions.

1. Power off the board
2. Set the boot switch to the recovery position
3. Connect the USB cable to the recovery port
4. Power on the board

After powering on, the board should be detected as a USB device
with VID:PID `8087:0b39`.

### The special case of TI AM335x devices

During initialization, the ROM code will set up a boot device list and for each
device, will try to perform either a memory boot or a peripheral boot.
Peripheral booting is what interests us for recovering a board. It can be done
over USB, UART or Ethernet. Out of the 3 possible peripheral boot modes,
snagrecover supports UART mode, and USB mode.  UART is much simpler to setup but
is very slow and for this reason is only supported by snagrecover, not
snagflash.

#### TI AM335x UART recovery

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

#### TI AM335x USB recovery

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

### Broadcom BCM

Set up your board in "USB device boot mode", connect the board to the USB device port, power the board if necessary. A new USB device should appear on your host system.

### AMLogic

Set up your board in "USB device boot mode", connect the board to the USB device port, power the board if necessary. A new USB device should appear on your host system.
See U-Boot AMLogic boards [documentation](https://docs.u-boot.org/en/latest/board/amlogic/boot-flow.html) for more information.

**Note:** Some boards (eg LibreComputer AML-S905X-CC "Le Potato") requires you to use a, non standard, USB A to A (male to male) cable to enable the USB recovery.
This USB cable needs to power up the board, ie it needs to have its internal VBUS cable connected, which is not always the case if you made it yourself. After connecting the USB A to A cable and properly setting up boot switches and/or buttons, a new AMLogic USB device should be enumerated. After that, you might need to provide additional power by connecting another MicroUSB cable to the board.

**DISCLAIMER: USB A to A type of cable can seriously harm your hardware, use it at your own risk.**

## Preparing recovery firmware

Snagrecover requires firmware binaries to successfully recover the board. Each
recovery flow has a set of named firmware that it will attempt to write to the
board and run, in a predetermined order. Configurations for these firmware have
to be passed to the recovery tool via the --firmware or --firmware-file
argument. You can pass these options multiple times if necessary. This section
explains what firmware and configuration options are needed for each SoC family.

A firmware configuration file for snagrecover has the following structure:

```
paths-relative-to: THIS_FILE
fw_1:
  path: /path/to/fw_1
  option1: value1
fw_2:
  path: /path/to/fw_2
  option_a: value_a
  option_b: value_b
fw_3:
  path: /path/to/fw_3
  option3: value3
```

The firmware needed for each SoC family are listed below. Some
[templates](../src/snagrecover/templates) are provided for reference. Whichever
type of SoC you are using, you will probably want to configure your U-Boot build
so that it can interact with snagflash correctly after recovery (e.g. use DFU,
UMS or fastboot).

The key `paths-relative-to` is optional and indicates that paths to images are
relative to a specific path, either:

- `CWD`: the current working directory, e.g the default behaviour
- `THIS_FILE`: the directory containing the current configuration file
- a path to a directory.

If `THIS_FILE` or a path is specified, snagrecover will effectively join this
path and the images paths. `CWD` is actually a no-op and will keep the default
behaviour.
Absolute paths to images will not be modified by this option.

This is useful when distributing the configuration file alongside images.

### General tips on configuring U-Boot

In many cases, in can be necessary to build the recovery U-Boot yourself e.g.
when existing images do not work or when specific features are needed to
interact with snagflash. Here are a few SoC-independent tips that can be helpful
when configuring U-Boot.

- Set `CONFIG_AUTOBOOT=n` if you don't want U-Boot to try and boot automatically
  after recovery e.g. if you want to get a U-Boot command line.
- Sometimes U-Boot will try to load an environment from some memory device,
  which can cause issues. Setting `CONFIG_ENV_IS_NOWHERE=y` can help avoid this.
- If you want to use snagflash after recovery, make sure to write down the
  `CONFIG_USB_GADGET_VENDOR/PRODUCT_NUM` values so that you can
  pass them to snagflash and setup proper udev rules so that you have rw access
  rights to the corresponding USB device. See [snagflash docs](snagflash.md)
  for more details.

### For ST STM32MP1/2 devices

[example](https://github.com/bootlin/snagboot/blob/main/src/snagrecover/templates/stm32mp1-stm32mp157f-dk2.yaml)

TF-A is used as the first stage and U-Boot as the second stage.

**fip:** Contains at least U-Boot with an stm32 image header. Usually the
raw U-Boot image needs to be generated first, then packaged by a
trusted-arm-firmware build. If the autoboot feature is enabled, then U-Boot will
enter DFU mode after recovery.

configuration:
 * path

**tf-a:** Arm-trusted firmware BL2, with an stm32 image header. In typical
build strategies, you have to pass your U-Boot binary to the tf-a build
process. For the secure firmware, use SP_MIN if available.
OPTEE can also work.

configuration:
 * path

#### For STM32MP2 only:

**fip-ddr:** Contains the DDR initialization firmware.

configuration:
 * path

#### Example build process for an stm32mp15-based board

Download upstream TF-A and U-Boot. In U-Boot:

```bash
make stm32mp15_defconfig
make DEVICE_TREE=<your device tree>
```

In TF-A, run `make \<params\> all fip` where `params` contains the following:

```bash
ARCH=aarch32 ARM_ARCH_MAJOR=7 AARCH32_SP=sp_min PLAT=stm32mp1 DTB_FILE_NAME=<your device tree>.dtb BL33_CFG=/path/to/u-boot.dtb BL33=/path/to/u-boot-nodtb.bin STM32MP_USB_PROGRAMMER=1
```

This will generate tf-a-\<your device tree\>.stm32 and fip.bin, which you can
pass to snagrecover.

### For Microchip SAMA5 devices

[example](https://github.com/bootlin/snagboot/blob/main/src/snagrecover/templates/sama5-sama5d2xplained.yaml)

**lowlevel:** SAM-BA applet used to initialize the clock tree. You can
obtain SAM-BA applets by downloading the source code for SAM-BA ISP from
Microchip’s website. In the downloaded folder, go to qml/SAMBA/Device/[board
model]/applets. If the binaries aren’t there, check that your board is
supported by the recovery tool.

configuration:
 * path: the binary can be obtained from the SAM-BA ISP sources e.g.
 	applet-lowlevel\_sama5d3-generic\_sram.bin
 * console\_instance: board-specific
 * console\_ioset: board-specific

**extram:** SAM-BA ISP applet used to initialize external RAM.

configuration:
 * path: the binary can be obtained from the SAM-BA ISP sources e.g.
 	applet-extram\_sama5d3-generic\_sram.bin
 * preset: board-specific, check your DDR model, e.g. "DDR2\_MT47H128M16:Preset
 	2 (2 x MT47H128M16)" supported presets are listed in
 	snagrecover/firmware/samba\_applet.py
 * console\_instance: board-specific
 * console\_ioset: board-specific

**u-boot:** U-Boot binary. Make sure that `CONFIG_SKIP_LOWLEVEL_INIT`
 and `CONFIG_SYS_ARM_MMU` are both disabled!

configuration:
 * path
 * address: check the value of CONFIG\_TEXT\_BASE in your  u-boot configuration

### For NXP i.MX6/7 SoCs

#### Option1: Use dcd to initialize the external RAM

[example](https://github.com/bootlin/snagboot/blob/main/src/snagrecover/templates/imx7-colibri-imx7d.yaml)

**u-boot-with-dcd:** For some boards, you can build the `u-boot.imx` target in
U-Boot which contains an IVT header + a DCD + U-Boot proper. The DCD will be
used to initialize external RAM and U-Boot proper will be installed immediately
after this.

configuration:
 * path

#### Option 2: Use SPL to initialize the external RAM

[example](https://github.com/bootlin/snagboot/blob/main/src/snagrecover/templates/var-som-mx6.yaml)

**SPL:** IVT header + U-BOOT SPL to be loaded in OCRAM. You can generate this
by compiling the SPL target in U-Boot. SPL should support SDP. You should not
modify the default USB gadget VID/PID values, as they are used by snagrecover
to match protocols.

configuration:
 * path

**u-boot:** IVT header + U-BOOT proper to be loaded in external RAM.
You can generate this by compiling the u-boot.imx target in U-Boot.

configuration:
 * path

### For NXP i.MX8, i.MX28 , i.MX91 and i.MX93 devices

[example](https://github.com/bootlin/snagboot/blob/main/src/snagrecover/templates/imx8-dart-mx8m-mini.yaml)

The process for generating the bootloader firmware for i.MX8 SoCs is highly
vendor and board specific. We recommend that you follow your board vendor’s
tutorial to generate a recovery sd card image , then dump the start of this sd
card image (up to the start of the first partition) into a flash.bin file. For
i.MX28 SoCs, the required binary can be generated with the u-boot.sb target in
U-Boot.

**flash-bin:** This should contain at least spl and u-boot. The precise image
structure depends on the SoC and build process.

configuration:
 * path

### For TI AM335x devices

[example](https://github.com/bootlin/snagboot/blob/main/src/snagrecover/templates/am335x-beaglebone-black.yaml)

**spl:** First stage bootloader. Build the spl/u-boot-spl.bin target for your
board in U-Boot mainline. If recovering via UART, SPL should be built with
CONFIG\_SPL\_YMODEM_SUPPORT enabled. If recovering via USB, the USB Ethernet
gadget should be enabled, which implies the following options:

```bash
CONFIG\_SPL\_NET\_SUPPORT=y
CONFIG\_SPL\_NET\_VCI\_STRING="AM335x U-Boot SPL"
CONFIG\_SPL\_USB\_GADGET\_SUPPORT=y
CONFIG\_SPL\_USB\_ETHER=y
# CONFIG\_SPL\_USB\_SDP\_SUPPORT is not set
```

configuration:
 * path

**u-boot:** Second stage bootloader. Build the u-boot.img target in U-Boot.

configuration:
 * path

**Warning:** If recovering via usb, check the config\_sys\_bootfile\_prefix option in
your spl configuration. it could impose constraints on how you name your u-boot
binary file.

### For Allwinner SUNXI devices

#### Option 1: Single SPL+U-Boot binary

[example](https://github.com/bootlin/snagboot/blob/main/src/snagrecover/templates/sunxi-orangepi-pc.yaml)

**u-boot-with-spl:** Described in sunxi-u-boot.dtsi. For arm64 SOCs, this
contains: sunxi-spl.bin + nonfit or FIT container with u-boot-nodtb,bl31,
[scp.bin], @fdt-SEQ. For arm32 SOCs: sunxi-spl.bin + nonfit or FIT container
with u-boot-img. This binary usually corresponds to the
u-boot-sunxi-with-spl.bin file generated by a U-Boot build.

#### Option 2: Separate SPL and U-Boot binaries

**spl:** SPL with an eGON header, you can typically use sunxi-spl.bin for this

configuration:
 * path

**u-boot:** Same as the u-boot-with-spl firmware from option 1 but without the
SPL part, you can typically use u-boot.img for this

configuration:
 * path

### For TI AM62x/AM62Ax/AM62Px/AM62Lx/AM62Dx/AM64x/AM654x devices

[example](https://github.com/bootlin/snagboot/blob/main/src/snagrecover/templates/am625-beagle-play.yaml)

Instructions for building the required images can be found in various locations
depending on your SoC and board model. In general, your board vendor's
documentation should be the first place to check. For evaluation kits, you can
either check the [U-Boot documentation](https://u-boot.readthedocs.io/en/latest/board/ti/)
or the TI SDK documentation for your SoC. When building tiboot3, please make
sure that your configuration supports booting from DFU.

*Note for AM654x SoCs:* When building tiboot3 and tispl binaries, please check
that the device trees for your board have USB components enabled in both SPL
boot stages (r5 and a53).

The following images are required for all AM6xx SoCs:

**tiboot3:** X.509 certificate container with U-Boot SPL for R5, TIFS, and a FIT
container with device tree blobs. SPL should support DFU. For AM62Lx, instead of
U-Boot SPL for R5, it contains Pre-BL and there is no fit container with device
tree blobs.

configuration:
 * path

**u-boot:** FIT container with U-Boot proper for A53 and device tree blobs

configuration:
 * path

**tispl:** FIT container with ATF FOR A53, OPTEE (not necessary for recovery),
DM firmware, U-Boot SPL for A53 and device tree blobs. For AM62Lx, X.509 certificate
container with ATF for A53, OPTEE, U-Boot SPL for A53, device tree blobs and
TIFS.

configuration:
 * path

AM654x SoCs require an additional "sysfw" binary:

**sysfw:** FIT container with system configuration data. Usually generated as a
tiboot3 build artifact, named "sysfw.itb".

configuration:
 * path

### For Xilinx ZynqMP devices

[example](https://github.com/bootlin/snagboot/blob/main/src/snagrecover/templates/zynqmp-generic.yaml)

Detailed instructions for building the required boot images can be found in the
[Xilinx documentation](https://xilinx.github.io/Embedded-Design-Tutorials), in
the "boot-and-configuration" section for ZynqMP SoCs. Please note that the
first boot image containing only the FSBL and PMUFW should not be required, as
Snagboot is capable of extracting a working first-stage boot image from the
full boot image.

The following images are required for all ZynqMP SoCs:

**boot:** Xilinx ZynqMP boot image containing the Xilinx FSBL, PMUFW, ATF,
control DT and U-Boot proper. The FSBL should be compiled with USB support
enabled.

configuration:
 * path

**fsbl:** (optional) Xilinx ZynqMP boot image containing the Xilinx FSBL and
PMUFW. This is optional, and should only be provided if Snagboot fails to
extract the FSBL and PMUFW from the complete boot image.

configuration:
 * path

### For Intel Keembay devices

[example](https://github.com/bootlin/snagboot/blob/main/src/snagrecover/templates/keembay-generic.yaml)

Intel Keembay boards use a Firmware Image Package (FIP) to boot the board
in recovery mode.

**fip:** Firmware Image Package containing the ATF and u-boot firmware
necessary to initialize the board.

configuration:
 * path: Path to the FIP file. The filename should match the board model:
   - For EVM boards: `fip-evm.bin`
   - For M2 boards: `fip-m2.bin`
   - For HDDL2 boards: `fip-hddl2.bin`

### For Broadcom BCM devices

[example](https://github.com/bootlin/snagboot/blob/main/src/snagrecover/templates/bcm2711.yaml)

In the case of Raspberry Pi, most firmwares can be found in their GitHub repositories [github.com/raspberrypi](https://github.com/raspberrypi/)
along with a [genimage.cfg](https://github.com/raspberrypi/buildroot/blob/mass-storage-gadget64/board/raspberrypi64-mass-storage-gadget/genimage.cfg) file wich can be taken as a reference for building the DOS partition image using the [genimage](https://github.com/pengutronix/genimage) tool.


**bootfiles:** tar archive containing the FSBL and some of the firmwares required by the FSBL to boot U-Boot. Firmwares can optionally be located inside of a subfolder, named 2711|2712 for bcm2711|bcm2712 respectively.
 - bootcode\<n>.bin: the FSBL, which acts as USB client requesting firmware to load. For bootcode, \<n> is 4|5 for bcm2711|bcm2712 respectively.
 - mcb.bin: RAM init
 - memsys\<nn>.bin: more RAM inits
 - bootmain: the loader for the disk image

In the case of Raspberry Pi, a ready made "bootfiles" firmware can be found [here](https://github.com/raspberrypi/usbboot/commit/798ea2ef893bfa11fe3dba0e088cbc9b862184a1).

configuration:
 * path


**boot:** DOS partition table image with the first partition bootable with a FAT filesystem containing:
 - \<board>.dtb: the compiled device tree, loaded in memory by `start<n>.elf` and used by U-Boot
 - \<board>.dtbo: the device tree overlays
 - config.txt: a file which specifies to `start<n>.elf` to boot U-Boot proper instead of Linux (`kernel=u-boot.bin`) and to start in 64 bits mode (`arm_64bit=1`)
 - cmdline.txt: linux kernel command line, as we don't boot linux you can keep it empty.
 - start\<n>.elf: the SSBL
 - fixup\<n>.dat: the SSBL linker file (found in pair with start\<n>.elf)
 - U-Boot proper (`u-boot.bin`)

 This DOS partition image can be generated using the `genimage` tool. In the case of Raspberry Pi, [ready made images already exists](https://github.com/raspberrypi/usbboot/blob/master/mass-storage-gadget64/boot.img), however they do not contain a U-Boot but a Linux. **If you use them, you must provide U-Boot separately using the "u-boot" firmware section**. In that case, Snagrecover will create a temporary copy of it and do what is necessary to boot U-Boot instead of Linux.

configuration:
 * path

**config:** config text file with parameter to setup the board to boot from RAM (`boot_ramdisk=1`)

configuration:
 * path

**u-boot:** (optional) U-Boot proper. You can use this option if you want Snagrecover to modify **boot** firmware to add U-Boot to it (this is mandatory if you are using a ready-made **boot** firmware from RPi). If your **boot** firmware already contains a U-Boot, you can skip this option.

configuration:
  * path

### For AMLogic devices

There are two protocols of USB recovery for AMLogic SoCs :
1. Series: G12A (eg S905D2), G12B (eg A311D), SM1 (eg S905D3)
2. Series: GXL (eg S905D), GXM (eg S912), GXBB (eg S905), AXG (eg A113D)

These two recoveries uses different firmwares.

#### 1. G12x and SM1 series

[example](https://github.com/bootlin/snagboot/blob/main/src/snagrecover/templates/amlogic_G12x_SM1.yaml)

**u-boot-fip:** Firmware Image Package (FIP) containing both the BL2 bootloader and U-Boot proper. For some boards you can use the tool [amlogic-boot-fip](https://github.com/LibreELEC/amlogic-boot-fip) to generate it, otherwise, refer to your board vendor..

configuration:
  * path
  * bl2-load-addr (optional): load address for `BL2`, if not provided a default value is used.


#### 2. GXx and AXG series

[example](https://github.com/bootlin/snagboot/blob/main/src/snagrecover/templates/amlogic_GXx_AXG.yaml)

**bl2:** BL2 bootloader from AMLogic, seems to be based on TFA (no source available). For some boards you can use the tool [amlogic-boot-fip](https://github.com/LibreELEC/amlogic-boot-fip) to generate it, otherwise, refer to your board vendor.

configuration:
  * path

**u-boot:** signed U-Boot proper. For some boards you can use the tool [amlogic-boot-fip](https://github.com/LibreELEC/amlogic-boot-fip) to generate it, otherwise, refer to your board vendor.

configuration:
  * path
  * load-addr (optional): load address of U-Boot, if not provided a default value is used.

## Running snagrecover

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

