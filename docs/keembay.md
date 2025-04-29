# Intel Keembay Board Support

This document describes how to use Snagboot with Intel Keembay boards.

## Supported Boards

The following Intel Keembay boards are supported:

- Intel Keembay EVM
- Intel Keembay M2
- Intel Keembay HDDL2

## Prerequisites

Before using Snagboot with Keembay boards, ensure you have:

1. Installed Snagboot according to the main installation instructions
2. Set up the udev rules for Keembay boards:
   ```bash
   $ snagrecover --udev > 50-snagboot.rules
   $ sudo cp 50-snagboot.rules /etc/udev/rules.d/
   $ sudo udevadm control --reload-rules
   $ sudo udevadm trigger
   ```

## Board Setup for Recovery

To put your Keembay board in recovery mode:

1. Power off the board
2. Set the boot switch to recovery mode position (refer to your board's documentation for the exact switch location)
3. Connect the USB cable to the recovery port
4. Power on the board

The board should now be detected in recovery mode with USB VID:PID `8087:0b39`.

## Required Firmware Files

To recover and flash a Keembay board, you need the following firmware files:

1. **FIP (Firmware Image Package)**: This is the first stage firmware that will be flashed to the board.
   - For EVM boards: `fip-evm.bin`
   - For M2 boards: `fip-m2.bin`
   - For HDDL2 boards: `fip-hddl2.bin`

2. **U-Boot**: The bootloader that will be flashed after the FIP.
   - `u-boot.bin`

3. **OS Images**: The operating system images to flash to the board.
   - `boot.img`: Boot partition image
   - `system.img`: System partition image
   - `syshash.img`: System hash image for verified boot
   - `data.img`: Data partition image

## Recovery Process

The recovery process for Keembay boards consists of two stages:

1. **FIP Recovery**: Flash the FIP to the board in recovery mode
2. **OS Recovery**: Flash the OS images to the board in fastboot mode

### Using snagrecover

To recover a Keembay board using snagrecover:

```bash
$ snagrecover -s keembay -f templates/keembay-generic.yaml
```

This will:
1. Detect the board in recovery mode
2. Flash the FIP to the board
3. Wait for the board to reboot into fastboot mode
4. Flash U-Boot to the board

```
# Enter the MaskROM
[242604.547769] usb 1-4: reset full-speed USB device number 2 using xhci_hcd
[242622.288629] usb 1-1: new high-speed USB device number 79 using xhci_hcd
[242622.417923] usb 1-1: New USB device found, idVendor=8087, idProduct=0b39, bcdDevice= 0.01
[242622.417930] usb 1-1: New USB device strings: Mfr=1, Product=2, SerialNumber=3
[242622.417933] usb 1-1: Product: Intel Movidius Keem Bay 3xxx
[242622.417935] usb 1-1: Manufacturer: Intel Corp.
[242622.417937] usb 1-1: SerialNumber: xxxxxxxx
[242646.354732] usb 1-4: reset full-speed USB device number 2 using xhci_hcd

# Uboot fastboot
[242662.858099] usb 1-1: USB disconnect, device number 79
[242676.560613] usb 1-1: new high-speed USB device number 80 using xhci_hcd
[242676.688139] usb 1-1: New USB device found, idVendor=8087, idProduct=da00, bcdDevice= 2.23
[242676.688153] usb 1-1: New USB device strings: Mfr=1, Product=2, SerialNumber=3
[242676.688159] usb 1-1: Product: USB download gadget
[242676.688163] usb 1-1: Manufacturer: Intel
[242676.688168] usb 1-1: SerialNumber: XXXXXXXXXXXXXXXX
```

### Using snagflash

After recovering the board with snagrecover, you can use snagflash to flash the OS images:

```bash
$ snagflash -P fastboot -p 8087:da00 -f flash:boot_a:boot.img -f flash:system_a:system.img -f flash:syshash_a:syshash.img -f flash:data:data.img
```

Alternatively, you can use the `flashall` command to flash all images at once:

```bash
$ snagflash -P fastboot -p 8087:da00 -f flashall:boot.img,system.img,syshash.img,data.img
```

The `flashall` command will:
1. Format the device with a GPT partition table
2. Flash each image to its corresponding partition:
   - boot.img → boot_a and boot_b partitions
   - system.img → system_a and system_b partitions
   - syshash.img → syshash_a and syshash_b partitions
   - data.img → data partition
   - factory.img → factory partition

## Troubleshooting

### Board not detected in recovery mode

If the board is not detected in recovery mode:

1. Check that the boot switch is in the recovery position
2. Ensure the USB cable is connected to the recovery port
3. Verify that the udev rules are properly installed
4. Try a different USB cable or port

### Board not entering fastboot mode after FIP flashing

If the board doesn't enter fastboot mode after FIP flashing:

1. Check the FIP file is correct for your board model
2. Try power cycling the board
3. Check the board's serial console for error messages

### Flashing fails

If flashing fails:

1. Ensure you're using the correct image files for your board
2. Check that the images are not corrupted
3. Try the recovery process again from the beginning
