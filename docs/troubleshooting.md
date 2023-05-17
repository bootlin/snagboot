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
`HIDException` errors. Sometimes, this is dues to a weird USB hardware setup
e.g. daisy chaining certain hubs. We recommend you try plugging the board
directly to your computer or using only one USB hub.

## SPL fails to find a boot device

Make sure that your SPL supports whatever USB gadget is needed to recover your
specific type of SoC.

- i.MX: SPL should have SDP USB gadget support
- AM62x: SPL should have DFU USB gadget support
- AM335: SPL should support booting from USB Ethernet, which implies the
  following options: 
```bash
CONFIG\_SPL\_NET\_SUPPORT=y
CONFIG\_SPL\_NET\_VCI\_STRING="AM335x U-Boot SPL"
CONFIG\_SPL\_USB\_GADGET\_SUPPORT=y
CONFIG\_SPL\_USB\_ETHER=y
# CONFIG\_SPL\_USB\_SDP\_SUPPORT is not set
```

