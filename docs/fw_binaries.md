# Firmware binaries required by snagrecover

Snagrecover requires firmware binaries to successfully recover the board. Each
recovery flow has a set of named firmware that it will attempt to write to the
board and run, in a predetermined order. Configurations for these firmware have
to be passed to the recovery tool via the --firmware or --firmware-file
argument. You can pass these options multiple times if necessary. This part of
the documentation explains what firmware and configuration options are needed
for each SoC family.

A firmware configuration file for snagrecover has the following structure:

```
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

The firmwares needed for each SoC family are listed below. Some
[templates](../src/snagrecover/templates) are provided as references. Whatever SoC family you are
using, you will probably want to configure your U-Boot build so that it can
interact with snagflash correctly after recovery (e.g. use DFU, UMS or
fastboot).

**Note:** When configuring U-Boot, you'll probably want to disable autoboot,
unless you're setting up a automated recovery+boot process.

## For ST STM32MP1 devices 

[example](../src/snagrecover/templates/stm32mp1-stm32mp157f-dk2.yaml)

These instructions are for setting up a trusted boot using TF-A as a first
stage and U-Boot as a second stage. Apparently using SPL as a first stage
doesn’t work very well on these boards. We haven’t tested the recovery tool on
a STM32MP13 board, the build process seems to be slightly different for those
so you might have to refer to external docs if you want to build binaries to
try and use the tool with one of these boards.

**fip:** Contains at least U-Boot with an stm32 image header. Usually the
raw U-Boot image needs to be generated first, then packaged by a
trusted-arm-firmware build. If the autoboot feature is enabled, then U-Boot will
enter DFU mode.

configuration:
 * path

**tf-a:** Arm-trusted firmware BL2, with an stm32 image header. This should be
built for trusted boot, i.e. using SP_MIN as the trusted firmware. In some
build strategies, you have to pass your U-Boot binary to the tf-a build process

configuration:
 * path

### Example build process:

Download mainline TF-A and U-Boot. In U-Boot:

```bash 
make stm32mp15_defconfig make DEVICE_TREE=<your device tree> 
```

In TF-A, run make <params> all fip where params contains the following:

```bash 
ARCH=aarch32 ARM_ARCH_MAJOR=7 AARCH32_SP=sp_min PLAT=stm32mp1 DTB_FILE_NAME=<your device tree>.dtb BL33_CFG=/path/to/u-boot.dtb BL33=/path/to/u-boot-nodtb.bin STM32MP_USB_PROGRAMMER=1
```

This will generate tf-a-<your device tree>.stm32 which you can pass as tf-a,
and fip.bin which you can pass as u-boot.

## For Microchip SAMA5 devices

[example](../src/snagrecover/templates/sama5-sama5d2xplained.yaml)

**lowlevel:** SAM-BA ISP applet used to initialize the clock tree. You can
obtain SAM-BA ISP applets by downloading the source code for SAM-BA ISP from
Microchip’s website. In the downloaded folder, go to qml/SAMBA/Device/[board
model]/applets. If the binaries aren’t there, check that your board is
supported by the recovery tool.

configuration:
 * path: this binary can be obtained from the SAM-BA ISP sources e.g.
 	applet-lowlevel\_sama5d3-generic\_sram.bin
 * console\_instance: board-specific
 * console\_ioset: board-specific

**extram:** SAM-BA ISP applet used to initialize external RAM.

configuration:
 * path: this binary can be obtained from the SAM-BA ISP sources e.g.
 	applet-extram\_sama5d3-generic\_sram.bin
 * preset: board-specific, check your DDR model, e.g. "DDR2\_MT47H128M16:Preset
 	2 (2 x MT47H128M16)" supported presets are listed in
 	recovery/firmware/samba\_applet.py
 * console\_instance: board-specific
 * console\_ioset: board-specific

**u-boot:** U-Boot binary. Make sure that “MMU-based Paged Memory Management
Support” and “Skip the calls to certain low level initialization functions” are
disabled.

configuration:
 * path
 * address: check the value of CONFIG\_TEXT\_BASE in your  u-boot configuration

## For NXP i.MX SoCs that use the SDPS protocol: imx28,imx93,imx8{qxp,qm,dxl,15,65}

[example](../src/snagrecover/templates/imx28-evk.yaml)

**u-boot-sdps:** Contains at least U-Boot and other SoC-specific components. For
i.MX28, this can be generated with the u-boot.sb target in U-Boot.

configuration:
 * path

## For NXP i.MX6/7 SoCs

### Option1: Use dcd to initialize the external RAM

[example](../src/snagrecover/templates/imx7-colibri-imx7d.yaml)

**u-boot-with-dcd:** For some boards, you can build the flash.bin target in
U-Boot which contains an IVT header + a DCD + U-Boot proper. The DCD will be
used to initialize external RAM and U-Boot proper will be installed immediately
after this.

configuration:
 * path

### Option 2: Use SPL to initialize the external RAM

[example](../src/snagrecover/templates/var-som-mx6.yaml)

**SPL:** IVT header + U-BOOT SPL to be loaded in OCRAM. You can
generate this by compiling the SPL target in U-Boot.

configuration:
 * path

**u-boot:** IVT header + U-BOOT proper to be loaded in external RAM.
You can generate this by compiling the u-boot.imx target in U-Boot.

configuration:
 * path

## For NXP i.MX8 devices

[example](../src/snagrecover/templates/imx8-dart-mx8m-mini.yaml)

iMX8 boards require more complicated firmware binaries, since U-BOOT cannot
boot them on its own. The process for generating the bootloader firmware is
highly vendor and board specific. We recommend that you follow your board
vendor’s tutorial to generate a recovery sd card image , then dump the start of
this sd card image (up to the start of the first partition) into a flash.bin 
file.

**flash-bin:** This should contain at least: IVT header + SPL + ddr firmware
+ ATF + u-boot. The precise image structure depends on the board and build
process. The recovery tool will download the IVT header + SPL + ddr
firmware part of the image to OCRAM and run it, then download the ATF+u-boot
part to external RAM. Normally, SPL should support the SDPV (instead of SDPU)
protocol, which makes it capable of autofinding u-boot proper in the image we
send.

configuration:
 * path

## For TI AM335x devices

[example](../src/snagrecover/templates/am335-beaglebone-black.yaml)

**spl:** First stage bootloader. Build the spl/u-boot-spl.bin target for your
board in U-Boot mainline. spl/u-boot-spl.bin is the required binary. If
recovering via UART, SPL should be built with CONFIG\_SPL\_YMODEM_SUPPORT
enabled.

configuration:
 * path

**u-boot:** Second stage bootloader. Build the u-boot.img target in U-Boot.

configuration:
 * path

**Warning:** If recovering via usb, check the config\_sys\_bootfile\_prefix option in
your spl configuration. it could impose constraints on how you name your u-boot
binary file.

## For Allwinner SUNXI devices

### Option 1: Single SPL+U-Boot binary
[example](../src/snagrecover/templates/sunxi-orangepi-pc.yaml)

**u-boot-with-spl:** Described in sunxi-u-boot.dtsi. For arm64 SOCs, this
contains: sunxi-spl.bin + nonfit or FIT container with u-boot-nodtb,bl31,
[scp.bin], @fdt-SEQ. For arm32 SOCs: sunxi-spl.bin + nonfit or FIT container
with u-boot-img. This binary usually corresponds to the
u-boot-sunxi-with-spl.bin file generated by a U-Boot build.

### Option 2: Separate SPL and U-Boot binaries

**spl:** SPL with an eGON header, you can typically use sunxi-spl.bin for this

configuration:
 * path

**u-boot:** Same as the u-boot-with-spl firmware from option 1 but without the
SPL part, you can typically use u-boot.img for this

configuration:
 * path

## For TI AM62x devices

[example](../src/snagrecover/templates/am625-beagle-play.yaml)

**Warning:** Please refer to 
[this documentation](https://u-boot.readthedocs.io/en/latest/board/ti/am62x_sk.html)
for building the required images. When building the U-Boot SPL image for R5,
please make sure that the resulting SPL supports Booting from DFU! The
defconfig indicated by the linked documentation does not guarantee this!

AM62 SoCs require multiple complex firmware images to boot. 

**tiboot3:** X.509 certificate container with U-Boot SPL for R5, TIFS, and a FIT
container with device tree blobs.

configuration:
 * path

**u-boot:** FIT container with U-Boot proper for A53 and device tree blobs

configuration:
 * path

**tispl:** FIT container with ATF FOR A53, OPTEE (not necessary for recovery),
DM firmware, U-Boot SPL for A53 and device tree blobs

configuration:
 * path

