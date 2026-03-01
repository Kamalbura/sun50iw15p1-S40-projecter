#!/system/bin/sh
# Full partition dump script - creates raw images of all partitions
OUTDIR="/data/local/tmp/fw_dump"
mkdir -p $OUTDIR

echo "=== FULL FIRMWARE DUMP ==="
echo "Output: $OUTDIR"
echo ""

# Partition map
echo "=== PARTITION MAP ===" > $OUTDIR/partition_map.txt
ls -la /dev/block/by-name/ >> $OUTDIR/partition_map.txt 2>&1
cat /proc/partitions >> $OUTDIR/partition_map.txt 2>&1
mount >> $OUTDIR/partition_map.txt 2>&1

# Critical partitions to dump (skip userdata - too large and contains personal data)
# Format: partition_name block_device
PARTITIONS="
bootloader_a:/dev/block/mmcblk0p1
bootloader_b:/dev/block/mmcblk0p2
env_a:/dev/block/mmcblk0p3
env_b:/dev/block/mmcblk0p4
boot_a:/dev/block/mmcblk0p5
boot_b:/dev/block/mmcblk0p6
vendor_boot_a:/dev/block/mmcblk0p7
vendor_boot_b:/dev/block/mmcblk0p8
init_boot_a:/dev/block/mmcblk0p9
init_boot_b:/dev/block/mmcblk0p10
super:/dev/block/mmcblk0p11
misc:/dev/block/mmcblk0p12
vbmeta_a:/dev/block/mmcblk0p13
vbmeta_b:/dev/block/mmcblk0p14
vbmeta_system_a:/dev/block/mmcblk0p15
vbmeta_system_b:/dev/block/mmcblk0p16
vbmeta_vendor_a:/dev/block/mmcblk0p17
vbmeta_vendor_b:/dev/block/mmcblk0p18
frp:/dev/block/mmcblk0p19
empty:/dev/block/mmcblk0p20
metadata:/dev/block/mmcblk0p21
treadahead:/dev/block/mmcblk0p22
private:/dev/block/mmcblk0p23
dtbo_a:/dev/block/mmcblk0p24
dtbo_b:/dev/block/mmcblk0p25
media_data:/dev/block/mmcblk0p26
Reserve0_a:/dev/block/mmcblk0p27
Reserve0_b:/dev/block/mmcblk0p28
"

for entry in $PARTITIONS; do
    name=$(echo $entry | cut -d: -f1)
    dev=$(echo $entry | cut -d: -f2)
    size_blocks=$(cat /proc/partitions | grep "${dev##*/}" | awk '{print $3}')
    size_mb=$((size_blocks / 1024))
    echo "  Dumping $name ($dev) - ${size_mb}MB..."
    dd if=$dev of=$OUTDIR/${name}.img bs=4096 2>/dev/null
    echo "    Done: $(ls -la $OUTDIR/${name}.img | awk '{print $5}') bytes"
done

echo ""
echo "=== DUMPING DEVICE TREE BLOB ==="
dd if=/dev/block/mmcblk0p24 of=$OUTDIR/dtbo_a.img bs=4096 2>/dev/null
echo "Done"

echo ""
echo "=== SAVING SYSTEM PROPERTIES ==="
getprop > $OUTDIR/all_props.txt
echo "Saved all properties"

echo ""
echo "=== SAVING KERNEL CONFIG ==="
cat /proc/config.gz > $OUTDIR/kernel_config.gz 2>/dev/null || echo "No /proc/config.gz"
zcat /proc/config.gz > $OUTDIR/kernel_config.txt 2>/dev/null || echo "Could not decompress"

echo ""
echo "=== SAVING KERNEL MODULES LIST ==="
lsmod > $OUTDIR/lsmod.txt 2>/dev/null || cat /proc/modules > $OUTDIR/modules.txt 2>/dev/null

echo ""
echo "=== SAVING INIT SCRIPTS ==="
mkdir -p $OUTDIR/init_scripts
cp /system/etc/init/*.rc $OUTDIR/init_scripts/ 2>/dev/null
cp /vendor/etc/init/*.rc $OUTDIR/init_scripts/ 2>/dev/null
cp /vendor/etc/init/hw/*.rc $OUTDIR/init_scripts/ 2>/dev/null
cp /system/bin/preinstall $OUTDIR/init_scripts/ 2>/dev/null
cp /system/bin/appsdisable $OUTDIR/init_scripts/ 2>/dev/null
cp /system/bin/oem_preinstall.sh $OUTDIR/init_scripts/ 2>/dev/null
cp /system/bin/copy_rom.sh $OUTDIR/init_scripts/ 2>/dev/null
cp /system/bin/gmsopt $OUTDIR/init_scripts/ 2>/dev/null

echo ""
echo "=== SAVING FSTAB ==="
find / -name "fstab*" -exec cp {} $OUTDIR/ 2>/dev/null \;
cat /vendor/etc/fstab.sun50iw15p1 > $OUTDIR/fstab.txt 2>/dev/null

echo ""
echo "=== LISTING ALL FILES IN DUMP ==="
ls -la $OUTDIR/
du -sh $OUTDIR/

echo ""
echo "=== FIRMWARE DUMP COMPLETE ==="
