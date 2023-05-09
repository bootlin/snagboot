# Running snagflash

**Note:** A delay might be required between snagrecover and snagflash, to let
U-Boot start up before connecting to it.

In all flashing modes, snagflash takes the protocol argument, which specifies either DFU, UMS or fastboot.

 * -P, --protocol {dfu,ums,fastboot} Protocol to use for flashing

## DFU mode

In DFU mode, snagflash takes two additional arguments :

 * -p --port vid:pid 
   The USB address of the DFU device exposed by U-Boot 
 * -D --dfu-config  altsetting[,size]:path 
   The altsetting and path of a file to download to the board. This should match
   the value specified in dfu\_alt\_info in U-Boot. This flag can be passed
   multiple times, to specify multiple files to download. The files will be
   downloaded in the order that the flags were passed in.

For instructions on how to setup DFU in U-Boot, please refer to the [U-Boot
documentation](https://u-boot.readthedocs.io/en/latest/usage/dfu.html).

## UMS mode

Snagflash can copy a file to either a raw block device or a mounted one. When
copying to a raw block device, it uses bmap to speed up transfers.
In UMS mode, snagflash takes two additional arguments:

 * -b –blockdev device 
   A file to be written to a raw block device. This can only be passed once.
 * -D --dest
   Sets the destination file name for transfers to mounted devices. 
 * -s --src filepath
   Source file to copy to destination
 * --size Optional. You can specify this to copy only a portion of the source
 	file. Only works for raw transfers. Can be specified in decimal or
 	hexadecimal.

Make sure that snagflash has the necessary access rights to the target
devices/mount dirs. If you are passing a raw partition, make sure that it is not
mounted. If you want to automate this process, you might have to write udev
rules to make sure that device paths and mount points stay consistent across
runs.

**Note:** sizes can be specified in decimal or hexadecimal

## Fastboot mode

In fastboot mode, snagflash takes two additional arguments: 

 * -p --port vid:pid The USB address of the Fastboot device exposed by U-Boot 
 * -f --fastboot_cmd  cmd:args A fastboot command to be sent to U-Boot. The
 	following commands are supported by snagflash (which does not mean that they
 	are supported by your U-Boot!) :

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

For more information on Fastboot commands, see the [fastboot
specification](https://android.googlesource.com/platform/system/core/+/refs/heads/master/fastboot/README.md)
and the [U-Boot
docs](https://elixir.bootlin.com/u-boot/v2023.04/source/doc/android/fastboot.rst). 

