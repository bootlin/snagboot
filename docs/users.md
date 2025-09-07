# Getting started

**Note:** On Linux, running snagboot as root is not recommended and will typically not
work, since it is probably installed for the current user only

Firstly, check that your SoC is supported in snagrecover by running:

`snagrecover --list-socs`

Then follow these steps:

 - [Setup your board for recovery](board_setup.md)
 - [Run snagrecover](snagrecover.md)
 - [Run snagflash](snagflash.md)

For recovering and flashing large batches of boards efficiently, you may use the Snagfactory application which is included in Snagboot. Usage instructions for Snagfactory are available at [snagfactory.md](https://github.com/bootlin/snagboot/blob/main/docs/snagfactory.md). The configuration file syntax for Snagfactory is documented at [snagfactory_config.md](https://github.com/bootlin/snagboot/blob/main/docs/snagfactory_config.md).


Note that Snagfactory support is only included in the "gui" package variant: `pip install snagboot[gui]`

Some [benchmark results](https://github.com/bootlin/snagboot/blob/main/docs/snagfactory_benchmarks.md) are provided in the Snagfactory docs.

If you encounter issues, please take a look at the
[troubleshooting](https://github.com/bootlin/snagboot/blob/main/docs/troubleshooting.md) section.

You can play the snagrecover tutorial in your terminal!

```
sudo apt install asciinema
asciinema play -s=2 docs/tutorial_snagrecover.cast
```
