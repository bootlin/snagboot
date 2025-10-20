# Snagboot

Snagboot intends to be an open-source and generic replacement to the
vendor-specific, sometimes proprietary, tools used to recover and/or reflash
embedded platforms. Examples of such tools include STM32CubeProgrammer, SAM-BA
ISP, UUU, and sunxi-fel. Snagboot is made of two separate parts:

- **snagrecover** uses vendor-specific ROM code mechanisms to initialize
  external RAM and run U-Boot, without modifying any non-volatile
  memories.
- **snagflash** communicates with U-Boot to flash system images to non-volatile
  memories, using either DFU, UMS or Fastboot.

<p align="center">
  <img src="docs/tutorial_snagrecover.gif" alt="animated" />
</p>

Snagboot currently supports the following families of System-On-Chips (SoCs):

 * [Allwinner sunxi](https://linux-sunxi.org/) A10, A10S, A13, A20, A23, A31, A33, A63, A64, A80, A83T, AF1C100S, H2+, R8, R16, R40, R329, R528, T113-S3, V3S, V5S, V536, V831, V853
 * [STMicroelectronics](http://st.com/) [STM32MP1](https://www.st.com/en/microcontrollers-microprocessors/stm32mp1-series.html) and [STM32MP2](https://www.st.com/en/microcontrollers-microprocessors/stm32mp2-series.html)
 * [Microchip](https://www.microchip.com/) [SAMA5](https://www.microchip.com/en-us/products/microprocessors/32-bit-mpus/sama5)
 * [NXP](https://www.nxp.com/) [i.MX6](https://www.nxp.com/products/processors-and-microcontrollers/arm-processors/i-mx-applications-processors/i-mx-6-processors:IMX6X_SERIES), [i.MX7](https://www.nxp.com/products/processors-and-microcontrollers/arm-processors/i-mx-applications-processors/i-mx-7-processors:IMX7-SERIES), [i.MX8](https://www.nxp.com/products/processors-and-microcontrollers/arm-processors/i-mx-applications-processors/i-mx-8-applications-processors:IMX8-SERIES), [i.MX93](https://www.nxp.com/products/processors-and-microcontrollers/arm-processors/i-mx-applications-processors/i-mx-9-processors/i-mx-93-applications-processor-family-arm-cortex-a55-ml-acceleration-power-efficient-mpu:i.MX93)
 * [Texas Instruments](https://www.ti.com) [AM335x](https://www.ti.com/product/AM3358), [AM62x](https://www.ti.com/product/AM625), [AM62Lx](https://www.ti.com/product/AM62L), [AM64x](https://www.ti.com/product/AM6442), [AM654x](https://www.ti.com/product/AM6548)
 * [Xilinx/AMD](https://www.amd.com/) [Zynq UltraScale+ MPSoC](https://www.amd.com/en/products/adaptive-socs-and-fpgas/soc/zynq-ultrascale-plus-mpsoc.html)
 * [Intel](https://www.intel.com/) Keembay
 * [Broadcom](https://www.broadcom.com/) BCM2711 and BCM2712, used in [Raspberry Pi 4 & 5](https://www.raspberrypi.com/documentation/computers/processors.html)
 * [AMLogic](https://www.amlogic.com/#Products) series: G12A (eg S905D2), G12B (eg A311D), SM1 (eg S905D3) and series: GXL (eg S905D), GXM (eg S912), GXBB (eg S905), AXG (eg A113D)


Please check [supported_socs.yaml](https://github.com/bootlin/snagboot/blob/main/src/snagrecover/supported_socs.yaml)
or run `snagrecover --list-socs` for a more precise list of supported SoCs.

## Installation on Linux

System requirements:

 * libusb 1.x, libusb 0.1.x or OpenUSB
 * The ensurepip Python package. On Debian, you can install the
   python[your python version]-venv package

Snagboot is available on pip: `python3 -m pip install --user snagboot`.

This package provides two CLI tools:

```bash
$ snagrecover -h
$ snagflash -h
```

Installing the gui variant: `python3 -m pip install --user snagboot[gui]`, provides the additional "snagfactory" command.

You also need to install udev rules so that snagrecover has read and write
access to the USB devices exposed by the SoCs.

```bash
$ snagrecover --udev > 50-snagboot.rules
$ sudo cp 50-snagboot.rules /etc/udev/rules.d/
$ sudo udevadm control --reload-rules
$ sudo udevadm trigger
```

These rules work by adding the "uaccess" tag to the relevant USB devices.
Systemd will then add an ACL to give access to currently logged in users. More
info
[here](https://enotty.pipebreaker.pl/2012/05/23/linux-automatic-user-acl-management/).

**Warning:** If your distro does not use systemd, the "uaccess" method could
possibly not work. In this case, make sure to customize the provided udev rules
for your specific system.

Alternatively, Snagboot can be installed as a local Python wheel. An
installation script is provided to automatically build and install the package.

```bash
$ cd snagboot
$ ./install.sh
OR
$ ./install.sh --with-gui
```

There is also an [AUR package](https://aur.archlinux.org/packages/snagboot)
available.

## Installation on Windows 10 or 11

**Note:** Am335x devices are not supported on Windows!

Snagboot requires the "libusb-win32" driver to be bound to any device it
processes **apart from i.MX and SAMA5 devices, which already have their own
s**. This can be done using the Zadig tool which you can obtain [here](https://github.com/pbatard/libwdi/releases/download/v1.5.1/zadig-2.9.exe).


After opening Zadig, select the device entry corresponding to your board's
VID:PID pair.

Then, make sure the "libusb-win32" driver is selected and click on "Install
driver". You should only have to do this once for a given VID:PID pair.

Powershell is required by Snagboot, but it should already be installed.

### Option 1: Using the snagboot installer

An executable installer based on [PyInstaller](https://pyinstaller.org/en/stable/) and [InnoSetup](https://jrsoftware.org/isinfo.php) can be downloaded [from the latest Snagboot release](https://github.com/bootlin/snagboot/releases/latest/download/snagboot_installer_win64.exe).

### Option 2: Using pip

Please install the following software:

- Python 3.8 or later: https://www.python.org/downloads/windows/

- python3-libusb: run `pip install libusb`

After installing Python and libusb, you should add them to your PATH environment variable:

- Open the start menu and type « environment variable » into the search bar
- click on « Edit environment variables for your account »
- In « User variables », click on « Path » then « Edit »
- In the edit window, add four new paths:

```
C:\users\yourusername\appdata\roaming\python\python312\site-packages\libusb\_platform\_windows\x64
C:\users\yourusername\appdata\roaming\python\python312\site-packages\libusb\_platform\_windows\x32
C:\Users\yourusername\AppData\Roaming\Python\Python312\Scripts
```

setuptools: Run `pip install setuptools` then  `pip install snagboot` in powershell

## Usage guide

**Note:** On Linux, running snagboot as root is not recommended and will typically not
work, since it is probably installed for the current user only

To recover and reflash a board using snagboot:

1. Check that your SoC is supported in snagrecover by running: `snagrecover --list-socs`
2. [Setup your board for recovery](https://github.com/bootlin/snagboot/blob/main/docs/board_setup.md)
3. [Build or download the firmware binaries necessary for recovering and reflashing the board.](https://github.com/bootlin/snagboot/blob/main/docs/fw_binaries.md)
4. [Run snagrecover](https://github.com/bootlin/snagboot/blob/main/docs/snagrecover.md) and check that the recovery was a success i.e. that U-Boot is running properly.
5. [Run snagflash](https://github.com/bootlin/snagboot/blob/main/docs/snagflash.md) to reflash the board



For recovering and flashing large batches of boards efficiently, you may use the Snagfactory application which is included in Snagboot. Usage instructions for Snagfactory are available at [snagfactory.md](https://github.com/bootlin/snagboot/blob/main/docs/snagfactory.md). The configuration file syntax for Snagfactory is documented at [snagfactory_config.md](https://github.com/bootlin/snagboot/blob/main/docs/snagfactory_config.md).


Note that Snagfactory support is only included in the "gui" package variant: `pip install snagboot[gui]`

Some [benchmark results](https://github.com/bootlin/snagboot/blob/main/docs/snagfactory_benchmarks.md) are provided in the Snagfactory docs.

If you encounter issues, please take a look at the
[troubleshooting](https://github.com/bootlin/snagboot/blob/main/docs/troubleshooting.md) section.

You can play the snagrecover tutorial in your terminal!

```
sudo apt install asciinema
asciinema play -s=2 docs/tutorial_snagrecover.cast
```

## Contributing

Contributions are welcome! Since Snagboot includes many different recovery
techniques and protocols, we try to keep the code base as structured as
possible. Please consult the [contribution guidelines](https://github.com/bootlin/snagboot/blob/main/CONTRIBUTING.md).

## License

Snagboot is released under the [GNU General Public License version 2](https://github.com/bootlin/snagboot/blob/main/LICENSE)
