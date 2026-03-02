#!/usr/bin/env python3
"""
SD Card Image Builder for Orange Box S40 (Allwinner H723)
=========================================================
Creates a bootable SD card image using extracted vendor components.

Usage:
    python build_sdcard_image.py [--size SIZE_MB] [--output OUTPUT_FILE]

Prerequisites (in firmware_dump/ directory):
    - boot_chain_14mb.bin  (raw eMMC header with boot0 + sunxi-package)
    - boot_a.img           (Android boot image with vendor kernel)
    - env_a.bin            (U-Boot environment, will be modified)
    - device_tree.dtb      (device tree blob)
    - vendor_modules.tar.gz (kernel modules)
    - vendor_firmware.tar.gz (firmware files)

The script creates an SD card image with:
    - Protective MBR + GPT partition table
    - boot0 at sector 16 (BROM requirement)
    - boot0 copy at sector 256 (redundancy)
    - sunxi-package (U-Boot+ATF+SCP+OP-TEE) at sector 24576
    - env_a partition with modified U-Boot environment for Linux boot
    - boot_a partition with vendor kernel
    - rootfs partition (empty, to be populated separately)

Boot flow:
    BROM → boot0 (from SD sector 16) → sunxi-package (U-Boot from SD sector 24576)
    → U-Boot reads env_a → loads boot_a → kernel boots with custom args
    → kernel mounts rootfs from SD partition → Linux userspace starts

Removing the SD card boots original Android from eMMC (non-destructive).
"""

import argparse
import binascii
import os
import struct
import sys
import uuid

# ============================================================================
# Constants
# ============================================================================

SECTOR_SIZE = 512
DEFAULT_IMAGE_SIZE_MB = 2048  # 2 GB default

# Raw boot chain locations (BROM/vendor hardcoded offsets)
BOOT0_SECTOR = 16          # 8 KB offset (BROM reads boot0 here)
BOOT0_COPY_SECTOR = 256    # 128 KB offset (redundant boot0)
MAC_SECTOR = 12288          # 6 MB offset (MAC address area)
SUNXI_PKG_SECTOR = 24576   # 12 MB offset (sunxi-package: U-Boot+ATF+SCP+OP-TEE)

# GPT partition layout (matching eMMC for compatibility)
GPT_FIRST_USABLE = 73728   # Sector where first partition starts (36 MB)

# Partition definitions: (name, start_sector, size_in_sectors)
# We simplify the 29-partition eMMC layout to just what Linux needs
PARTITIONS = [
    ("bootloader_a", 73728,  65536),    # 32 MiB (for boot logos, optional)
    ("env_a",        139264, 512),       # 256 KiB (U-Boot environment)
    ("boot_a",       139776, 131072),    # 64 MiB (kernel image)
    ("rootfs",       270848, 0),         # Rest of SD card (calculated dynamically)
]

# GPT constants
GPT_HEADER_SIZE = 92
GPT_ENTRY_SIZE = 128
GPT_MAX_ENTRIES = 128  # Standard GPT has 128 entries
GPT_SIGNATURE = b'EFI PART'
GPT_REVISION = 0x00010000

# Microsoft Basic Data GUID (for generic partitions)
BASIC_DATA_GUID = uuid.UUID('EBD0A0A2-B9E5-4433-87C0-68B6B72699C7')

# Linux filesystem GUID
LINUX_FS_GUID = uuid.UUID('0FC63DAF-8483-4772-8E79-3D69D8477DE4')


# ============================================================================
# Helper Functions
# ============================================================================

def crc32(data: bytes) -> int:
    """Calculate CRC32 (same as zlib.crc32 but always unsigned)."""
    return binascii.crc32(data) & 0xFFFFFFFF


def uuid_to_mixed_endian(u: uuid.UUID) -> bytes:
    """Convert UUID to GPT mixed-endian format."""
    b = u.bytes
    # GPT stores first 3 groups as little-endian, last 2 as big-endian
    return (b[3::-1] + b[5:3:-1] + b[7:5:-1] + b[8:16])


def create_guid() -> bytes:
    """Generate a random GUID in GPT mixed-endian format."""
    return uuid_to_mixed_endian(uuid.uuid4())


