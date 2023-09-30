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

The currently supported SoC families are ST STM32MP1, Microchip SAMA5, NXP
i.MX6/7/8, TI AM335x, Allwinner SUNXI and TI AM62x. Please check
[supported_socs.yaml](https://github.com/bootlin/snagboot/blob/main/src/snagrecover/supported_socs.yaml) or run `snagrecover
--list-socs` for a more precise list of supported SoCs.

## Installation

Requirements:

 * One of the libhidapi backends. On Debian, you can install the
   `libhidapi-hidraw0` package or the `libhidapi-libusb0` package.
   On OSX you can install the
   [`hidapi`](https://formulae.brew.sh/formula/hidapi) package.
 * The ensurepip Python package. On Debian, you can install the
   python[your python version]-venv package
 * Swig is required to build pylibfdt. You can simply install the `swig` package on most distros.

Snagboot is available on pip: `python3 -m pip install --user snagboot`.

This package provides two CLI tools:

```bash
$ snagrecover -h
$ snagflash -h
```

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
```

There is also an [AUR package](https://aur.archlinux.org/packages/snagboot)
available.

## Usage guide

**Note:** Running snagboot as root is not recommended and will typically not
work, since it is probably installed for the current user only

To recover and reflash a board using snagboot:

1. Check that your SoC is supported in snagrecover by running: `snagrecover --list-socs`
2. [Setup your board for recovery](https://github.com/bootlin/snagboot/blob/main/docs/board_setup.md)
3. [Build or download the firmware binaries necessary for recovering and reflashing the board.](https://github.com/bootlin/snagboot/blob/main/docs/fw_binaries.md)
4. [Run snagrecover](https://github.com/bootlin/snagboot/blob/main/docs/snagrecover.md) and check that the recovery was a success i.e. that U-Boot is running properly.
5. [Run snagflash](https://github.com/bootlin/snagboot/blob/main/docs/snagflash.md) to reflash the board

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


