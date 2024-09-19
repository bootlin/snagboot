# Supporting new SoCs: hardware inventory

Snagrecover supports a precisely defined set of SoC models. These are all
listed in [supported_socs.yaml](../../src/snagrecover/supported_socs.yaml).
Models are grouped into SoC families. These are groups of devices that support
similar recovery flows.

When adding a new SoC family support, you should begin by making a list of all
the SoC models that you wish to include in the support.

Then, for each model in your list, procure the SoC's technical reference manual
or other relevant documentation and read the section which describes the USB
boot mode. Confirm that all SoC models in your list have similar USB boot
procedures. If this is not the case, you will have to separate the list into
multiple groups, with each group having its own separate support.

Your list of SoC models defines a Snagrecover SoC family. At this point, you
should choose a suitable name for it and add the SoC models to the
[supported_socs.yaml](../../src/snagrecover/supported_socs.yaml) file.

The next step is to procure a set of boards that will allow you to test
Snagrecover on your SoC family. At least one tested SoC model is required for a
family to be added to Snagrecover. If some of your SoC models have special
quirks or particularities, it is recommended that you test them as well.

## Example: the "imx" SoC family

Here is a nonexhaustive list of i.MX SoCs supported by Snagrecover:

imx28, imx53, imx6q, imx6ull, imx7d, imx8mm, imx8qm, imx8qxp, imx93, imx6d,
imx6sl, imx6sll, ...

All of these devices are able to boot in USB recovery mode by exposing an HID
gadget to the host machine. A vendor-specific variety of the SDP protocol is
used over this HID layer to download and run code in internal RAM.

