## General guidelines

- do not contribute code that you are not legally allowed to contribute to this
  project, e.g. code obtained from decompiled vendor binaries with
  restrictive EULAs.
- when adding new SoC supports/protocols, please follow the general code
  structure used by existing SoC supports

## Style guide

- tabs are used for indentation
- function names use snake case, class names use camel case and global
  numeric/string constants use screaming snake case.
- function definitions should have type hints when possible
- operators are surrounded by spaces e.g. a = 3 + 2 not a=3+2
- function arguments are separated by spaces e.g. foo(a, b, c)
- please lint your code with ruff: `cd snagboot && ruff .`

## Code architecture

- snagrecover should be board-agnostic, any board-specific logic should be
  handled via external configuration input
- snagflash should be board and SoC-agnostic, only assuming that U-Boot is
  installed and configured properly
- code in src/snagrecover/firmware should only be accessed using the
  run_firmware interface
- code in src/snagrecover/recoveries should not parse or otherwise handle
  firmware binaries
- when adding a new protocol to src/snagrecover/protocols, please use the
  memory_ops interface when possible
- snagrecover should not modify non-volatile memories

## Wishlist

Here are a few things which would be nice to add to the recovery tool:
- testing snagrecover on supported but untested SoCs (see
  [supported_socs.yaml](src/snagrecover/supported_socs.yaml))
- snagrecover support for RaspberryPi platforms (Broadcom BCM283x and
  BCM271x SoCs)
- snagrecover support for Rockchip SOCs. Some initial investigation
  has been done in this direction, but there are some difficulties due
  to the lack of proper USB gadget support in the U-Boot SPL for
  Rockchip platforms. Contact us if you're interested in this effort.
- snagrecover support for Microchip AT91 SoCs
