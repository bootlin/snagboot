# Firmware binaries required by snagrecover

Snagrecover requires firmware binaries to successfully recover the board. Each
recovery flow has a set of named firmware that it will attempt to write to the
board and run, in a predetermined order. Configurations for these firmware have
to be passed to the recovery tool via the --firmware or --firmware-file
argument. You can pass these options multiple times if necessary. This section
explains what firmware and configuration options are needed for each SoC family.

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

The firmware needed for each SoC family are listed below. Some
[templates](../src/snagrecover/templates) are provided for reference. Whichever
type of SoC you are using, you will probably want to configure your U-Boot build
so that it can interact with snagflash correctly after recovery (e.g. use DFU,
UMS or fastboot).

## General tips on configuring U-Boot

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

## For ST STM32MP1/2 devices

[example](../src/snagrecover/templates/stm32mp1-stm32mp157f-dk2.yaml)

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

### For STM32MP2 only:

**fip-ddr:** Contains the DDR initialization firmware.

configuration:
 * path

### Example build process for an stm32mp15-based board

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

## For Microchip SAMA5 devices

[example](../src/snagrecover/templates/sama5-sama5d2xplained.yaml)

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

## For NXP i.MX6/7 SoCs

### Option1: Use dcd to initialize the external RAM

[example](../src/snagrecover/templates/imx7-colibri-imx7d.yaml)

**u-boot-with-dcd:** For some boards, you can build the `u-boot.imx` target in
U-Boot which contains an IVT header + a DCD + U-Boot proper. The DCD will be
used to initialize external RAM and U-Boot proper will be installed immediately
after this.

configuration:
 * path

### Option 2: Use SPL to initialize the external RAM

[example](../src/snagrecover/templates/var-som-mx6.yaml)

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

## For NXP i.MX8, i.MX28 , i.MX91 and i.MX93 devices

[example](../src/snagrecover/templates/imx8-dart-mx8m-mini.yaml)

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

## For TI AM335x devices

[example](../src/snagrecover/templates/am335x-beaglebone-black.yaml)

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

## For TI AM62x/AM62Ax/AM62Px/AM64x/AM62Lx devices

[example](../src/snagrecover/templates/am625-beagle-play.yaml)

Instructions for building the required images can be found in various locations
depending on your SoC and board model. In general, your board vendor's
documentation should be the first place to check. For evaluation kits, you can
either check the [U-Boot documentation](https://u-boot.readthedocs.io/en/latest/board/ti/)
or the TI SDK documentation for your SoC. When building tiboot3, please make
sure that your configuration supports booting from DFU.

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

## For Xilinx ZynqMP devices

[example](../src/snagrecover/templates/zynqmp-generic.yaml)

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

## For Rockchip devices

Current implementation of support for the Rockchip SoCs, RAMboot and
SPL DFU are supported.

As there's no implementation for Rockchip USB protocol support, it is
possible to push the DDR init files and SPL files from Rockchip but the next
step will fail.

Mainline u-boot does not support boot from RAM and boot from SPL DFU,
it has to be patched.

The patches have been sent to the u-boot mailing list by their authors
and not yet merged. The patches can all be found inside this
[merge request](https://gitlab.collabora.com/hardware-enablement/rockchip-3588/u-boot/-/merge_requests/7).

### Using binary generated by Rockchip's ``boot_merger``

[example](../src/snagrecover/templates/rockchip-merger.yaml)

Snagboot can upload the ``CODE471_OPTION`` and ``CODE472_OPTION`` of a binary
generated with the ``boot_merger`` tool and configuration files from
[Rockchip rkbin](https://github.com/radxa/rkbin/tree/develop-v2024.03/).

In case of u-boot, this would mean to upload the TPL, SPL and then use SPL DFU
to boot u-boot proper (see later section for SPL DFU).

An example configuration for rk3399 would be:
```
[CHIP_NAME]
NAME=RK330C
[VERSION]
MAJOR=1
MINOR=123
[CODE471_OPTION]
NUM=1
Path1=tpl/u-boot-tpl-dtb.bin
Sleep=1
[CODE472_OPTION]
NUM=1
Path1=spl/u-boot-spl-dtb.bin
Sleep=3000
[LOADER_OPTION]
NUM=2
LOADER1=FlashData
LOADER2=FlashBoot
FlashData=spl/u-boot-spl-dtb.bin
FlashBoot=u-boot.itb
[OUTPUT]
PATH=rk3399_uboot.bin
[FLAG]
471_RC4_OFF=false
```

The ``tpl/u-boot-tpl-dtb.bin``, ``spl/u-boot-spl-dtb.bin``, ``u-boot.itb``
files are generated during u-boot's build. Please note has the ``LOADER_OPTION``
is not handled by snagboot.

The configuration parameters are:

**xpl:** Binary blob generated with bootmerger. For instance, here, ``rk3399_uboot.bin``.
 * path: path to the blob

**u-boot-fit:** U-boot FIT image.
 * path: Path to the FIT image. Typically, ``u-boot.itb``


### Boot from Ram

[example](../src/snagrecover/templates/rockchip-ramboot.yaml)

When building u-boot with the previously mentioned patches, u-boot will generate two files:

- ``u-boot-rockchip-usb471.bin``
- ``u-boot-rockchip-usb472.bin``

These are the files needed to boot from RAM.

The configuration parameters are:

**code471:** File to use for maskrom code 0x471.

configuration:
 * path: Path to the ``u-boot-rockchip-usb471.bin`` file
 * delay: Optional delay in milliseconds before loading next binary

**code472:** File to use for maskrom code 0x472.

configuration:
 * path: Path to the ``u-boot-rockchip-usb472.bin`` file


### Boot from SPL DFU

[example](../src/snagrecover/templates/rockchip-spl-dfu.yaml)

To enable u-boot with SPL DFU support in the u-boot configuration, ensure that the
following options are enabled:

```
CONFIG_SPL_DM_USB_GADGET=y
CONFIG_SPL_USB_GADGET=y
CONFIG_SPL_DFU=y
```

On some systems, rebooting the system won't reset the memory content. This means that
booting over DFU after having done a boot from RAM will result in u-boot loading the
u-boot version from the boot from RAM boot and won't try to load u-boot over DFU.

To solve this, disable boot from RAM with:

```
# CONFIG_SPL_RAM_DEVICE is not set
```

The (SPL) USB gadget driver needs to be enabled too.

At the end of the build, the following files will be needed:

- ``mkimage-in-simple-bin.mkimage-u-boot-tpl`` or ``mkimage-in-simple-bin.mkimage-rockchip-tpl``
- ``mkimage-in-simple-bin.mkimage-u-boot-spl``
- ``u-boot.itb``

The configuration parameters are:

**code471:** File to use for maskrom code 0x471.

configuration:
 * path: Path to the TPL file. For instance, ``mkimage-in-simple-bin.mkimage-rockchip-tpl``.
 * delay: Optional delay in milliseconds before loading next binary

**code472:** File to use for maskrom code 0x472.

configuration:
 * path: Path to the  SPL. For instance, ``mkimage-in-simple-bin.mkimage-u-boot-spl``.
 * delay: Optional delay in milliseconds before loading next binary

**u-boot-fit:** U-boot FIT image.
 * path: Path to the FIT image. Typically, ``u-boot.itb``