def encode_utf16le(name: str, max_bytes: int = 72) -> bytes:
    """Encode partition name as UTF-16LE, padded with zeros."""
    encoded = name.encode('utf-16-le')
    if len(encoded) > max_bytes:
        encoded = encoded[:max_bytes]
    return encoded.ljust(max_bytes, b'\x00')


def uboot_env_crc32(env_data: bytes) -> int:
    """Calculate CRC32 for U-Boot environment data."""
    return binascii.crc32(env_data) & 0xFFFFFFFF


# ============================================================================
# U-Boot Environment Modification
# ============================================================================

def parse_uboot_env(raw: bytes) -> dict:
    """Parse U-Boot environment from raw partition data."""
    # Format: 4-byte CRC32 + 1-byte flags + null-terminated key=value pairs
    stored_crc = struct.unpack('<I', raw[0:4])[0]
    flags = raw[4]
    env_data = raw[5:]

    # Find the double-null terminator
    end = env_data.find(b'\x00\x00')
    if end < 0:
        end = len(env_data)
    env_data = env_data[:end]

    # Parse key=value pairs
    env = {}
    for entry in env_data.split(b'\x00'):
        if b'=' in entry:
            key, val = entry.split(b'=', 1)
            env[key.decode('ascii')] = val.decode('ascii')

    # Verify CRC
    computed_crc = crc32(raw[5:])  # CRC covers flags byte onward... 
    # Actually, standard U-Boot env CRC covers data starting after CRC field
    # Some U-Boot versions include flags byte, some don't
    # For Allwinner, CRC covers bytes 4 onward (including flags)
    computed_crc = crc32(raw[4:])

    print(f"  Stored CRC:   0x{stored_crc:08x}")
    print(f"  Computed CRC: 0x{computed_crc:08x}")
    print(f"  CRC match:    {'YES' if stored_crc == computed_crc else 'NO (will recalculate)'}")
    print(f"  Flags byte:   0x{flags:02x}")
    print(f"  Variables:    {len(env)}")

    return env


def build_uboot_env(env: dict, total_size: int = 262144) -> bytes:
    """Build U-Boot environment binary with CRC."""
    # Build environment data: key=value\0key=value\0...\0\0
    pairs = []
    for key, val in env.items():
        pairs.append(f"{key}={val}".encode('ascii'))

    env_data = b'\x00'.join(pairs) + b'\x00\x00'

    # Pad to fill the partition (minus 5 bytes for CRC + flags)
    data_size = total_size - 5
    if len(env_data) > data_size:
        raise ValueError(f"Environment data too large: {len(env_data)} > {data_size}")
    env_data = env_data.ljust(data_size, b'\x00')

    # Build: CRC(4) + flags(1) + data
    flags = b'\x00'
    payload = flags + env_data
    crc = crc32(payload)

    return struct.pack('<I', crc) + payload


def create_linux_env(original_env: dict) -> dict:
    """Modify U-Boot environment for Linux boot from SD card."""
    env = original_env.copy()

    # Key modifications for Linux boot
    env['bootdelay'] = '3'  # Allow U-Boot console access (was 0)
    env['bootcmd'] = 'run setargs_linux boot_normal'  # Use Linux boot args

    # Custom Linux boot arguments
    # root=/dev/mmcblk0p4 — when booting from SD, SD card is typically mmcblk0
    # rootwait — wait for root device to appear
    # firmware_class.path — where kernel looks for firmware files
    # clk_ignore_unused — prevent kernel from disabling "unused" clocks (critical for display)
    # cma=24M — contiguous memory for display/GPU DMA
    env['setargs_linux'] = (
        'setenv bootargs '
        'console=${console} '
        'loglevel=${loglevel} '
        'root=/dev/mmcblk0p4 '
        'rootfstype=ext4 '
        'rw '
        'rootwait '
        'init=/sbin/init '
        'firmware_class.path=/lib/firmware '
        'clk_ignore_unused '
        'cma=${cma} '
        'cpufreq.default_governor=${default_governor} '
        'earlyprintk=${earlyprintk} '
        'gpt=1 '
        'panic=10'
    )

    # Keep original boot_normal — it reads kernel from "boot" partition via sunxi_flash
    # boot_normal=sunxi_flash read 40007000 boot;bootm 40007000

    # Add fallback to Android boot (original behavior)
    env['boot_android'] = 'run setargs_nand boot_normal'

    # Remove Android-specific vars that might cause issues
    for key in ['force_normal_boot', 'BOOTMODE']:
        if key in env:
            del env[key]

    # Override init
    env['init'] = '/sbin/init'

    return env


