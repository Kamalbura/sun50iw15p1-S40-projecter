#!/system/bin/sh
echo "=== DISPLAY DRIVER ==="
ls -la /sys/class/graphics/fb0/ 2>/dev/null
echo ""
echo "--- fb0 info ---"
cat /sys/class/graphics/fb0/mode 2>/dev/null
cat /sys/class/graphics/fb0/modes 2>/dev/null
cat /sys/class/graphics/fb0/virtual_size 2>/dev/null
cat /sys/class/graphics/fb0/bits_per_pixel 2>/dev/null
cat /sys/class/graphics/fb0/stride 2>/dev/null
cat /sys/class/graphics/fb0/name 2>/dev/null

echo ""
echo "=== DISP DRIVER (Allwinner) ==="
find /sys/devices -path "*disp*" -name "*.ko" 2>/dev/null
find /sys/module -name "*disp*" 2>/dev/null | head -10
find /sys/module -name "*sunxi*" 2>/dev/null | head -10
find /sys/module -name "*hdmi*" 2>/dev/null | head -10
find /sys/module -name "*tv*" 2>/dev/null | head -10

echo ""
echo "=== KERNEL MODULES ==="
lsmod 2>/dev/null || cat /proc/modules 2>/dev/null

echo ""
echo "=== PROJECTION/KEYSTONE DRIVER ==="
ls -la /sys/class/projection/ 2>/dev/null
echo ""
for f in $(ls /sys/class/projection/ 2>/dev/null); do
    val=$(cat /sys/class/projection/$f 2>/dev/null)
    echo "  projection/$f = $val"
done

echo ""
echo "=== GOV_PROJECTOR ==="
ls -la /sys/class/gov_projector/ 2>/dev/null
for f in $(ls /sys/class/gov_projector/ 2>/dev/null); do
    val=$(cat /sys/class/gov_projector/$f 2>/dev/null)
    echo "  gov_projector/$f = $val"
done

echo ""
echo "=== DEVICE TREE (display) ==="
find /proc/device-tree -name "*disp*" -o -name "*lcd*" -o -name "*hdmi*" -o -name "*projector*" -o -name "*keystone*" 2>/dev/null | head -20

echo ""
echo "=== /dev/hxext ==="
ls -la /dev/hxext 2>/dev/null
echo "=== /dev/pddev ==="
ls -la /dev/pddev 2>/dev/null

echo ""
echo "=== HDMI CEC ==="
ls -la /dev/cec* 2>/dev/null
find /sys -name "*cec*" -maxdepth 5 2>/dev/null | head -20
dumpsys hdmi_control 2>/dev/null | head -60

echo ""
echo "=== INPUT DEVICES (IR, etc) ==="
cat /proc/bus/input/devices

echo ""
echo "=== IR KEYLAYOUT FILES ==="
find /system /vendor -name "*.kl" 2>/dev/null

echo ""
echo "=== STEPPER MOTOR (Auto Focus/Keystone) ==="
find /sys -name "*stepper*" -o -name "*motor*" 2>/dev/null | head -10
cat /sys/class/projection/adc_value 2>/dev/null
cat /sys/class/projection/adc_ctl_enable 2>/dev/null

echo ""
echo "=== WIFI CHIP ==="
find /sys/module -name "*aic*" -o -name "*8800*" 2>/dev/null | head -10
getprop wifi.interface
getprop wlan.driver.vendor

echo ""
echo "=== THERMAL ==="
for tz in /sys/class/thermal/thermal_zone*/; do
    type=$(cat ${tz}type 2>/dev/null)
    temp=$(cat ${tz}temp 2>/dev/null)
    echo "  $type: $temp"
done

echo ""
echo "=== POWER ==="
cat /sys/class/power_supply/*/type 2>/dev/null
dumpsys battery 2>/dev/null | head -10

echo ""
echo "=== VIDEO DEVICES ==="
ls -la /dev/video* 2>/dev/null
v4l2-ctl --list-devices 2>/dev/null

echo ""
echo "=== ALLWINNER SPECIFIC ==="
cat /proc/sunxi_ver 2>/dev/null
find /sys -name "*allwinner*" -o -name "*sunxi*" 2>/dev/null | head -20
