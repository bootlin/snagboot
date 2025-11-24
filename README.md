# Snagboot

Snagboot intends to be an open-source and generic replacement to the
vendor-specific, sometimes proprietary, tools used to recover and/or reflash
embedded platforms. Examples of such tools include STM32CubeProgrammer, SAM-BA
ISP, UUU, and sunxi-fel. Snagboot is made of three separate parts:

- **snagrecover** uses vendor-specific ROM code mechanisms to initialize
  external RAM and run U-Boot, without modifying any non-volatile
  memories.
- **snagflash** communicates with U-Boot to flash system images to non-volatile
  memories, using either DFU, UMS or Fastboot.
- **snagfactory** FIXME

<p align="center">
  <img src="docs/tutorial_snagrecover.gif" alt="animated" />
</p>

Snagboot currently supports the following families of System-On-Chips (SoCs):

 * [Allwinner sunxi](https://linux-sunxi.org/) A10, A10S, A13, A20, A23, A31, A33, A63, A64, A80, A83T, AF1C100S, H2+, R8, R16, R40, R329, R528, T113-S3, V3S, V5S, V536, V831, V853
 * [STMicroelectronics](http://st.com/) [STM32MP1](https://www.st.com/en/microcontrollers-microprocessors/stm32mp1-series.html) and [STM32MP2](https://www.st.com/en/microcontrollers-microprocessors/stm32mp2-series.html)
 * [Microchip](https://www.microchip.com/) [SAMA5](https://www.microchip.com/en-us/products/microprocessors/32-bit-mpus/sama5)
 * [NXP](https://www.nxp.com/) [i.MX6](https://www.nxp.com/products/processors-and-microcontrollers/arm-processors/i-mx-applications-processors/i-mx-6-processors:IMX6X_SERIES), [i.MX7](https://www.nxp.com/products/processors-and-microcontrollers/arm-processors/i-mx-applications-processors/i-mx-7-processors:IMX7-SERIES), [i.MX8](https://www.nxp.com/products/processors-and-microcontrollers/arm-processors/i-mx-applications-processors/i-mx-8-applications-processors:IMX8-SERIES), [i.MX91](https://www.nxp.com/products/i.MX91), [i.MX93](https://www.nxp.com/products/processors-and-microcontrollers/arm-processors/i-mx-applications-processors/i-mx-9-processors/i-mx-93-applications-processor-family-arm-cortex-a55-ml-acceleration-power-efficient-mpu:i.MX93)
 * [Texas Instruments](https://www.ti.com) [AM335x](https://www.ti.com/product/AM3358), [AM62x](https://www.ti.com/product/AM625), [AM62Lx](https://www.ti.com/product/AM62L), [AM64x](https://www.ti.com/product/AM6442), [AM654x](https://www.ti.com/product/AM6548)
 * [Xilinx/AMD](https://www.amd.com/) [Zynq UltraScale+ MPSoC](https://www.amd.com/en/products/adaptive-socs-and-fpgas/soc/zynq-ultrascale-plus-mpsoc.html)
 * [Intel](https://www.intel.com/) Keembay
 * [Broadcom](https://www.broadcom.com/) BCM2711 and BCM2712, used in [Raspberry Pi 4 & 5](https://www.raspberrypi.com/documentation/computers/processors.html)
 * [AMLogic](https://www.amlogic.com/#Products) series: G12A (eg S905D2), G12B (eg A311D), SM1 (eg S905D3) and series: GXL (eg S905D), GXM (eg S912), GXBB (eg S905), AXG (eg A113D)


Please check [supported_socs.yaml](https://github.com/bootlin/snagboot/blob/main/src/snagrecover/supported_socs.yaml)
or run `snagrecover --list-socs` for a more precise list of supported SoCs.

## Installing Snagboot

Please read the [installation guide](FIXME)

## Using Snagboot

Please read the [user guide](FIXME)

## Contributing

Contributions are welcome! Since Snagboot includes many different recovery
techniques and protocols, we try to keep the code base as structured as
possible. Please consult the [contribution guidelines](https://github.com/bootlin/snagboot/blob/main/CONTRIBUTING.md).

## License

Snagboot is released under the [GNU General Public License version 2](https://github.com/bootlin/snagboot/blob/main/LICENSE)