# ============================================================================
# GPT Partition Table
# ============================================================================

def create_protective_mbr(disk_sectors: int) -> bytes:
    """Create a protective MBR for GPT."""
    mbr = bytearray(512)

    # Boot signature
    mbr[510] = 0x55
    mbr[511] = 0xAA

    # Protective MBR partition entry at offset 446
    # Type 0xEE = GPT protective
    entry_offset = 446
    mbr[entry_offset + 0] = 0x00  # Not bootable
    mbr[entry_offset + 1] = 0x00  # CHS start (ignored for GPT)
    mbr[entry_offset + 2] = 0x01
    mbr[entry_offset + 3] = 0x00
    mbr[entry_offset + 4] = 0xEE  # GPT protective type
    mbr[entry_offset + 5] = 0xFF  # CHS end
    mbr[entry_offset + 6] = 0xFF
    mbr[entry_offset + 7] = 0xFF

    # LBA start = 1
    struct.pack_into('<I', mbr, entry_offset + 8, 1)
    # LBA size = min(disk_sectors - 1, 0xFFFFFFFF)
    size = min(disk_sectors - 1, 0xFFFFFFFF)
    struct.pack_into('<I', mbr, entry_offset + 12, size)

    return bytes(mbr)


def create_gpt(disk_sectors: int, partitions: list) -> tuple:
    """Create GPT header and partition entries.

    Returns (primary_header, primary_entries, backup_entries, backup_header)
    """
    disk_guid = create_guid()

    # Calculate partition entries area
    entries_sectors = (GPT_MAX_ENTRIES * GPT_ENTRY_SIZE + SECTOR_SIZE - 1) // SECTOR_SIZE
    # Primary entries start at sector 2
    primary_entries_start = 2
    # First usable sector (after primary GPT)
    first_usable = primary_entries_start + entries_sectors
    # Ensure first_usable is at least GPT_FIRST_USABLE for Allwinner compatibility
    first_usable = max(first_usable, GPT_FIRST_USABLE)

    # Backup entries end at last sector - 1
    last_usable = disk_sectors - 1 - entries_sectors - 1
    backup_header_sector = disk_sectors - 1
    backup_entries_start = backup_header_sector - entries_sectors

    # Build partition entries
    entries = bytearray(GPT_MAX_ENTRIES * GPT_ENTRY_SIZE)
    for i, (name, start, size) in enumerate(partitions):
        if size == 0:
            # Dynamic: use remaining space
            size = last_usable - start + 1
        end = start + size - 1
        if end > last_usable:
            end = last_usable
            size = end - start + 1

        offset = i * GPT_ENTRY_SIZE

        # Partition type GUID
        if name == 'rootfs':
            type_guid = uuid_to_mixed_endian(LINUX_FS_GUID)
        else:
            type_guid = uuid_to_mixed_endian(BASIC_DATA_GUID)
        entries[offset:offset+16] = type_guid

        # Unique partition GUID
        entries[offset+16:offset+32] = create_guid()

        # Start and end LBA
        struct.pack_into('<Q', entries, offset + 32, start)
        struct.pack_into('<Q', entries, offset + 40, end)

        # Attributes (0)
        struct.pack_into('<Q', entries, offset + 48, 0)

        # Name (UTF-16LE, 72 bytes max)
        name_bytes = encode_utf16le(name)
        entries[offset + 56:offset + 56 + len(name_bytes)] = name_bytes

        print(f"  Partition {i+1}: {name:20s} sectors {start:>8d}-{end:>8d} "
              f"({(end-start+1)*512/1048576:>7.1f} MiB)")

    entries_crc = crc32(bytes(entries))

    # Build primary header
    primary_hdr = bytearray(SECTOR_SIZE)
    struct.pack_into('8s', primary_hdr, 0, GPT_SIGNATURE)
    struct.pack_into('<I', primary_hdr, 8, GPT_REVISION)
    struct.pack_into('<I', primary_hdr, 12, GPT_HEADER_SIZE)
    # CRC32 of header (initially 0, calculated after)
    struct.pack_into('<I', primary_hdr, 16, 0)
    struct.pack_into('<I', primary_hdr, 20, 0)  # Reserved
    struct.pack_into('<Q', primary_hdr, 24, 1)  # My LBA
    struct.pack_into('<Q', primary_hdr, 32, backup_header_sector)  # Alternate LBA
    struct.pack_into('<Q', primary_hdr, 40, first_usable)
    struct.pack_into('<Q', primary_hdr, 48, last_usable)
    primary_hdr[56:72] = disk_guid
    struct.pack_into('<Q', primary_hdr, 72, primary_entries_start)  # Entries start
    struct.pack_into('<I', primary_hdr, 80, GPT_MAX_ENTRIES)
    struct.pack_into('<I', primary_hdr, 84, GPT_ENTRY_SIZE)
    struct.pack_into('<I', primary_hdr, 88, entries_crc)

    # Calculate header CRC
    hdr_crc = crc32(bytes(primary_hdr[:GPT_HEADER_SIZE]))
    struct.pack_into('<I', primary_hdr, 16, hdr_crc)

    # Build backup header (swap my_lba and alternate_lba, update entries start)
    backup_hdr = bytearray(primary_hdr)
    struct.pack_into('<I', backup_hdr, 16, 0)  # Clear CRC first
    struct.pack_into('<Q', backup_hdr, 24, backup_header_sector)  # My LBA
    struct.pack_into('<Q', backup_hdr, 32, 1)  # Alternate LBA
    struct.pack_into('<Q', backup_hdr, 72, backup_entries_start)

    backup_crc = crc32(bytes(backup_hdr[:GPT_HEADER_SIZE]))
    struct.pack_into('<I', backup_hdr, 16, backup_crc)

    return bytes(primary_hdr), bytes(entries), bytes(entries), bytes(backup_hdr)


