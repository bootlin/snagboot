# Configuring eMMC hardware partitions

Some eMMC devices support advanced configuration of the User Data Area and
general purpose hardware partitions. In this section, we will show how these
parameters can be changed from the U-Boot CLI, and how this can be leveraged by
Snagfactory to perform hardware partitioning on batches of devices.

## General concepts

Most eMMC devices divide their flash memory area into several distinct hardware
partitions. This should not be confused with software partitions, which are
defined by a partition table such as GPT and interpreted by software.

The following hardware partitions are typically defined:

Boot#0: First boot partition
Boot#1: Second boot partition
User Data Area: system and application data
RPMB: Replay Protected Memory Block

General purpose partitions (GP0,GP1,...) can also sometimes be added.

Some devices support creating enhanced hardware partitions. The meaning of
"enhanced" varies from manufacturer to manufacturer, but this often means that
the memory area uses pSLC (pseudo Single Layer Cell) storage, which reduces
memory capacity but increases reliability and resistance. You will have to check your
eMMC device manufacturer's documentation to know what "enhanced" means in your
case.

Using standard U-Boot commands, you can perform the following configuration actions:

 - Create an Enhanced User Data Area which covers a contiguous section of the
   User Data Area. This will reduce the overall size of the User Data Area. From
   the perspective of the operating system, the entire User Data area will still
   only appear as one device.
 - Slice off a section of the User Data Area and allocate it to a new general
   purpose partition. This new partition can optionally be configured as
   enhanced. The GP will appear as a new, separate device from the operating
   system's perspective.
 - Resize the boot and RPMB partitions (this is out of the scope of this document)

On some devices, for each configured hardware partition, an option called "write
reliability" can be enabled. This will force all write operations to the
partition to be atomic, incurring a performance decrease in exchange for better
resilience to power cuts.

/!\
**WARNING**: eMMC hardware partitioning is a one-time operation and cannot be
reverted once completed!
/!\

## Configuring hardware partitions from U-Boot

Ensure that U-Boot has been compiled with the MMC_HW_PARTITIONING option.

Boot to the U-Boot CLI on a device identical to those you will be configuring
with Snagfactory.

View the current hardware partition layout by running:

```
mmc hwpartition
```

If your eMMC has not been partitioned yet, you should see something like this:

```
Partition configuration:
        No enhanced user data area
        No GP1 partition
        No GP2 partition
        No GP3 partition
        No GP4 partition
```

Run the `mmc info` command and take note of the following parameters:

 - User Capacity
 - HC WP group size

Design a hardware partition layout suitable for your use case. Keep in mind that
new hardware partitions must be aligned on HC WP groups, and that the total size
of enhanced memory areas may be limited by the device.

The configuration of hardware partitions is a five-step process:

 1. check: mmc hwpartition <args> check
 2. set: mmc hwpartition <args> set
 3. complete: mmc hwpartition <args> complete
 4. reset and power cycle
 5. verify: mmc hwpartition

The arguments of the "mmc hwpartition" command are as follow:

```
mmc hwpartition <USER> <GP> <MODE>
	arguments (sizes in 512-byte blocks):
	USER - <user> <enh> <start> <cnt> <wrrel> <{on|off}>
		: sets user data area attributes
	GP - <{gp1|gp2|gp3|gp4}> <cnt> <enh> <wrrel> <{on|off}>
		: general purpose partition
```

**WARNING**: The U-Boot CLI tends to interpret every number as hexadecimal. To
be safe, specify every partition parameter as a hexadecimal number with a "0x"
prefix.

Here are example commands for the following hardware partition layout on a
14.8GiB eMMC device:

EUDA: offset 0, size 1200MiB, no wrl
GP1: size 2272MiB, enhanced, wrl
GP2: size 2272MiB, enhanced, wrl

```
setenv hwpart_usr 'user enh 0 0x258000 wrrel off'
setenv hwpart_gp1 'gp1 0x470000 enh wrrel on'
setenv hwpart_gp2 'gp2 0x470000 enh wrrel on'
setenv hwpart_args "${hwpart_usr} ${hwpart_gp1} ${hwpart_gp2}"
print hwpart_args
mmc hwpartition ${hwpart_args} check
```

At this point, make sure that the check command was successful. Then, continuing
in the same U-Boot session:

```
mmc hwpartition ${hwpart_args} set
mmc hwpartition
```

Both commands should succeed. Check the partition configuration returned by the
last command. Finally, still in the same U-Boot session:

```
mmc hwpartition ${hwpart_args} complete
reset
```

Power cycle the device by unplugging and replugging the power cable. Your eMMC
should now be partitioned successfully. You can check this by booting to a new
U-Boot CLI and running `mmc hwpartition`.

## Configuring hardware partitions from snagfactory

The "emmc-hwpart" flashing task can be used for this. The task arguments are of
the following form:

```
  euda:  --> Enhanced User Data Area start, size and write-reliability flag
    start: ...
    size: ...
    wrrel: True/False

  gp1: --> first general purpose partition start, size, enhanced flag, and write-reliability flag
    size: ...
    enh: ...
    wrrel: ...

  gp2:
    size: 0x470000
    enh: true
    wrrel: True

  ...

  skip-pwr-cycle: False --> eMMC hardware partitioning usually requires a power-cycle to be effective. If you want to skip this, you can set this flash to True.
```

The euda section is mandatory. All other sections are optional.

