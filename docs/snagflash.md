# Running snagflash

**Note:** A delay might be required between snagrecover and snagflash, to let
U-Boot start up before connecting to it. If Snagflash is run too early, it will
retry a few times before failing.

Snagflash always requires the "protocol" argument.

 * `-P, --protocol {dfu,ums,fastboot}`
   The protocol to use for flashing

When running snagflash right after snagrecover e.g. in an automated procedure,
make sure that U-Boot will expose the DFU/Fastboot/UMS device by the time
snagflash runs. You might want to configure your recovery U-Boot so that it
autoruns the relevant command. In case snagflash doesn't find the USB port/UMS
device it is looking for, it will retry a few times then fail.

**Warning:** Since the vid:pid pairs of U-Boot USB gadgets can vary wildly, they
are not hardcoded in snagflash. Therefore, you will not necessary have access
rights to these devices. Assuming that your U-Boot config has
`CONFIG_USB_GADGET_VENDOR_NUM=vid` and `CONFIG_USB_GADGET_PRODUCT_NUM=pid`, you
can add the following udev rule to get access:

`SUBSYSTEM=="usb", ATTRS{idVendor}=="vid", ATTRS{idProduct}=="pid", MODE="0660", TAG+="uaccess"`

Alternatively, you can also use bus-ports addresses, which can be more stable.

## DFU mode

In DFU mode, snagflash takes additional arguments :

 * `-p --port [vid:pid | bus-port1.port2.(...)]`
   The USB address of the DFU device exposed by U-Boot
 * `-D --dfu-config  altsetting:path`
   The altsetting and path of a file to download to the board. This should match
   the value specified in dfu\_alt\_info in U-Boot. This flag can be passed
   multiple times, to specify multiple files to download.
 * `--dfu-keep`
   An optional argument to avoid detaching DFU mode after download and keep the mode active
 * `--dfu-detach`
   An optional argument to only request detaching DFU mode
 * `--dfu-reset`
   Reset USB device after download and reboot the board

Example:
```bash
# in U-Boot: setenv dfu_alt_info "mmc=uboot part 0 1"
# in U-Boot: dfu 0 mmc 0
snagflash -P dfu -p 0483:df11 -D 0:binaries/u-boot.stm32
```

For instructions on how to setup DFU in U-Boot, please refer to the [U-Boot
documentation](https://u-boot.readthedocs.io/en/latest/usage/dfu.html).

## UMS mode

Snagflash can copy a file to either a raw block device or a mounted one. When
copying to a raw block device, it uses bmap to speed up transfers.
In UMS mode, snagflash takes two mandatory arguments:

 * `-s --src filepath`
   Source file to copy to destination

Then either one of:

 * `-d --dest path`
   Sets the destination file name for transfers to mounted devices.
 * `-b –blockdev device`
   Sets the block device for transfers to raw block devices.

Make sure that snagflash has the necessary access rights to the target
devices/mount directories. If you are passing a raw block device, make sure that
it is not mounted.

Example:

```bash
# in U-Boot: ums 0 mmc 0
snagflash -P ums -s binaries/u-boot.stm32 -b /dev/sdb1
snagflash -P ums -s binaries/u-boot.stm32 -d /mnt/u-boot.stm32
```

**Note:** If you want a static block device path, you can use the following udev
rules to create symlinks when a certain VID:PID pair is detected: 
- For a parent block device: `SUBSYSTEM=="block", KERNEL!="*[0-9]",
  SUBSYSTEMS=="usb", ATTRS{idVendor}=="...", ATTRS{idProduct}=="...",
  MODE="0660", TAG+="uaccess", SYMLINK+="myblockdev"`
- For a partition device: `SUBSYSTEM=="block", ATTR{partition}=="*",
  SUBSYSTEMS=="usb", ATTRS{idVendor}=="...", ATTRS{idProduct}=="...",
  MODE="0660", TAG+="uaccess", SYMLINK+="myblockdev$attr{partition}"`


## Fastboot mode

In fastboot mode, snagflash takes two additional arguments:

 * `-p --port [vid:pid | bus-port1.port2.(...)]`
   The USB address of the Fastboot device exposed by U-Boot
 * `-f --fastboot_cmd  cmd:args`
   A fastboot command to be sent to U-Boot. The following commands are supported
   by snagflash (which does not mean that they are supported by your U-Boot!) :

```
getvar:<var>
download:<filepath>
erase:<part>
flash:<part>
boot
continue
reboot
reboot-bootloader
powerdown
ucmd:<cmd>
acmd:<cmd>
oem-run:<cmd>
oem-format
oem-partconf:<args>
oem-bootbus:<args>
```

Example:
```bash
# in U-Boot: fastboot usb 0
snagflash -P fastboot -p 0483:0afb -f download:boot.img -f flash:0:1 -f boot
```

For more information on Fastboot commands, see the [fastboot
specification](https://android.googlesource.com/platform/system/core/+/refs/heads/master/fastboot/README.md)
and the [U-Boot
docs](https://elixir.bootlin.com/u-boot/v2023.04/source/doc/android/fastboot.rst).

### Interactive Fastboot mode

Interactive mode provides a set of more complex commands that leverage
basic Fastboot commands to perform various flashing tasks. Interactive
commands can be passed to a CLI prompt with the "-i" flag, and
can also be read from a file using the "-I" option.

Interactive mode flashing commands handle writing files larger than the
Fastboot memory buffer by slicing them up into sections.

The following command set is supported:

```
help_text = """snagflash interactive mode
syntax: <cmd> <arg1> <arg2> ...
commands:

exit : exit snagflash
quit : exit snagflash
help : show this help text
set <var> <value>: set the value of an environment variable
print <var>: print the value of an environment variable
run <fastboot_cmd>: run a Fastboot command given in Snagflash format
gpt <device num> <partitions>: write a GPT partition table to the specified mmc device
flash-mmc <device_num> <image_path> <image_offset> [<partition_name>]
	Write the file at <image_path> to an MMC device or partition.
	The "fb-addr" and "fb-size" environment variables are required.
flash-mtd <device_name|partition_name> <image_path> <image_offset>:
	Write the file at <image_path> to an MTD device or partition.
	The "fb-addr", "fb-size" and "eraseblk-size" environment
	variables are required.

environment:

fb-addr: address in memory of the Fastboot buffer
fb-size: size in bytes of the Fastboot buffer
eraseblk-size: size in bytes of an erase block on the target Flash device
```

