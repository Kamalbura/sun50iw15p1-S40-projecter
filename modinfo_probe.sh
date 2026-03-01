#!/system/bin/sh
echo "=== MOTOR CONTROL MODULE ==="
modinfo motor_control 2>/dev/null
echo ""
echo "=== MOTOR LIMITER MODULE ==="
modinfo motor_limiter 2>/dev/null
echo ""
echo "=== STMVL53L1 - ToF Sensor ==="
modinfo stmvl53l1 2>/dev/null
echo ""
echo "=== SC7A20E - Accelerometer ==="
modinfo sc7a20e 2>/dev/null
echo ""
echo "=== KXTJ3 - Accelerometer ==="
modinfo kxtj3 2>/dev/null
echo ""
echo "=== SUNXI_KSC - Keystone Correction ==="
modinfo sunxi_ksc 2>/dev/null
echo ""
echo "=== VS_DISPLAY ==="
modinfo vs_display 2>/dev/null
echo ""
echo "=== VS_OSD ==="
modinfo vs_osd 2>/dev/null
echo ""
echo "=== TVPANEL ==="
modinfo tvpanel 2>/dev/null
echo ""
echo "=== SUNXI IR RX ==="
modinfo sunxi_ir_rx 2>/dev/null
echo ""
echo "=== MALI GPU ==="
modinfo mali_kbase 2>/dev/null
echo ""
echo "=== PWM FAN ==="
modinfo pwm_fan 2>/dev/null
echo ""
echo "=== PWM BACKLIGHT ==="
modinfo pwm_bl 2>/dev/null
echo ""
echo "=== BACKLIGHT ==="
modinfo backlight 2>/dev/null
echo ""
echo "=== AIC8800 WiFi ==="
modinfo aic8800_fdrv 2>/dev/null
echo ""
echo "=== HIDTVREG ==="
modinfo hidtvreg_dev 2>/dev/null
echo ""
echo "=== STEPPER MOTOR SCRIPT ==="
cat /system/bin/stepper_motor_test.sh 2>/dev/null
echo ""
echo "=== DEVICE TREE OVERLAYS ==="
find /proc/device-tree -maxdepth 2 -name "compatible" -exec sh -c 'echo "$1:"; cat "$1"; echo' _ {} \; 2>/dev/null | head -50
echo ""
echo "=== DSI/LVDS PANEL DRIVER ==="
modinfo panel_dsi_gen 2>/dev/null
modinfo panel_lvds_gen 2>/dev/null
echo ""
echo "=== PROJECTION SYSFS ==="
find /sys/class/projection -type f -exec sh -c 'echo "$1 = $(cat "$1" 2>/dev/null)"' _ {} \;
echo ""
echo "=== GOV PROJECTOR SYSFS ==="
find /sys/class/gov_projector -type f -exec sh -c 'echo "$1 = $(cat "$1" 2>/dev/null)"' _ {} \; 2>/dev/null
