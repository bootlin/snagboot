# Installing Snagboot

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

### General notes

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

