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

