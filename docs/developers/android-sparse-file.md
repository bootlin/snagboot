
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
