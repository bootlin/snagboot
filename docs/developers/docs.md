# Supporting new SoCs: Documenting your new support

Once your new SoC support is fully functional, the last step is to document it
in the same way as the existing SoC supports.

Update the [README](../../README.md) to mention that your SoC family is supported.

Add general instructions for setting up boards for recovery in
[board_setup.md](../board_setup.md).

Describe the required firmware binaries and associated configuration options in
[fw_binaries.md](../fw_binaries.md).

If there are any quirks and pitfalls that users should watch out for when
recovering your SoCs, you can mention them in
[troubleshooting.md](../troubleshooting.md).

