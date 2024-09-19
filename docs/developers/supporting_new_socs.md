# Adding support for a new family of SoCs

First of all, thank you for your interest in contributing to Snagboot!

The codebase is divided into three distinct parts:

 * Snagrecover: downloads and runs U-Boot on a device powered up in USB recovery mode
 * Snagflash: flashes and configures storage devices over a USB gadget exposed by U-Boot
 * Snagfactory: runs snagrecover and snagflash in parallel on groups of devices

The only part of Snagboot which is SoC-specific is Snagrecover. Therefore, when
adding support for a new family of SoCs, your efforts will be exclusively
focused on the recovery aspect of Snagboot.

The following documentation is meant to guide contributors who plan to add
support for a new family of SoCs to Snagboot. It lays out the main steps required
to design and implement such a support and specifies the core rules to follow
when integrating new code to the project.

Implementation of a new SoC family support can be broken down into six steps:

 1. [Inventory of SoC models and their USB boot modes](soc_inventory.md)
 2. [Design of a recovery flow](recovery_flow.md)
 3. [Implementation of basic USB communication with the target](protocols.md)
 4. [Implementation of firmware handling](firmware.md)
 5. [Implementation of the recovery flow](recovery.md)
 6. [Documentation of the new support](docs.md)

For each of these steps, an example is given using an existing support.

Once your new support is ready, you can simply open a GitHub pull request. If
more information is required, you can open a GitHub issue or contact us via
email.