# ============================================================================
# Main Image Builder
# ============================================================================

def build_image(args):
    """Build the complete SD card image."""
    dump_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'firmware_dump')

    # Verify required files
    required_files = {
        'boot_chain_14mb.bin': 'Raw eMMC boot chain (boot0 + sunxi-package)',
        'boot_a.img': 'Android boot image (vendor kernel)',
        'env_a.bin': 'U-Boot environment partition',
    }

    print("=" * 70)
    print("SD Card Image Builder for Orange Box S40 (Allwinner H723)")
    print("=" * 70)
    print()

    print("[1/7] Checking required files...")
    for fname, desc in required_files.items():
        fpath = os.path.join(dump_dir, fname)
        if not os.path.exists(fpath):
            print(f"  ERROR: Missing {fname} ({desc})")
            print(f"  Expected at: {fpath}")
            sys.exit(1)
        size = os.path.getsize(fpath)
        print(f"  OK: {fname} ({size:,} bytes)")

    # Calculate image size
    image_size_bytes = args.size * 1024 * 1024
    total_sectors = image_size_bytes // SECTOR_SIZE
    print(f"\n  Image size: {args.size} MiB ({total_sectors:,} sectors)")

    # ---- Step 2: Read source files ----
    print("\n[2/7] Reading source files...")

    boot_chain = open(os.path.join(dump_dir, 'boot_chain_14mb.bin'), 'rb').read()
    print(f"  boot_chain: {len(boot_chain):,} bytes")

    boot_a = open(os.path.join(dump_dir, 'boot_a.img'), 'rb').read()
    print(f"  boot_a.img: {len(boot_a):,} bytes")

    env_raw = open(os.path.join(dump_dir, 'env_a.bin'), 'rb').read()
    print(f"  env_a.bin:  {len(env_raw):,} bytes")

    # ---- Step 3: Modify U-Boot environment ----
    print("\n[3/7] Modifying U-Boot environment for Linux boot...")
    original_env = parse_uboot_env(env_raw)
    linux_env = create_linux_env(original_env)

    # Show key changes
    print("\n  Key environment changes:")
    for key in ['bootdelay', 'bootcmd', 'init']:
        old = original_env.get(key, '(not set)')
        new = linux_env.get(key, '(not set)')
        if old != new:
            print(f"    {key}: '{old}' → '{new}'")
    print(f"    setargs_linux: (NEW) '{linux_env.get('setargs_linux', '')[:80]}...'")

    env_bin = build_uboot_env(linux_env, total_size=len(env_raw))

    # ---- Step 4: Calculate partition layout ----
    print("\n[4/7] Creating partition layout...")

    # Adjust rootfs partition to use remaining space
    partitions = [(n, s, sz) for n, s, sz in PARTITIONS]
    for name, start, size in partitions:
        if size == 0:
            print(f"  rootfs partition starts at sector {start} "
                  f"(remaining ~{(total_sectors - start) * 512 / 1048576:.0f} MiB)")

    # ---- Step 5: Create GPT ----
    print("\n[5/7] Building GPT partition table...")
    mbr = create_protective_mbr(total_sectors)
    primary_hdr, primary_entries, backup_entries, backup_hdr = create_gpt(
        total_sectors, partitions
    )

    # ---- Step 6: Extract boot chain components ----
    print("\n[6/7] Extracting boot chain components from raw dump...")

    # boot0 at sector 16 (offset 0x2000)
    boot0_offset = BOOT0_SECTOR * SECTOR_SIZE
    # boot0 size from header at offset 0x10 (little-endian u32)
    boot0_size = struct.unpack('<I', boot_chain[boot0_offset + 0x10:boot0_offset + 0x14])[0]
    boot0_data = boot_chain[boot0_offset:boot0_offset + boot0_size]
    print(f"  boot0: {boot0_size:,} bytes at sector {BOOT0_SECTOR}")

    # Verify boot0 magic
    boot0_magic = boot_chain[boot0_offset + 4:boot0_offset + 12]
    if boot0_magic != b'eGON.BT0':
        print(f"  WARNING: boot0 magic mismatch: {boot0_magic} (expected eGON.BT0)")
    else:
        print(f"  boot0 magic: {boot0_magic.decode()} ✓")

    # sunxi-package at sector 24576 (offset 0xC00000)
    pkg_offset = SUNXI_PKG_SECTOR * SECTOR_SIZE
    pkg_magic = boot_chain[pkg_offset:pkg_offset + 13]
    if pkg_magic != b'sunxi-package':
        print(f"  WARNING: sunxi-package magic mismatch at sector {SUNXI_PKG_SECTOR}")
        print(f"  Got: {pkg_magic}")
    else:
        print(f"  sunxi-package magic: ✓")

    # Determine sunxi-package size from item entries
    # Header: 4 items, each item entry has offset+size
    num_items = struct.unpack('<I', boot_chain[pkg_offset + 0x20:pkg_offset + 0x24])[0]
    print(f"  sunxi-package items: {num_items}")

    # Find the end of the last item to determine total package size
    # Item entries are at 0x3C, 0x1AC, 0x31C, 0x48C (approximately 0x170 spacing)
    # Each item has: name(64 bytes) + padding + offset(4) + size(4)
    # Simpler approach: scan for the furthest offset+size
    max_end = 0
    item_names = []
    for scan_pos in range(pkg_offset, pkg_offset + 0x800, 1):
        # Look for "MIE;" or "IIE;" markers
        marker = boot_chain[scan_pos:scan_pos + 4]
        if marker in (b'MIE;', b'IIE;'):
            name_end = boot_chain[scan_pos + 4:scan_pos + 68].find(b'\x00')
            item_name = boot_chain[scan_pos + 4:scan_pos + 4 + name_end].decode('ascii')
            # offset and size are after the name block (at +0x44 from marker start)
            # Based on observed structure: offset at marker+0x44, size at marker+0x48
            item_offset_pos = scan_pos + 0x44
            item_size_pos = scan_pos + 0x48
            if item_offset_pos + 8 <= len(boot_chain):
                item_off = struct.unpack('<I', boot_chain[item_offset_pos:item_offset_pos + 4])[0]
                item_sz = struct.unpack('<I', boot_chain[item_size_pos:item_size_pos + 4])[0]
                item_end = item_off + item_sz
                if item_end > max_end:
                    max_end = item_end
                item_names.append(f"{item_name}({item_sz // 1024}KB)")

    # Round up to sector boundary
    pkg_size = ((max_end + SECTOR_SIZE - 1) // SECTOR_SIZE) * SECTOR_SIZE
    pkg_data = boot_chain[pkg_offset:pkg_offset + pkg_size]
    pkg_sectors = pkg_size // SECTOR_SIZE
    print(f"  sunxi-package: {pkg_size:,} bytes ({pkg_sectors} sectors)")
    print(f"  Contents: {', '.join(item_names)}")

    # MAC address area at sector 12288
    mac_offset = MAC_SECTOR * SECTOR_SIZE
    if mac_offset < len(boot_chain):
        mac_data = boot_chain[mac_offset:mac_offset + SECTOR_SIZE]
    else:
        mac_data = b'\x00' * SECTOR_SIZE

    # ---- Step 7: Assemble the image ----
    print(f"\n[7/7] Assembling SD card image: {args.output}")

    output_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), args.output)
    with open(output_path, 'wb') as f:
        # Create sparse file of target size
        f.seek(image_size_bytes - 1)
        f.write(b'\x00')

        # Write protective MBR (sector 0)
        f.seek(0)
        f.write(mbr)

        # Write primary GPT header (sector 1)
        f.seek(SECTOR_SIZE)
        f.write(primary_hdr)

        # Write primary GPT entries (sector 2+)
        f.seek(2 * SECTOR_SIZE)
        f.write(primary_entries)

        # Write boot0 at sector 16
        f.seek(BOOT0_SECTOR * SECTOR_SIZE)
        f.write(boot0_data)
        print(f"  ✓ boot0 written at sector {BOOT0_SECTOR}")

        # Write boot0 copy at sector 256
        f.seek(BOOT0_COPY_SECTOR * SECTOR_SIZE)
        f.write(boot0_data)
        print(f"  ✓ boot0 copy written at sector {BOOT0_COPY_SECTOR}")

        # Write MAC address area at sector 12288
        f.seek(MAC_SECTOR * SECTOR_SIZE)
        f.write(mac_data)

        # Write sunxi-package at sector 24576
        f.seek(SUNXI_PKG_SECTOR * SECTOR_SIZE)
        f.write(pkg_data)
        print(f"  ✓ sunxi-package written at sector {SUNXI_PKG_SECTOR}")

        # Write env_a partition (modified for Linux boot)
        env_part = None
        for name, start, size in partitions:
            if name == 'env_a':
                f.seek(start * SECTOR_SIZE)
                f.write(env_bin)
                print(f"  ✓ env_a (modified) written at sector {start}")
                break

        # Write boot_a partition (vendor kernel)
        for name, start, size in partitions:
            if name == 'boot_a':
                f.seek(start * SECTOR_SIZE)
                f.write(boot_a)
                print(f"  ✓ boot_a written at sector {start} ({len(boot_a):,} bytes)")
                break

        # Write backup GPT entries and header at end of disk
        entries_sectors = (GPT_MAX_ENTRIES * GPT_ENTRY_SIZE + SECTOR_SIZE - 1) // SECTOR_SIZE
        backup_entries_start = total_sectors - 1 - entries_sectors
        f.seek(backup_entries_start * SECTOR_SIZE)
        f.write(backup_entries)

        f.seek((total_sectors - 1) * SECTOR_SIZE)
        f.write(backup_hdr)
        print(f"  ✓ Backup GPT written at sector {total_sectors - 1}")

    final_size = os.path.getsize(output_path)
    print(f"\n{'=' * 70}")
    print(f"SD card image created successfully!")
    print(f"  File: {output_path}")
    print(f"  Size: {final_size:,} bytes ({final_size / 1048576:.0f} MiB)")
    print(f"{'=' * 70}")
    print()
    print("NEXT STEPS:")
    print("=" * 70)
    print()
    print("1. WRITE IMAGE TO SD CARD:")
    print("   Windows: Use Win32DiskImager or balenaEtcher")
    print(f"   Linux:   sudo dd if={args.output} of=/dev/sdX bs=4M status=progress")
    print()
    print("2. POPULATE ROOTFS (partition 4):")
    print("   The rootfs partition is empty. You need to format it and add a Linux rootfs.")
    print()
    print("   Option A - Alpine Linux (recommended, small):")
    print("     # On Linux/WSL:")
    print("     sudo mkfs.ext4 -L rootfs /dev/sdX4")
    print("     sudo mount /dev/sdX4 /mnt")
    print("     cd /mnt")
    print("     sudo wget https://dl-cdn.alpinelinux.org/alpine/v3.21/releases/armv7/alpine-minirootfs-3.21.3-armv7.tar.gz")
    print("     sudo tar xzf alpine-minirootfs-*.tar.gz")
    print("     sudo rm alpine-minirootfs-*.tar.gz")
    print()
    print("     # Add vendor kernel modules:")
    print("     sudo mkdir -p /mnt/lib/modules/5.15.167")
    print("     sudo tar xzf firmware_dump/vendor_modules.tar.gz -C /mnt/lib/modules/5.15.167/")
    print()
    print("     # Add vendor firmware:")
    print("     sudo mkdir -p /mnt/lib/firmware")
    print("     sudo tar xzf firmware_dump/vendor_firmware.tar.gz -C /mnt/lib/firmware/")
    print()
    print("     # Create init symlink:")
    print("     sudo ln -sf /bin/busybox /mnt/sbin/init")
    print()
    print("     # Configure networking and auto-login:")
    print("     echo 'auto lo' | sudo tee /mnt/etc/network/interfaces")
    print("     echo 'iface lo inet loopback' | sudo tee -a /mnt/etc/network/interfaces")
    print("     echo 'ttyAS0::respawn:/sbin/getty -L ttyAS0 115200 vt100' | sudo tee /mnt/etc/inittab")
    print("     sudo umount /mnt")
    print()
    print("   Option B - Debian/Armbian armhf debootstrap:")
    print("     sudo debootstrap --arch=armhf bookworm /mnt http://deb.debian.org/debian")
    print()
    print("3. INSERT SD CARD AND BOOT:")
    print("   - Power off the projector")
    print("   - Insert the prepared SD card")
    print("   - Power on — BROM will find boot0 on SD and boot from it")
    print("   - To return to Android: power off, remove SD card, power on")
    print()
    print("4. SERIAL CONSOLE (optional but recommended):")
    print("   Connect a 3.3V USB-UART adapter to the ttyAS0 serial port")
    print("   Settings: 115200 baud, 8N1")
    print("   This gives you U-Boot console (bootdelay=3) and Linux shell")
    print()
    print("IMPORTANT NOTES:")
    print("-" * 70)
    print("• SD card MUST be at least 1 GB (2+ GB recommended)")
    print("• This is NON-DESTRUCTIVE — eMMC Android is untouched")
    print("• Removing the SD card restores normal Android boot")
    print("• The vendor kernel is 32-bit ARM (armv7l) — use armhf rootfs")
    print("• bootdelay=3 allows pressing any key to enter U-Boot shell")
    print("• If boot fails, remove SD card and reboot to Android")
    print()


# ============================================================================
# Entry Point
# ============================================================================

if __name__ == '__main__':
    parser = argparse.ArgumentParser(
        description='Build SD card boot image for Orange Box S40 (Allwinner H723)'
    )
    parser.add_argument(
        '--size', type=int, default=DEFAULT_IMAGE_SIZE_MB,
        help=f'SD card image size in MiB (default: {DEFAULT_IMAGE_SIZE_MB})'
    )
    parser.add_argument(
        '--output', type=str, default='sdcard.img',
        help='Output image filename (default: sdcard.img)'
    )
    args = parser.parse_args()

    if args.size < 512:
        print("ERROR: Image size must be at least 512 MiB")
        sys.exit(1)

    build_image(args)
