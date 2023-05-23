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
[supported_socs.yaml](src/snagrecover/supported_socs.yaml) or run `snagrecover
--list-socs` for a more precise list of supported SoCs.

## Installation

Requirements:

 * One of the libhidapi backends. On Debian, you can install the
   `libhidapi-hidraw0` package or the `libhidapi-libusb0` package
 * The ensurepip Python package. On Debian, you can install the
   python[your python version]-venv package

Snagboot is available on pip: `python3 -m pip install --user snagboot`.

This package provides two CLI tools:

```bash
$ snagrecover -h
$ snagflash -h
```

You also need to install udev rules so that snagrecover has read and write
access to the USB devices exposed by the SoCs.

```bash
$ snagrecover --udev > 80-snagboot.rules
$ sudo cp 80-snagboot.rules /etc/udev/rules.d/
$ sudo udevadm control --reload-rules
$ sudo udevadm trigger
```

The affected devices will be accessible to the "plugdev" group, so please check
that you are part of this group. You can also modify the udev rules to pick a
more restrictive group if you wish.

**Warning:** The "plugdev" group does not exist on Fedora, please make sure you
modify the udev rules before installing them! You should replace "plugdev" with
any group you wish, e.g. "users". 

Alternatively, Snagboot can be installed as a local Python wheel. An
installation script is provided to automatically build and install the package.

```bash
$ cd snagboot
$ ./install.sh
```

## Usage guide

**Note:** Running snagboot as root is not recommended and will typically not
work, since it is probably installed for the current user only

To recover and reflash a board using snagboot:

1. Check that your SoC is supported in snagrecover by running: `snagrecover --list-socs`
2. [Setup your board for recovery](docs/board_setup.md)
3. [Build or download the firmware binaries necessary for recovering and reflashing the board.](docs/fw_binaries.md)
4. [Run snagrecover](docs/snagrecover.md) and check that the recovery was a success i.e. that U-Boot is running properly.
5. [Run snagflash](docs/snagflash.md) to reflash the board

If you encounter issues, please take a look at the
[troubleshooting](docs/troubleshooting.md) section.

You can play the snagrecover tutorial in your terminal!

```
sudo apt install asciinema
asciinema play -s=2 docs/tutorial_snagrecover.cast
```

## Contributing

Contributions are welcome! Since Snagboot includes many different recovery
techniques and protocols, we try to keep the code base as structured as
possible. Please consult the [contribution guidelines](CONTRIBUTING.md).

## License

Snagboot is released under the [GNU General Public License version 2](LICENSE)


