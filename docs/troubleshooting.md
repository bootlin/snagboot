# Troubleshooting

## AttributeError: /usr/lib/x86_64-linux-gnu/libhidapi-hidraw.so: undefined symbol: hid_get_input_report

This is related to hid 1.0.5 using a symbol which isn't supported in your
version of libhidapi-hidraw0. Downgrading to hid==1.0.4 should fix the issue:

```bash
python3 -m pip uninstall hid
python3 -m pip install hid==1.0.4
```

## HID exceptions on NXP i.MX

When recovering i.MX boards, it's possible to encounter some fairly vague
`HIDException` errors. Sometimes, this is due to a complicated USB hardware
setup e.g. daisy chaining hubs. We recommend you try plugging the board
directly to your computer or using only one USB hub.

## SPL fails to find a boot device

Make sure that your SPL supports whatever USB gadget is needed to recover your
specific type of SoC. These are specified in the [firmware
binaries](fw_binaries.md) section of the docs.

## U-Boot DFU/UMS/Fastboot commands fail with `Controller uninitialized`

On some boards, you have to enable `CONFIG_USB_ETHER` in U-Boot for USB gadgets
to work correctly.

## AM335x UART recovery fails after running SPL

In some cases SPL's standard console output can be confused with xmodem 'C'
pings. You can set the following U-Boot configuration options to try and silence
SPL:

```
CONFIG_SPL_SILENT_CONSOLE=y
CONFIG_SPL_BANNER_PRINT=n
CONFIG_SPL_DISPLAY_PRINT=n
```

## Snagfactory fails with USB I/O errors when processing many boards

These kinds of errors can sometimes be caused by overwhelmed USB hubs. In an
ideal scenario, each board is plugged into a separate root hub port, but if an
external hub is absolutely necessary, using one with a higher capacity or making
sure that it is powered by an independent supply can help.

## Ambarella SoC recovery issues

### USB device not detected

If the Ambarella SoC is not detected as a USB device, make sure:
1. The board is properly set to USB boot mode using the appropriate jumpers or switches
2. The USB cable is connected to the correct port (usually the OTG port)
3. The board is powered on

### DRAM initialization fails

DRAM initialization can fail if the ADS script doesn't match the specific memory configuration of your board. Make sure you're using the correct ADS script for your specific board model and memory type.

### Bootloader fails to enter Amboot mode

If the bootloader fails to enter Amboot mode:
1. Check that you're using the correct bootloader binary for your SoC model
2. Ensure the board has enough power (some boards may require a powered USB hub)
3. Try resetting the board and starting the recovery process again
