
## File header

Field               | Length in bytes | Info
--------------------|-----------------|---------------------
Magic               |               4 | 0xED26FF3A
Major               |               2 | Always 1
Minor               |               2 | Always 0
Header length       |               2 | Should be 28
Chunk header length |               2 | Should be 12
Block size          |               4 | Block size in bytes. Multiple of 4. Usually 4096
Blocks              |               4 | Number of blocks of the non-sparse image
Chunks              |               4 | Number of chunks of the sparse image
Checksum            |               4 | Optional checksum


## Chunk header

Field      | Length in bytes | Info
-----------|-----------------|-----
Type       |               2 | Type of the chunk
Reserved   |               2 | '0000'
Size       |               4 | Size of the chunk in the non-sparse image in blocks
Total size |               4 | Size of the chunk including the header. in bytes So at least 12.


Chunk types:

  - ``CHUNK_TYPE_DONTCARE``: There's no chunk data. Don't care about the output file content,
  so skip to the offset ``$current_offset + $block_size*$size`` of the non-sparse output file
  - ``CHUNK_TYPE_RAW`` : file data of ``$block_size*$size``
  - ``CHUNK_TYPE_FILL``: the chunk data is containing the value to use to fill the output. Usually 0.
  - ``CHUNK_TYPE_CRC32``: the chunk data is a checksum.

## Fastboot, buffer size and splitting sparse files

When flashing a (sparse) file with the fastboot protocol, the data is stored into a buffer.
This buffer has a size of ``max-download-size`` bytes. When the file is bigger than this
size, the solution is to split the image into several sparse images.

As the fastboot flash command is only allowing to flash according to a partition, there's
no offset involved. A solution is needed to not write the 2nd image and the following ones
without always writing at the beginning of the partition.

The solution is to use the ``CHUNK_TYPE_DONTCARE``, which will skip some blocks of the output
partition in the beginning of the 2+ images.

Each split fragment is a fully valid, self-contained sparse file:

- its ``total_blks`` field in the sparse header always reports the full block
  count of the *original*, unsplit image, not just the blocks contained in
  that particular fragment;
- it is prefixed with a ``CHUNK_TYPE_DONTCARE`` chunk covering every block
  already written by previous fragments;
- it is suffixed with a ``CHUNK_TYPE_DONTCARE`` chunk covering every block that
  will be written by later fragments;
- the total serialized size of the fragment (file header + all chunk headers +
  payloads) never exceeds ``max-download-size``.

## Splitting raw (non-sparse) files

Raw binary files can also be split into a sequence of ``max-download-size``-bounded
sparse fragments, using the exact same splitting algorithm described above.

The raw file is treated as a single logical ``CHUNK_TYPE_RAW`` region spanning
the whole image:

```text
total_blks = ceil(file_size / block_size)
```

where ``block_size`` defaults to 4096 bytes. This synthetic RAW region is fed
into the same fragment-splitting logic used for real sparse files (prefix/suffix
``CHUNK_TYPE_DONTCARE`` padding, header/overhead accounting bounded by
``max-download-size``), so raw files gain automatic splitting support without
needing any format conversion of the file on disk.

If the raw file size is not a multiple of ``block_size``, the final block is
transparently zero-padded up to the block boundary in the generated sparse
payload only; the source file itself is never modified.

This is implemented by ``snagrecover.protocols.fastboot.Fastboot.flash_image()``,
which:

1. Reads ``max-download-size`` from U-Boot (raises an error if it can't be read,
   or if it is 0).
2. If the file's size fits within ``max-download-size``, downloads and flashes
   it directly with no splitting.
3. Otherwise, detects whether the file is an Android sparse file (by checking
   its magic cookie) or a raw binary file, and splits it accordingly:
   sparse files are split with the existing chunk-parsing logic, raw files are
   split via the synthetic single-RAW-region approach described above.
4. Downloads and flashes each fragment in turn.
