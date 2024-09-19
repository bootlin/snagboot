# Supporting new SoCs: recovery flow

Once you've specified an SoC family, the next step is to design a recovery flow
for it.

The goal of Snagrecover is to go from USB recovery mode to a U-Boot CLI.
Different SoC families use different methods to achieve this. Recovery flows are
what allow the Snagrecover codebase to maintain a minimum level of coherency
despite these differences. Recovery flows are basically an list of firmware that
should be downloaded and executed on the target device to achieve full recovery.

For example, here is a very simple recovery flow:

```
1. get USB recovery device exposed by ROM code
2. download and run U-Boot SPL in internal SRAM, to initialize external RAM
3. get USB recovery device exposed by SPL
4. download and run U-Boot proper in external RAM
```

Designing a recovery flow is the trickiest part of any Snagrecover support, as
it must follow several constraints:

 * No non-volatile storage devices must be modified or relied upon.
 * The target device must be uniquely identifiable from its bus and port
   numbers, which are reported by libusb. This is to allow parallel recovery
   of multiple devices which use the same USB vid:pid. It can become tricky
   if you must access the USB device through a higher-level system driver such
   as hidraw.
 * Only the USB link should be used to communicate with the target
 * Specific details of firmware handling and communication protocols must be
   delegated to the "firmware" and "protocols" layers of Snagrecover (these will be
   covered in more detail later on).

If you reference existing recovery tools to design your recovery flow, make
sure to respect the terms of the original codebase's license. All code
contributed to Snagboot must fall under a GPLv2-compatible license.

## Example: Recovery flow for SAMA5 SoCs

1. Get USB device exposed by ROM code, using bus and port numbers
2. Get the corresponding serial port device (SAMA5 ROM codes enumerate as serial ports)
3. Check the board ID by reading the CIDR register
4. Download and run the "lowlevel" firmware, to initialize the clock tree
5. Download and run the "extram" firmware, to initialize the external RAM
6. Write to the AXMIX\_REMAP register to remap ROM addresses to SRAM0
7. Download and run U-Boot proper.
8. Close the serial port.

