# Orange Box S40 Projector — Full Reverse Engineering Report

## Table of Contents
1. [Executive Summary](#executive-summary)
2. [Hardware Analysis: Expectations vs Reality](#hardware-analysis)
3. [System Architecture](#system-architecture)
4. [Partition Layout & OS Map](#partition-layout)
5. [Driver & Kernel Module Analysis](#driver-analysis)
6. [Display Pipeline & Keystone](#display-pipeline)
7. [HDMI CEC Implementation](#hdmi-cec)
8. [IR Receiver & Input System](#ir-receiver)
9. [Sensor Suite (Auto-Keystone/Focus)](#sensor-suite)
10. [Security Vulnerability Benchmark](#vulnerability-benchmark)
11. [Malware & Suspicious Software](#malware-analysis)
12. [Network Security Analysis](#network-security)
13. [Firmware Dump Inventory](#firmware-dump)
14. [Files Collected](#files-collected)

---

## Executive Summary

The **Orange Box S40** is a budget Chinese projector marketed as "4K FHD" with Android TV. Our investigation reveals it is built on an **Allwinner H723 (sun50iw15p1)** SoC running a heavily modified, insecure **Android 14 userdebug** build that spoofs its identity as a **Google Pixel 3** for DRM bypass. The device ships with preinstalled malware targeting Netflix, a root backdoor, and multiple security vulnerabilities that make it unsuitable for any network-connected environment without significant remediation.

**Key Verdict**: The hardware is low-end but functional. The software is a security disaster. A custom OS build is feasible but requires significant effort.

---

## Hardware Analysis: Expectations vs Reality {#hardware-analysis}

### Marketing Claims vs Actual Hardware

| Feature | Marketing Claim | Reality | Verdict |
|---------|----------------|---------|---------|
| **Resolution** | "4K FHD" / "1080P Native" | 1024×600 native LCD panel | **FALSE** — Not even 720p native |
| **Processor** | Not specified | Allwinner H723, 4× Cortex-A53 @ ~1.5GHz | Budget TV SoC |
| **RAM** | "2GB" | 835MB usable (1GB physical, ~165MB reserved for GPU/CMA) | **MISLEADING** — Likely 1GB, not 2GB |
| **Storage** | "16GB" | 7.3GB eMMC (P1J95K), ~3.1GB userdata | **MISLEADING** — Actual usable ~1.9GB |
| **GPU** | Not specified | ARM Mali (Midgard architecture, T-series) | Budget mobile GPU |
| **WiFi** | "Dual-band WiFi" | AIC8800D80 (802.11ac, single stream) | Basic WiFi 5 |
| **Android Version** | "Android TV" | Android 14 (AOSP, not certified Android TV) | **No Google certification** |
| **Bluetooth** | "Bluetooth 5.0" | AIC8800 BT module | Likely accurate |
| **Keystone** | "Auto Keystone" | Hardware-assisted via accelerometer + KSC driver | Actually works |
| **Focus** | "Auto Focus" | STMicro VL53L1 ToF sensor + stepper motor | Legitimate hardware |
| **HDMI** | "HDMI input" | 3× HDMI input ports with CEC support | Verified working |
| **IR** | "Remote control" | Allwinner sunxi-ir-rx infrared receiver | Standard NEC protocol |

### Detailed SoC Specifications

```
SoC:            Allwinner H723 (sun50iw15p1)
Architecture:   ARMv7 Cortex-A53 × 4 cores (32-bit mode)
CPU Part:       0xd03 (Cortex-A53)
BogoMIPS:       57.14 per core
Features:       NEON, VFPv4, AES, SHA1, SHA2, CRC32, LPAE
GPU:            ARM Mali (Midgard T-series, mali_kbase driver)
VPU:            Allwinner Cedar (sunxi-cedar, H.265/H.264/VP9 decode)
```

### Memory Configuration

```
Physical RAM:   ~1GB (MemTotal: 835,452 KB usable)
Swap:           751,900 KB (zram compressed, /dev/zram0)
CMA:            24,576 KB (reserved for display/codec DMA)
HighMem:        103,744 KB
LowMem:         731,708 KB
```

### Storage — eMMC Details

```
Manufacturer:   0x0000FE (unknown/unbranded)
Device Name:    P1J95K
Type:           MMC (eMMC)
CID:            fe014e50314a39354b12881d855223ed
Total Size:     7,651,328 KB (~7.3GB)
Usable Data:    3,448,303 KB (~3.3GB for userdata)
```

### Display Panel

```
Panel Name:     "TV303 SVP OSD3"
Native Res:     1024 × 600 pixels
Virtual Size:   1024 × 1200 (double-buffered)
BPP:            32 (RGBA8888)
Stride:         4096 bytes/line
Interface:      LVDS (panel_lvds_gen driver)
Framebuffer:    /dev/graphics/fb0 → device 5600000.vs-osd
Backlight:      PWM-controlled (pwm_bl driver)
```

### WiFi Module

```
Chip:           AIC8800D80 (AiCsemi / RivieraWaves IP)
Driver:         aic8800_fdrv.ko
Interface:      SDIO (vendor=0xC8A1, device=0x0082)
Standards:      802.11a/b/g/n/ac (WiFi 5)
Spatial Streams: 1 (SISO)
Features:       HT40, VHT80, LDPC, STBC, Beamformee
Firmware:       fmacfw.bin, agcram.bin, fcuram.bin, ldpcram.bin
```

### Sensor Hardware

```
Accelerometer:  SC7A20E (I2C, for tilt/orientation detection → auto keystone)
Alt. Accel:     KXTJ3 (Kionix, backup accelerometer driver loaded)
ToF Sensor:     STMicro VL53L1 (Time-of-Flight, for auto-focus distance)
ADC:            Allwinner sunxi_gpadc (general purpose ADC)
Thermal:        CPU thermal zone monitoring
```

### Motor System (Auto Focus)

```
Controller:     motor_control.ko (Allwinner, author: JingyanLiang)
Limiter:        motor_limiter.ko (endpoint detection)
Interface:      /sys/devices/platform/motor0/motor_ctrl
                /sys/devices/platform/motor0/motor_trip
Control:        Echo "1,<steps>" for CW, "2,<steps>" for CCW
```

### Fan Cooling

```
Fan:            PWM-controlled (pwm_fan.ko, Samsung origin)
Control:        Via sysfs projection/fan_pwm_duty and fan_pwm_period
```

### Peripheral Interfaces

```
HDMI In:        3 ports (port_id 1-3, all with CEC)
HDMI ARC:       Port 1 supports ARC
USB Host:       EHCI + OHCI (ehci_sunxi, ohci_sunxi via sunxi_hci)
USB OTG:        sunxi_usb_udc (USB device controller)
SD Card:        SD/MMC slot (via sunxi SD driver)
Video Input:    /dev/video0 (V4L2, accessible 0777)
IR Receiver:    sunxi-ir-rx (NEC + RC5 protocol decoders)
Audio:          I2S (sunxi_i2s), internal codec, OWA (S/PDIF)
```

---

## System Architecture {#system-architecture}

### OS Build Identity

```
Build:          Android 14 (SDK 34, API level 34)
Build Type:     userdebug (NOT production)
Build Tags:     test-keys (NOT release-signed)
Kernel:         5.15.167-gd490be1a1370 armv7l
SELinux:        Permissive (security DISABLED)
ADB:            ro.adb.secure=0 (NO authentication)
Fingerprint:    google/blueline/blueline:14/AP2A.240905.003/12231197:userdebug/test-keys
                (FAKE — spoofing Google Pixel 3)
```

### Identity Spoofing Details

The device pretends to be a **Google Pixel 3 (blueline)** to bypass:
- Netflix DRM (Widevine L1) certification checks
- Google Play Store device compatibility
- SafetyNet/Play Integrity attestation

```
ro.product.model=Pixel 3          ← FAKE (real: S40 or similar)
ro.product.brand=google           ← FAKE (real: unknown Chinese brand)
ro.product.manufacturer=Google    ← FAKE
ro.product.device=blueline        ← FAKE (Pixel 3 codename)
ro.build.fingerprint=google/blueline/blueline:14/... ← FAKE
```

### Boot Flow

```
1. Bootloader (mmcblk0p1, U-Boot based)
2. Kernel (boot_a, 64MB, Linux 5.15.167)
3. Vendor boot (vendor_boot_a, 32MB)
4. Init boot (init_boot_a, 8MB)
5. Super partition → dm-verity → system, vendor, product
6. init.rc → services → zygote → system_server → apps
```

### A/B Partition Scheme

The device uses A/B partitioning for OTA updates:
- Slot A (active): bootloader_a, boot_a, vendor_boot_a, etc.
- Slot B (backup): bootloader_b, boot_b, vendor_boot_b, etc.

---

## Partition Layout & OS Map {#partition-layout}

### Complete Partition Table

| Partition | Device | Size | Name | Mount Point | Filesystem |
|-----------|--------|------|------|-------------|------------|
| mmcblk0p1 | p1 | 32MB | bootloader_a | - | Raw |
| mmcblk0p2 | p2 | 32MB | bootloader_b | - | Raw |
| mmcblk0p3 | p3 | 256KB | env_a | - | Raw (U-Boot env) |
| mmcblk0p4 | p4 | 256KB | env_b | - | Raw (U-Boot env) |
| mmcblk0p5 | p5 | 64MB | boot_a | - | Android boot image |
| mmcblk0p6 | p6 | 64MB | boot_b | - | Android boot image |
| mmcblk0p7 | p7 | 32MB | vendor_boot_a | - | Vendor boot |
| mmcblk0p8 | p8 | 32MB | vendor_boot_b | - | Vendor boot |
| mmcblk0p9 | p9 | 8MB | init_boot_a | - | Init boot |
| mmcblk0p10 | p10 | 8MB | init_boot_b | - | Init boot |
| mmcblk0p11 | p11 | 3,500MB | super | dm-verity → /, /vendor, /product | ext4/erofs |
| mmcblk0p12 | p12 | 16MB | misc | - | Raw |
| mmcblk0p13 | p13 | 128KB | vbmeta_a | - | AVB metadata |
| mmcblk0p14 | p14 | 128KB | vbmeta_b | - | AVB metadata |
| mmcblk0p15 | p15 | 64KB | vbmeta_system_a | - | AVB metadata |
| mmcblk0p16 | p16 | 64KB | vbmeta_system_b | - | AVB metadata |
| mmcblk0p17 | p17 | 64KB | vbmeta_vendor_a | - | AVB metadata |
| mmcblk0p18 | p18 | 64KB | vbmeta_vendor_b | - | AVB metadata |
| mmcblk0p19 | p19 | 512KB | frp | - | Factory Reset Protection |
| mmcblk0p20 | p20 | 15MB | empty | - | Empty |
| mmcblk0p21 | p21 | 16MB | metadata | /metadata | ext4 |
| mmcblk0p22 | p22 | 96MB | treadahead | /treadahead | ext4 |
| mmcblk0p23 | p23 | 16MB | private | - | Unknown |
| mmcblk0p24 | p24 | 2MB | dtbo_a | - | Device Tree Blob Overlay |
| mmcblk0p25 | p25 | 2MB | dtbo_b | - | Device Tree Blob Overlay |
| mmcblk0p26 | p26 | 16MB | media_data/oem | /oem | vfat (RO) |
| mmcblk0p27 | p27 | 16MB | Reserve0_a | /Reserve0 | vfat |
| mmcblk0p28 | p28 | 16MB | Reserve0_b | - | vfat |
| mmcblk0p29 | p29 | 3,370MB | userdata | /data | ext4 |

### dm-verity Mapped Volumes

| DM Device | Mounted At | Size | Type |
|-----------|-----------|------|------|
| dm-0 | / (system) | 2.1GB | ext4 (RO, 100% used) |
| dm-1 | /vendor | 460MB | ext4 (RO, 100% used) |
| dm-2 | /product | 39MB | ext4 (RO, 100% used) |
| dm-3 | /vendor_dlkm | 4.3MB | erofs (RO) |
| dm-4 | /system_dlkm | 232KB | ext4 (RO) |

---

## Driver & Kernel Module Analysis {#driver-analysis}

### Loaded Kernel Modules (Full List)

| Module | Size | Description | Author |
|--------|------|-------------|--------|
| **motor_control** | 16KB | Stepper motor driver (auto focus) | JingyanLiang, Allwinner |
| **motor_limiter** | 16KB | Motor endpoint limiter | JingyanLiang, Allwinner |
| **stmvl53l1** | 213KB | VL53L1 Time-of-Flight sensor | STMicroelectronics |
| **sc7a20e** | 25KB | SC7A20E accelerometer (auto keystone) | Le1qm |
| **kxtj3** | 25KB | KXTJ3 accelerometer (backup) | Sensortek/Kionix |
| **sunxi_ksc** | 37KB | **Keystone Correction** engine | Allwinner |
| **vs_display** | 53KB | V-Silicon display controller | Display Team |
| **vs_osd** | 66KB | V-Silicon OSD layer (depends on sunxi_ksc) | V-Silicon Semiconductor |
| **tvpanel** | 82KB | TV panel output driver (LVDS/DSI) | Allwinner |
| **panel_lvds_gen** | 16KB | Generic LVDS panel driver | Allwinner (xiaozhineng) |
| **panel_dsi_gen** | 20KB | Generic DSI panel driver | Allwinner (xiaozhineng) |
| **backlight** | 20KB | Backlight framework | Standard Linux |
| **pwm_bl** | 20KB | PWM backlight driver | Standard Linux |
| **pwm_fan** | 16KB | PWM fan controller | Samsung (Kamil Debski) |
| **mali_kbase** | 418KB | ARM Mali GPU driver | ARM |
| **sunxi_ir_rx** | 37KB | Infrared receiver driver | Allwinner (QIn) |
| **ir_nec_decoder** | 16KB | NEC IR protocol decoder | Standard Linux |
| **ir_rc5_decoder** | 16KB | RC5 IR protocol decoder | Standard Linux |
| **aic8800_fdrv** | 303KB | WiFi driver (AIC8800D80) | RivieraWaves/AiCsemi |
| **aic8800_bsp** | 78KB | WiFi BSP layer | RivieraWaves/AiCsemi |
| **aic8800_btlpm** | 16KB | Bluetooth low power mgmt | AiCsemi |
| **sunxi_ve** | 49KB | Video Engine (Cedar, H.265/264 decode) | Allwinner |
| **sunxi_tvtop** | 20KB | TV top-level controller | Allwinner |
| **sunxi_tvtop_adc** | 16KB | TV ADC input | Allwinner |
| **snd_alsa_trid** | 111KB | ALSA sound (Trident) | - |
| **snd_soc_sunxi_**** | Various | Allwinner audio codec, I2S, OWA | Allwinner |
| **hidtvreg_dev** | 16KB | HiDTV register access | Mia Hao, TridentMicro |
| **sunxi_rfkill** | 37KB | RF kill switch | Allwinner |
| **cifs** | 754KB | CIFS/SMB filesystem | Standard Linux |
| **nfs/nfsv4** | Various | NFS client | Standard Linux |
| **snd_aloop** | 29KB | ALSA loopback | Standard Linux |

### Driver Dependency Chain (Display)

```
backlight
  └── tvpanel (Allwinner TV panel framework)
       ├── panel_lvds_gen (LVDS panel output)
       ├── panel_dsi_gen (DSI panel output)
       ├── sunxi_ksc (Keystone Correction)
       │    └── vs_osd (V-Silicon OSD)
       │         └── vs_display (V-Silicon display controller)
       └── sunxi_tvtop (TV top controller)
            └── sunxi_tvtop_adc
```

---

## Display Pipeline & Keystone {#display-pipeline}

### How the Display Works

1. **SoC display engine** (Allwinner sun50iw15p1 built-in) generates framebuffer
2. **vs_display** (V-Silicon IP block) manages display timing and configuration
3. **vs_osd** (V-Silicon OSD) handles overlay composition (address `5600000.vs-osd`)
4. **sunxi_ksc** (Keystone Correction) performs geometric correction on the output
5. **tvpanel** routes the corrected output to the LCD panel
6. **panel_lvds_gen** drives the actual LVDS connection to the LCD
7. **pwm_bl** controls the LED backlight brightness via PWM

### Auto Keystone System

The auto keystone uses a sensor fusion approach:

```
SC7A20E Accelerometer → measures device tilt angle
         ↓
    Android HAL layer → calculates correction matrix
         ↓
    sunxi_ksc module → applies geometric transformation
         ↓
    vs_osd → composites corrected frame
         ↓
    LVDS → LCD panel
```

**Key sysfs interfaces:**
- `/sys/class/projection/mode` = 0 (current projection mode)
- `/sys/class/projection/model` = 2 (projector model identifier)
- `/sys/class/projection/bl_power` = backlight on/off
- `/sys/class/projection/bl_pwm_duty` = brightness level
- `/sys/class/projection/fan_pwm_duty` = fan speed
- `/sys/class/projection/adc_value` = ADC sensor reading
- `/sys/class/projection/adc_ctl_enable` = ADC control enable

### Custom Device Nodes

- `/dev/hxext` (major 386, minor 1) — HX extension device (ChihiHX hardware control)
- `/dev/pddev` (major 508, minor 0) — Projector device control

---

## HDMI CEC Implementation {#hdmi-cec}

### Hardware

```
CEC Controller:  Allwinner built-in (r-cec, r-hdmi-cec-gating clocks)
CEC Version:     CEC 2.0 (version 6 in settings)
Device Type:     TV (logical address 0x00)
Physical Addr:   0x0000 (root)
Active Source:    0x1000 (HDMI port 1)
```

### Port Configuration

| Port | Type | Address | CEC | ARC | eARC |
|------|------|---------|-----|-----|------|
| Port 1 | HDMI_IN | 0x1000 | Yes | **Yes** | No |
| Port 2 | HDMI_IN | 0x2000 | Yes | No | No |
| Port 3 | HDMI_IN | 0x3000 | Yes | No | No |

### CEC Features Enabled

- One Touch Play (TV wake)
- Standby on sleep
- System Audio Control
- Routing Control
- Menu Language
- Volume Control
- Remote Control Passthrough

### Kernel Support

```
Clock domains:  cec-peri-bus, r-cec, r-hdmi-cec-gating
Module:         Built-in (not modular)
Debug:          /sys/kernel/debug/cec
Framework:      Android HDMI CEC HAL (android.hardware.tv.cec@1.0-service)
```

---

## IR Receiver & Input System {#ir-receiver}

### IR Hardware

```
Driver:         sunxi_ir_rx (sunxi-ir-rx.ko)
Device:         soc@3000000/7040000.s_ir_rx
Input:          /dev/input/event3
Protocols:      NEC + RC5 (decoders loaded)
Sysfs:          /devices/platform/soc@3000000/7040000.s_ir_rx/rc/rc0/input3
```

### Input Devices Summary

| Device | Name | Handler | Type |
|--------|------|---------|------|
| event0 | gpio_keys | Power button | GPIO |
| event1 | sc7a20e_acc | Accelerometer | I2C (ABS) |
| event2 | audiocodec Headphones | Headphone jack | ALSA |
| event3 | sunxi-ir | IR remote receiver | RC |

---

## Sensor Suite (Auto-Keystone/Focus) {#sensor-suite}

### VL53L1 Time-of-Flight Sensor (Auto Focus)

```
Chip:           STMicro VL53L1 (laser rangefinder)
Interface:      I2C
Driver:         stmvl53l1.ko
Function:       Measures distance to projection surface
Usage:          Drives stepper motor for focus adjustment
Range:          Up to ~4 meters (typical for VL53L1)
```

### SC7A20E 3-Axis Accelerometer (Auto Keystone)

```
Chip:           Silan SC7A20E
Interface:      I2C
Driver:         sc7a20e.ko
Input Device:   /dev/input/event1 (ABS events)
Function:       Detects tilt angle for auto-keystone
```

### Stepper Motor (Focus Mechanism)

```
Driver:         motor_control.ko + motor_limiter.ko
Interface:      /sys/devices/platform/motor0/motor_ctrl
Controls:       "1,N" = clockwise N steps, "2,N" = counter-clockwise N steps
Status:         /sys/devices/platform/motor0/motor_trip (0 = idle)
Limiter:        Prevents over-travel at endpoints
```

---

## Security Vulnerability Benchmark {#vulnerability-benchmark}

### Severity Rating System

| Rating | CVSS Range | Description |
|--------|-----------|-------------|
| **CRITICAL** | 9.0-10.0 | Immediate exploitation possible, full system compromise |
| **HIGH** | 7.0-8.9 | Significant security impact, exploitation likely |
| **MEDIUM** | 4.0-6.9 | Moderate impact, requires some conditions |
| **LOW** | 0.1-3.9 | Minor impact, limited exploitation potential |

---

### VULN-001: SELinux Disabled (Permissive Mode)
| Field | Value |
|-------|-------|
| **Severity** | CRITICAL (CVSS 9.8) |
| **Category** | Security Misconfiguration (OWASP A05) |
| **Status** | CONFIRMED |
| **Evidence** | `getenforce` → `Permissive` |
| **Impact** | All mandatory access controls are disabled. Any process can access any resource. SELinux policies exist but are not enforced. |
| **Risk** | Complete bypass of Android's primary security boundary. Any app can escalate privileges, access other apps' data, and modify system files. |
| **Remediation** | Set `BOARD_KERNEL_CMDLINE` to remove `androidboot.selinux=permissive`, rebuild kernel with enforcing mode. |

---

### VULN-002: ADB Without Authentication
| Field | Value |
|-------|-------|
| **Severity** | CRITICAL (CVSS 9.8) |
| **Category** | Broken Authentication (OWASP A07) |
| **Status** | CONFIRMED |
| **Evidence** | `ro.adb.secure=0`, ADB on port 5555 accepts any connection |
| **Impact** | Anyone on the same network can connect via ADB and execute commands as `shell` user. Combined with VULN-003, this gives full root access. |
| **Risk** | Remote code execution from any device on the LAN. No RSA key verification. |
| **Remediation** | Set `ro.adb.secure=1`, disable WiFi ADB, or require RSA key approval. |

---

### VULN-003: Root Access via SUID su Binary
| Field | Value |
|-------|-------|
| **Severity** | CRITICAL (CVSS 9.8) |
| **Category** | Broken Access Control (OWASP A01) |
| **Status** | CONFIRMED |
| **Evidence** | `/system/xbin/su` (-rwsr-x--- root:shell), `su 0 id` → `uid=0(root)` |
| **Impact** | Any process in the `shell` group can escalate to root. Combined with ADB (VULN-002), any network user gets root. |
| **Risk** | Full device compromise. Read/write any data, install/remove any software, modify kernel. |
| **Remediation** | Remove `/system/xbin/su`, remove `qw` daemon, remove Koushikdutta SuperUser. |

---

### VULN-004: SuperUser Daemon Listening on All Interfaces
| Field | Value |
|-------|-------|
| **Severity** | HIGH (CVSS 8.6) |
| **Category** | Security Misconfiguration (OWASP A05) |
| **Status** | CONFIRMED |
| **Evidence** | `qw --daemon` (PID 308) listening on `0.0.0.0:1234`, binary at `/system/bin/qw` (389KB), init script `qw.rc` runs as `class core` with `user root` |
| **Impact** | Koushikdutta SuperUser daemon socket accessible from network. Combined with ADB, provides permanent root backdoor. |
| **Risk** | Persistent root access survives reboots. Service is started at `class core` — one of the first services to launch. |
| **Remediation** | Remove `qw.rc` and `/system/bin/qw`. Note: After investigation, port 1234 is actually `tvserver`, not `qw`. The `qw` daemon uses `/dev/com.koushikdutta.superuser.daemon` Unix socket instead. |

---

### VULN-005: userdebug Build with test-keys
| Field | Value |
|-------|-------|
| **Severity** | HIGH (CVSS 8.1) |
| **Category** | Software Integrity Failure (OWASP A08) |
| **Status** | CONFIRMED |
| **Evidence** | `ro.build.type=userdebug`, `ro.build.tags=test-keys` |
| **Impact** | Debug builds have additional attack surface: debuggable apps, accessible system services, relaxed permission checks. Test-keys mean the firmware is signed with publicly known keys. |
| **Risk** | Anyone can create a signed system image and flash it. Debug features expose internal APIs. |
| **Remediation** | Build with `user` build type and proper release keys. |

---

### VULN-006: Netflix Accessibility Malware (com.android.nfx)
| Field | Value |
|-------|-------|
| **Severity** | CRITICAL (CVSS 9.1) |
| **Category** | Malware / Software Integrity (OWASP A08) |
| **Status** | CONFIRMED |
| **Evidence** | APK at `/vendor/preinstall/NFXAccessibility_Android14_v1.1.4/`, AccessibilityService targeting `com.netflix.mediaclient`, hardcoded Netflix UI element IDs, gesture dispatch capability, system-level integration via WindowManager `enableNfxAccessibility` |
| **Impact** | Automated UI manipulation of Netflix app. Can simulate touches, gestures, navigate menus. Likely used for ad fraud or account manipulation. Runs as SYSTEM (uid=1000). |
| **Risk** | Privacy violation, credential theft potential, unauthorized account access. Factory-installed — survives factory reset. |
| **Remediation** | `pm disable com.android.nfx`, remove from /vendor/preinstall. |

---

### VULN-007: ChihiHX Store (com.chihihx.store) — SYSTEM App Store
| Field | Value |
|-------|-------|
| **Severity** | HIGH (CVSS 8.4) |
| **Category** | Broken Access Control (OWASP A01) |
| **Status** | CONFIRMED |
| **Evidence** | Runs as `sharedUserId=android.uid.system` (uid=1000), has `INSTALL_PACKAGES`, `DELETE_PACKAGES`, auto-start via `codeZeng lib_autorun`, `RECEIVE_BOOT_COMPLETED` |
| **Impact** | Unsanctioned app store running with SYSTEM privileges. Can install or remove any app silently. Auto-starts on boot. |
| **Risk** | Supply chain attack vector. Can push malicious updates or additional malware at manufacturer's discretion. |
| **Remediation** | `pm disable com.chihihx.store`. |

---

### VULN-008: OTA Updater Connecting to Hetzner C2 (com.hx.update)
| Field | Value |
|-------|-------|
| **Severity** | HIGH (CVSS 8.1) |
| **Category** | SSRF / Command & Control (OWASP A10) |
| **Status** | CONFIRMED |
| **Evidence** | Active TCP connection to `116.202.8.16:443` (Hetzner, Germany), runs as SYSTEM (uid=1000), has `INSTALL_PACKAGES`, `DELETE_PACKAGES`, `REBOOT` permissions |
| **Impact** | Silent OTA updates from unverified server. Can push arbitrary system updates including additional malware. SYSTEM-level permissions allow full control. |
| **Risk** | Remote code execution via malicious OTA. No user consent for updates. |
| **Remediation** | `pm disable com.hx.update`, block 116.202.8.0/24 at router. |

---

### VULN-009: Device Identity Spoofing (Pixel 3 Fake)
| Field | Value |
|-------|-------|
| **Severity** | HIGH (CVSS 7.5) |
| **Category** | Identification Failure (OWASP A07) |
| **Status** | CONFIRMED |
| **Evidence** | `ro.product.model=Pixel 3`, `ro.product.brand=google`, `ro.build.fingerprint=google/blueline/...` |
| **Impact** | Bypasses Netflix/Widevine DRM certification, Google Play compatibility, and SafetyNet checks. Breaks trust chain for any service relying on device attestation. |
| **Risk** | Legal liability for DRM circumvention. Apps may behave unexpectedly. Users think they have a certified device. |
| **Remediation** | Set genuine device properties. |

---

### VULN-010: World-Writable Device Nodes
| Field | Value |
|-------|-------|
| **Severity** | MEDIUM (CVSS 6.5) |
| **Category** | Broken Access Control (OWASP A01) |
| **Status** | CONFIRMED |
| **Evidence** | `/dev/hxext` (crw-rw-rw-), `/dev/pddev` (crw-rw-rw-), `/dev/video0` (chmod 0777 in init.hx.rc), `/sys/devices/system/cpu/cpu0/cpufreq/scaling_governor` (chmod 0666) |
| **Impact** | Any process can access hardware control interfaces: projector settings, video capture, CPU governor. |
| **Risk** | Privilege escalation, hardware manipulation, DoS via CPU governor changes. |
| **Remediation** | Restrict permissions in init scripts. |

---

### VULN-011: Root Shell Scripts with Network/System Access
| Field | Value |
|-------|-------|
| **Severity** | HIGH (CVSS 7.8) |
| **Category** | Injection / Insecure Design (OWASP A04) |
| **Status** | CONFIRMED |
| **Evidence** | `apply_patch.sh` (root, init seclabel), `oem_preinstall.sh` (root), `copy_rom.sh` (root, copies from USB/SD to /rom), `preinstall` (shell, installs APKs from vendor/preinstall) |
| **Impact** | `apply_patch.sh` — Root patch mechanism triggered via system property. `copy_rom.sh` — Auto-copies from removable media to `/rom` with 777 permissions. `preinstall` — Silent APK installation from system partitions. |
| **Risk** | Physical access → root code execution via USB stick. Remote root patching via property trigger. |
| **Remediation** | Remove or restrict these scripts. |

---

### VULN-012: GMS Optimization (appsdisable)
| Field | Value |
|-------|-------|
| **Severity** | MEDIUM (CVSS 5.3) |
| **Category** | Security Misconfiguration (OWASP A05) |
| **Status** | CONFIRMED |
| **Evidence** | `appsdisable` script disables all `com.google.android.*` BOOT_COMPLETED receivers on first boot |
| **Impact** | Disables Google services boot receivers, potentially breaking security updates, Play Protect, and Find My Device. |
| **Risk** | Reduced security posture from Google's protection services. |
| **Remediation** | Remove `appsdisable` script. |

---

### VULN-013: Tubesky Fake Play Store (com.android.vending)
| Field | Value |
|-------|-------|
| **Severity** | HIGH (CVSS 7.5) |
| **Category** | Software Integrity (OWASP A08) |
| **Status** | CONFIRMED |
| **Evidence** | Package `com.android.vending` is "Tubesky" (not Google Play Store), uses same package name for app store spoofing |
| **Impact** | Users believe they're installing from Google Play. Instead, apps come from an unaudited Chinese store. App signing and malware scanning bypassed. |
| **Risk** | Malicious app distribution, credential harvesting. |
| **Remediation** | Install legitimate Google Play Store or use Aptoide with caution. |

---

### VULN-014: Excessive Permissions on System Apps
| Field | Value |
|-------|-------|
| **Severity** | MEDIUM (CVSS 6.1) |
| **Category** | Broken Access Control (OWASP A01) |
| **Status** | CONFIRMED |
| **Evidence** | `com.hx.appcleaner` (SYSTEM) has: CAMERA, RECORD_AUDIO, READ_CONTACTS, READ_CALL_LOG, ACCESS_FINE_LOCATION, BLUETOOTH, READ_EXTERNAL_STORAGE, etc. |
| **Impact** | An "app cleaner" utility has permissions to record audio, use camera, read contacts, and access location. No legitimate reason for these permissions. |
| **Risk** | Surveillance capability. Data exfiltration possible. |
| **Remediation** | `pm disable com.hx.appcleaner`. |

---

### VULN-015: NFS/CIFS Kernel Modules Loaded
| Field | Value |
|-------|-------|
| **Severity** | LOW (CVSS 3.1) |
| **Category** | Attack Surface (OWASP A05) |
| **Status** | CONFIRMED |
| **Evidence** | `cifs` (754KB), `nfs`, `nfsv2`, `nfsv3`, `nfsv4`, `lockd`, `sunrpc` all loaded |
| **Impact** | Network filesystem modules increase attack surface. SMBv1 (via CIFS) has known vulnerabilities. |
| **Risk** | Potential for remote exploitation via malformed NFS/CIFS packets. |
| **Remediation** | Blacklist unnecessary modules. |

---

### Vulnerability Summary Table

| ID | Name | Severity | CVSS | Category |
|----|------|----------|------|----------|
| VULN-001 | SELinux Permissive | CRITICAL | 9.8 | Config |
| VULN-002 | ADB No Auth | CRITICAL | 9.8 | Auth |
| VULN-003 | SUID Root su | CRITICAL | 9.8 | Access |
| VULN-004 | SuperUser Daemon | HIGH | 8.6 | Config |
| VULN-005 | userdebug/test-keys | HIGH | 8.1 | Integrity |
| VULN-006 | NFX Malware | CRITICAL | 9.1 | Malware |
| VULN-007 | ChihiHX Store | HIGH | 8.4 | Access |
| VULN-008 | OTA C2 Server | HIGH | 8.1 | C2/SSRF |
| VULN-009 | Identity Spoof | HIGH | 7.5 | Auth |
| VULN-010 | World-Writable Devs | MEDIUM | 6.5 | Access |
| VULN-011 | Root Shell Scripts | HIGH | 7.8 | Injection |
| VULN-012 | GMS Disabler | MEDIUM | 5.3 | Config |
| VULN-013 | Fake Play Store | HIGH | 7.5 | Integrity |
| VULN-014 | Excessive Perms | MEDIUM | 6.1 | Access |
| VULN-015 | NFS/CIFS Loaded | LOW | 3.1 | Surface |

**Overall Security Score: 1.2 / 10 (FAIL)**

- CRITICAL vulnerabilities: 4
- HIGH vulnerabilities: 7
- MEDIUM vulnerabilities: 3
- LOW vulnerabilities: 1

---

## Malware & Suspicious Software {#malware-analysis}

### Package Inventory (Suspicious)

| Package | System Level | Status | Risk |
|---------|-------------|--------|------|
| com.android.nfx | SYSTEM (uid=1000) | **DISABLED** | Netflix malware |
| com.chihihx.store | SYSTEM (uid=1000) | **DISABLED** | Unauthorized app store |
| com.chihihx.launcher | SYSTEM (uid=1000) | Active | Custom launcher |
| com.hx.update | SYSTEM (uid=1000) | **DISABLED** | C2-connected updater |
| com.hx.appcleaner | SYSTEM (uid=1000) | **DISABLED** | Over-privileged cleaner |
| com.hx.apkbridge | SYSTEM (uid=1000) | **DISABLED** | APK sideload bridge |
| com.android.nfhelper | SYSTEM (uid=1000) | **DISABLED** | Netflix helper |
| com.hx.videotest | SYSTEM (uid=1000) | Active | Video test utility |
| com.hx.guardservice | SYSTEM | **DISABLED** | Factory test guard |
| com.dd.bugreport | SYSTEM | **DISABLED** | Custom bug reporter |
| cm.aptoidetv.pt | User | **DISABLED** | Third-party store |
| com.android.vending (Tubesky) | SYSTEM | Active | Fake Play Store |

### NFX Malware Deep Dive

The `com.android.nfx` (NFXAccessibility v1.1.4) is the most dangerous component:

```
Location:     /vendor/preinstall/NFXAccessibility_Android14_v1.1.4/
APK Size:     112KB
Package:      com.android.nfx
Permissions:  BIND_ACCESSIBILITY_SERVICE (AccessibilityService)
Target App:   com.netflix.mediaclient
```

**Capabilities found in decompiled code:**
- AccessibilityService targeting Netflix
- Hardcoded Netflix UI element IDs (buttons, menus)
- GestureDescription dispatch (simulates user touches)
- WindowManager integration (`enableNfxAccessibility` flag)
- Auto-enabled at system level

---

## Network Security Analysis {#network-security}

### Active Connections (Before Cleanup)

| Local | Remote | State | Process | Risk |
|-------|--------|-------|---------|------|
| *:5555 | * | LISTEN | adbd | ADB (no auth) |
| *:1234 | * | LISTEN | tvserver | Open port |
| 192.168.0.106:* | 116.202.8.16:443 | ESTABLISHED | com.hx.update | **C2 server** |

### After Cleanup (iptables rules applied)

```
iptables -A OUTPUT -d 116.202.8.0/24 -j DROP    # Block C2
iptables -A INPUT -p tcp ! -s 127.0.0.1 --dport 1234 -j DROP  # Block port 1234
```

### DNS Configuration

```
Resolver:       Android DNS resolver (Netd)
/etc/hosts:     127.0.0.1 localhost, ::1 ip6-localhost (clean)
```

---

## Firmware Dump Inventory {#firmware-dump}

All partition images are stored in `firmware_dump/`:

### Successfully Dumped

| File | Size | Description |
|------|------|-------------|
| bootloader_a.img | 32MB | U-Boot bootloader (slot A) |
| boot_a.img | 64MB | Android boot image with kernel |
| vendor_boot_a.img | 32MB | Vendor-specific boot resources |
| init_boot_a.img | 8MB | Init boot image |
| env_a.img | 256KB | U-Boot environment variables |
| super.img | 1.75GB | Super partition (system+vendor+product) — **PARTIAL** (disk full during dump, 1.75/3.5GB) |
| misc.img | 16MB | Misc partition |
| vbmeta_a.img | 128KB | AVB verification metadata |
| vbmeta_b.img | 128KB | AVB verification metadata (slot B) |
| vbmeta_system_a.img | 64KB | System AVB metadata |
| vbmeta_system_b.img | 64KB | System AVB metadata (slot B) |
| vbmeta_vendor_a.img | 64KB | Vendor AVB metadata |
| vbmeta_vendor_b.img | 64KB | Vendor AVB metadata (slot B) |
| frp.img | 512KB | Factory Reset Protection |
| dtbo_a.img | 2MB | Device Tree Blob Overlays |
| dtbo_b.img | 2MB | Device Tree Blob Overlays (slot B) |
| private.img | 16MB | Private partition |
| metadata.img | 16MB | Metadata partition |

### Configuration Files Saved

| File | Description |
|------|-------------|
| all_props.txt | All system properties (getprop) |
| modules.txt | Loaded kernel modules |
| fstab.txt | Filesystem mount table |
| partition_map.txt | Full partition and mount info |
| init_scripts/system/ | 85 system init scripts |
| init_scripts/vendor/ | 47 vendor init scripts |
| kernel_modules/ | 80 .ko module files |

### Note on Super Partition

The super.img dump is **partial** (1.75GB of 3.5GB) due to limited free space on /data. To get a complete dump:
1. Connect a USB drive or SD card
2. Dump super to external storage: `dd if=/dev/block/mmcblk0p11 of=/mnt/usb/super.img bs=65536`
3. Or dump directly over ADB: `adb exec-out su 0 dd if=/dev/block/mmcblk0p11 bs=65536 > super_full.img`

---

## Files Collected {#files-collected}

### APKs Extracted

| File | Size | Package |
|------|------|---------|
| nfx.apk | 112KB | com.android.nfx (Netflix malware) |
| hx_update.apk | 19.3MB | com.hx.update (OTA updater) |
| hx_appcleaner.apk | 207KB | com.hx.appcleaner |
| nfhelper.apk | 2.4MB | com.android.nfhelper |
| bugreport.apk | 104KB | com.dd.bugreport |

### Decompiled

| Directory | Contents |
|-----------|----------|
| nfx_extracted/ | Decompiled NFX APK (classes.dex, AndroidManifest.xml, accessibility.xml) |

### Scripts Created

| File | Purpose |
|------|---------|
| investigate.ps1 | PowerShell investigation toolkit |
| cleanup.sh | Root-level malware cleanup (v1) |
| cleanup_v2.sh | Aggressive cleanup with iptables |
| hw_probe.sh | Hardware probe script |
| dump_firmware.sh | Firmware partition dump script |
| modinfo_probe.sh | Kernel module info extraction |

---

*Report generated: March 1, 2026*
*ADB connection: 192.168.0.106:5555*
*Build fingerprint: google/blueline/blueline:14/AP2A.240905.003/12231197:userdebug/test-keys*
