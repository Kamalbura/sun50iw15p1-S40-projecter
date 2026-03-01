#!/system/bin/sh
OUTDIR="/data/local/tmp/fw_dump"
mkdir -p $OUTDIR

echo "=== FULL FIRMWARE DUMP ==="

# Save partition map first
ls -la /dev/block/by-name/ > $OUTDIR/partition_map.txt 2>&1
cat /proc/partitions >> $OUTDIR/partition_map.txt 2>&1
mount >> $OUTDIR/partition_map.txt 2>&1

# Dump each partition
echo "  Dumping bootloader_a..."
dd if=/dev/block/mmcblk0p1 of=$OUTDIR/bootloader_a.img bs=4096 2>/dev/null
echo "  Dumping bootloader_b..."
dd if=/dev/block/mmcblk0p2 of=$OUTDIR/bootloader_b.img bs=4096 2>/dev/null
echo "  Dumping env_a..."
dd if=/dev/block/mmcblk0p3 of=$OUTDIR/env_a.img bs=4096 2>/dev/null
echo "  Dumping env_b..."
dd if=/dev/block/mmcblk0p4 of=$OUTDIR/env_b.img bs=4096 2>/dev/null
echo "  Dumping boot_a..."
dd if=/dev/block/mmcblk0p5 of=$OUTDIR/boot_a.img bs=4096 2>/dev/null
echo "  Dumping boot_b..."
dd if=/dev/block/mmcblk0p6 of=$OUTDIR/boot_b.img bs=4096 2>/dev/null
echo "  Dumping vendor_boot_a..."
dd if=/dev/block/mmcblk0p7 of=$OUTDIR/vendor_boot_a.img bs=4096 2>/dev/null
echo "  Dumping vendor_boot_b..."
dd if=/dev/block/mmcblk0p8 of=$OUTDIR/vendor_boot_b.img bs=4096 2>/dev/null
echo "  Dumping init_boot_a..."
dd if=/dev/block/mmcblk0p9 of=$OUTDIR/init_boot_a.img bs=4096 2>/dev/null
echo "  Dumping init_boot_b..."
dd if=/dev/block/mmcblk0p10 of=$OUTDIR/init_boot_b.img bs=4096 2>/dev/null
echo "  Dumping super (3.5GB - this will take a while)..."
dd if=/dev/block/mmcblk0p11 of=$OUTDIR/super.img bs=65536 2>/dev/null
echo "  Dumping misc..."
dd if=/dev/block/mmcblk0p12 of=$OUTDIR/misc.img bs=4096 2>/dev/null
echo "  Dumping vbmeta_a..."
dd if=/dev/block/mmcblk0p13 of=$OUTDIR/vbmeta_a.img bs=4096 2>/dev/null
echo "  Dumping vbmeta_b..."
dd if=/dev/block/mmcblk0p14 of=$OUTDIR/vbmeta_b.img bs=4096 2>/dev/null
echo "  Dumping vbmeta_system_a..."
dd if=/dev/block/mmcblk0p15 of=$OUTDIR/vbmeta_system_a.img bs=4096 2>/dev/null
echo "  Dumping vbmeta_system_b..."
dd if=/dev/block/mmcblk0p16 of=$OUTDIR/vbmeta_system_b.img bs=4096 2>/dev/null
echo "  Dumping vbmeta_vendor_a..."
dd if=/dev/block/mmcblk0p17 of=$OUTDIR/vbmeta_vendor_a.img bs=4096 2>/dev/null
echo "  Dumping vbmeta_vendor_b..."
dd if=/dev/block/mmcblk0p18 of=$OUTDIR/vbmeta_vendor_b.img bs=4096 2>/dev/null
echo "  Dumping frp..."
dd if=/dev/block/mmcblk0p19 of=$OUTDIR/frp.img bs=4096 2>/dev/null
echo "  Dumping dtbo_a..."
dd if=/dev/block/mmcblk0p24 of=$OUTDIR/dtbo_a.img bs=4096 2>/dev/null
echo "  Dumping dtbo_b..."
dd if=/dev/block/mmcblk0p25 of=$OUTDIR/dtbo_b.img bs=4096 2>/dev/null
echo "  Dumping private..."
dd if=/dev/block/mmcblk0p23 of=$OUTDIR/private.img bs=4096 2>/dev/null
echo "  Dumping metadata..."
dd if=/dev/block/mmcblk0p21 of=$OUTDIR/metadata.img bs=4096 2>/dev/null

echo ""
echo "=== SAVING CONFIGS ==="
getprop > $OUTDIR/all_props.txt
cat /proc/config.gz > $OUTDIR/kernel_config.gz 2>/dev/null
cat /proc/modules > $OUTDIR/modules.txt 2>/dev/null

mkdir -p $OUTDIR/init_scripts
cp /system/etc/init/*.rc $OUTDIR/init_scripts/ 2>/dev/null
cp /vendor/etc/init/*.rc $OUTDIR/init_scripts/ 2>/dev/null
cp /vendor/etc/init/hw/*.rc $OUTDIR/init_scripts/ 2>/dev/null
cp /system/bin/preinstall $OUTDIR/init_scripts/ 2>/dev/null
cp /system/bin/appsdisable $OUTDIR/init_scripts/ 2>/dev/null
cp /system/bin/oem_preinstall.sh $OUTDIR/init_scripts/ 2>/dev/null
cp /system/bin/copy_rom.sh $OUTDIR/init_scripts/ 2>/dev/null
cp /system/bin/gmsopt $OUTDIR/init_scripts/ 2>/dev/null
cat /vendor/etc/fstab.sun50iw15p1 > $OUTDIR/fstab.txt 2>/dev/null

echo ""
echo "=== DUMP SIZES ==="
ls -lh $OUTDIR/*.img 2>/dev/null
du -sh $OUTDIR/

echo ""
echo "=== FIRMWARE DUMP COMPLETE ==="
