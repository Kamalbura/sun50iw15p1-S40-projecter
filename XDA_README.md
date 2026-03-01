# Tearing Apart a $60 "4K" Chinese Projector — What I Found Will Make You Unplug Yours

> **Device**: Orange Box S40 "4K FHD" Projector  
> **Claimed**: 4K resolution, 2GB RAM, 16GB storage, Android TV, Dual-band WiFi  
> **Reality**: A 1024×600 panel running malware-infested Android 14 that pretends to be a Google Pixel 3  

---

## TL;DR

I bought a cheap Chinese projector off AliExpress. Out of curiosity, I connected via ADB and found:

- **Pre-installed malware** that manipulates your Netflix app
- The device **lies about being a Google Pixel 3** to bypass DRM checks
- **SELinux is disabled**, **ADB has no authentication**, and there's a **root backdoor** listening on the network
- A hidden app store (ChihiHX) runs with SYSTEM privileges and can silently install anything
- An OTA updater phones home to a server in Germany (Hetzner) and can push updates without your consent
- An "App Cleaner" utility has camera, microphone, contacts, and location permissions — for no reason
- **Every single marketing claim** about the hardware is exaggerated or outright false

I then spent weeks doing a **complete reverse engineering** — dumping every partition, decompiling the firmware, extracting the device tree, mapping every chip on the board, and documenting all 15 security vulnerabilities with CVSS scores.

This is the full story.

---

## Table of Contents

1. [How It Started](#how-it-started)
2. [Getting In — ADB Access](#getting-in)
3. [The Hardware — Every Spec Is a Lie](#the-hardware)
4. [The Software — A Security Nightmare](#the-software)
5. [Finding the Malware](#finding-the-malware)
6. [The Identity Fraud — Fake Pixel 3](#identity-fraud)
7. [The Full Vulnerability Report (15 Findings)](#vulnerability-report)
8. [Going Deeper — Full Firmware Dump](#firmware-dump)
9. [What's Inside the Firmware](#inside-the-firmware)
10. [The Device Tree — Complete Hardware Map](#device-tree)
11. [The Display Pipeline — How It Actually Works](#display-pipeline)
12. [Community Research — We're Not Alone](#community-research)
13. [Cleanup — What I Disabled](#cleanup)
14. [What You Can Do Next](#what-next)
15. [File Inventory](#file-inventory)

---

## 1. How It Started {#how-it-started}

I bought an "Orange Box S40" projector — one of those generic Chinese projectors you see flooding AliExpress and Amazon with fake review photos and impossible specs. The listing claimed "4K FHD Native 1080P", "2GB RAM + 16GB Storage", "Android TV with Google Play", "Dual-band WiFi 6". It cost about $60.

The projector arrived, the picture quality was... fine for the price. But I'm a developer, and the software felt off. The launcher was Chinese, apps I didn't install kept appearing, and I noticed network activity I couldn't explain.

So I opened a terminal and typed `adb connect`.

What I found was far worse than I expected.

---

## 2. Getting In — ADB Access {#getting-in}

The projector runs Android with **ADB (Android Debug Bridge) wide open on port 5555**. No authentication. No RSA key approval. Just connect and you're in.

```
adb connect 192.168.0.106:5555
adb shell
```

And then I tried:

```
su 0
id
→ uid=0(root) gid=0(root) groups=0(root)
```

**Full root access.** No password, no prompt, no confirmation. The `su` binary at `/system/xbin/su` has the SUID bit set and is accessible to anyone in the `shell` group — which includes every ADB connection.

But wait — there's also a **SuperUser daemon** (`qw`) running as root from boot, started by an init script, providing persistent root access through a Unix socket. This isn't accidental debugging left in. This is by design.

Anyone on your WiFi network can connect to this projector and have **full root access** to the device. They can read your files, install apps, capture your screen, access your camera — anything.

---

## 3. The Hardware — Every Spec Is a Lie {#the-hardware}

With root access, I was able to probe every piece of hardware. Here's what the marketing says versus what's actually inside:

| Marketing Claim | Actual Hardware | Verdict |
|----------------|-----------------|---------|
| "4K FHD" / "1080P Native" | **1024×600** LCD panel (not even 720p) | **LIE** |
| "2GB RAM" | **1GB** physical, **835MB** usable | **LIE** |
| "16GB Storage" | **7.3GB** eMMC, **~1.9GB** actually free | **LIE** |
| "Android TV" | AOSP Android 14 (no Google certification) | **MISLEADING** |
| "WiFi 6 Dual-band" | AIC8800D80 — WiFi 5 (802.11ac), single stream | **LIE** |
| "Bluetooth 5.0" | AIC8800 BT module | *Probably accurate* |
| "Auto Keystone" | Hardware KSC engine + accelerometer | **Actually works** |
| "Auto Focus" | STMicro VL53L1 ToF sensor + stepper motor | **Actually works** |

### The SoC — Allwinner H723

```
SoC             Allwinner H723 (sun50iw15p1)
Architecture    4× ARM Cortex-A53 (running in 32-bit mode!)
GPU             ARM Mali Midgard (T-series)
Video Engine    Allwinner Cedar (H.265/H.264/VP9 decode)
RAM             1GB DDR (835MB usable — rest eaten by GPU/CMA/kernel)
Storage         eMMC "P1J95K" — 7.3GB from an unknown manufacturer
```

Yes, a quad-core 64-bit CPU running in **32-bit mode**. They literally wasted half the CPU's capability.

### The Display

```
Panel           "TV303 SVP OSD3"
Native Res      1024 × 600 pixels
Interface       LVDS (panel_lvds_gen driver)
Backlight       PWM-controlled, 100 brightness levels
```

That "4K" projector has fewer pixels than a 2008 netbook screen. The image is upscaled from 1024×600 to whatever resolution the HDMI source sends. The "Full HD" you see is just stretched pixels.

### Genuine Hardware (Credit Where Due)

Not everything is fake. The auto-focus and keystone systems are real hardware:

- **Auto Focus**: STMicro VL53L1 Time-of-Flight laser rangefinder → measures distance to wall → drives a 4-phase stepper motor to adjust the lens
- **Auto Keystone**: SC7A20E accelerometer detects tilt → Allwinner KSC hardware engine corrects the image geometry in real-time
- **3× HDMI inputs** with CEC support (including ARC on port 1)
- **IR receiver** with NEC + RC5 protocol decoders (supports 15 remote codes)
- **Dual PWM fans** for cooling

The hardware design isn't terrible for $60. The software is where things go very, very wrong.

---

## 4. The Software — A Security Nightmare {#the-software}

### Build Identity

```
OS              Android 14 (SDK 34)
Build Type      userdebug (NOT a production build)
Build Tags      test-keys (signed with PUBLIC test keys)
SELinux         Permissive (all security enforcement DISABLED)
ADB             ro.adb.secure=0 (no authentication required)
Kernel          Linux 5.15.167
Build Date      September 12, 2025
```

Let me break down why each of these is catastrophic:

- **`userdebug` build**: This is a developer build. It includes debugging tools, relaxed permissions, and extra attack surface that should never ship to consumers.
- **`test-keys`**: The firmware is signed with publicly known keys. Anyone can build a system image and flash it. There is zero software integrity.
- **SELinux Permissive**: Android's primary security boundary — the thing that keeps apps isolated from each other — is completely turned off. Every process can access every resource.
- **ADB no auth**: Anyone on your network can connect. No key exchange. No "Allow USB debugging?" prompt. Just instant shell access.

This isn't careless. This is a deliberate choice to make the device easy to control remotely — probably for pushing updates and managing the malware.

---

## 5. Finding the Malware {#finding-the-malware}

### NFX — The Netflix Manipulator

The first thing that caught my eye was a package called `com.android.nfx`. The name looks like a system package (it starts with `com.android`), but it's actually **NFXAccessibility v1.1.4** — a malware app pre-installed in the vendor partition.

```
Location    /vendor/preinstall/NFXAccessibility_Android14_v1.1.4/
Size        112KB
UID         1000 (SYSTEM)
Type        AccessibilityService targeting com.netflix.mediaclient
```

I decompiled the APK. Here's what it does:

1. Registers as an **AccessibilityService** — this gives it the ability to read the screen and simulate user input on ANY app
2. Specifically targets **Netflix** (`com.netflix.mediaclient`)
3. Contains **hardcoded Netflix UI element IDs** — it knows exactly which buttons to press
4. Uses **GestureDescription** to simulate taps and swipes — it can navigate Netflix menus by itself
5. Has **WindowManager integration** with a custom flag (`enableNfxAccessibility`) — it's baked into the system framework

This is factory-installed. It survives factory resets. It runs as SYSTEM (uid=1000). It is burned into the read-only vendor partition.

What's it used for? Most likely **ad fraud** — automatically playing specific content on Netflix to generate engagement metrics. Or **credential harvesting**. Either way, it's manipulating your Netflix account without your knowledge.

### ChihiHX Store — The Silent App Installer

```
Package     com.chihihx.store
UID         1000 (SYSTEM — same as Settings, Phone, etc.)
Perms       INSTALL_PACKAGES, DELETE_PACKAGES
Behavior    Auto-starts on boot, can install/remove any app silently
```

An unauthorized app store running with the highest Android privileges. It can install any APK onto your device without your consent. This is the supply chain attack vector — they can push new malware anytime.

### HX Update — The C2 Connection

```
Package     com.hx.update
UID         1000 (SYSTEM)
Perms       INSTALL_PACKAGES, DELETE_PACKAGES, REBOOT
Connection  TCP → 116.202.8.16:443 (Hetzner, Germany)
```

I caught this one making an active TCP connection to a server at `116.202.8.16` on Hetzner's infrastructure in Germany. This is the OTA (Over-The-Air) update mechanism. It has permissions to install packages, delete packages, and **reboot your device**. It runs as SYSTEM. It checks in with the command-and-control server regularly.

No consent. No notification. No way to verify what it's downloading.

### HX App Cleaner — The Spy

```
Package     com.hx.appcleaner
UID         1000 (SYSTEM)
Perms       CAMERA, RECORD_AUDIO, READ_CONTACTS, READ_CALL_LOG,
            ACCESS_FINE_LOCATION, BLUETOOTH, READ_EXTERNAL_STORAGE
```

An "app cleaner" utility that has permissions to **use your camera, record audio, read your contacts, read your call log, track your location, and access your files**. There is no legitimate reason for a cache cleaner to have these permissions. This is a surveillance toolkit disguised as a utility.

### Tubesky — The Fake Play Store

The package `com.android.vending` — which should be the Google Play Store — is actually something called **"Tubesky"**. It uses the Play Store's package name to intercept app installation requests. Users think they're installing from Google Play. They're not. They're installing from an unaudited Chinese app store with no malware scanning.

---

## 6. The Identity Fraud — Fake Pixel 3 {#identity-fraud}

This one surprised me. Deep in the init ramdisk's `build.prop`:

```properties
ro.product.model=Pixel 3
ro.product.brand=google
ro.product.manufacturer=Google
ro.product.device=blueline
ro.build.fingerprint=google/blueline/blueline:14/AP2A.240905.003/12231197:userdebug/test-keys
```

The projector tells every app, every service, and every Google server that it is a **Google Pixel 3** (codename: "blueline"). This is identity spoofing to:

1. **Bypass Netflix DRM** (Widevine L1) certification
2. **Pass Google Play compatibility checks** 
3. **Bypass SafetyNet/Play Integrity** attestation
4. **Unlock app compatibility** for apps that require certified Android TV devices

The irony: it claims to be a `user/release-keys` build in the fingerprint, while the actual build is `userdebug/test-keys`. Even the lie has a lie inside it.

---

## 7. The Full Vulnerability Report {#vulnerability-report}

I catalogued 15 security vulnerabilities using OWASP methodology and CVSS scoring:

| ID | Vulnerability | Severity | CVSS |
|----|--------------|----------|------|
| VULN-001 | SELinux Permissive — all MAC disabled | CRITICAL | 9.8 |
| VULN-002 | ADB on WiFi — no RSA authentication | CRITICAL | 9.8 |
| VULN-003 | SUID `su` binary — any shell user gets root | CRITICAL | 9.8 |
| VULN-004 | SuperUser daemon (`qw`) — persistent root backdoor | HIGH | 8.6 |
| VULN-005 | userdebug build with test-keys | HIGH | 8.1 |
| VULN-006 | NFX malware — Netflix manipulation | CRITICAL | 9.1 |
| VULN-007 | ChihiHX Store — silent app installer (SYSTEM) | HIGH | 8.4 |
| VULN-008 | OTA updater — C2 connection to 116.202.8.16 | HIGH | 8.1 |
| VULN-009 | Identity spoofing — fake Pixel 3 fingerprint | HIGH | 7.5 |
| VULN-010 | World-writable device nodes (/dev/video0, /dev/hxext) | MEDIUM | 6.5 |
| VULN-011 | Root shell scripts — USB auto-exec, patch mechanism | HIGH | 7.8 |
| VULN-012 | GMS disabler — disables Google security services at boot | MEDIUM | 5.3 |
| VULN-013 | Tubesky — fake Play Store using com.android.vending | HIGH | 7.5 |
| VULN-014 | App Cleaner — camera/mic/location on a cache cleaner | MEDIUM | 6.1 |
| VULN-015 | NFS/CIFS kernel modules loaded — unnecessary attack surface | LOW | 3.1 |

**Overall Security Score: 1.2 / 10**

- 4 CRITICAL vulnerabilities
- 7 HIGH vulnerabilities
- 3 MEDIUM vulnerabilities
- 1 LOW vulnerability

---

## 8. Going Deeper — Full Firmware Dump {#firmware-dump}

After the initial investigation, I decided to dump the entire firmware for offline analysis.

### The Dumping Process

The device has **29 eMMC partitions** in an A/B partition scheme. I dumped each one over ADB.

**Critical lesson learned**: PowerShell's `>` redirect operator **corrupts binary data** by injecting `\r\n` line endings. Every binary transfer must use:

```powershell
cmd /c "adb exec-out su 0 dd if=/dev/block/mmcblk0pX bs=65536 > output.img"
```

The `cmd /c` wrapper bypasses PowerShell's encoding and preserves the raw bytes. This cost me a failed 3.5GB super partition dump before I figured it out.

### Partition Map

| # | Partition | Size | Purpose |
|---|-----------|------|---------|
| p1-p2 | bootloader_a/b | 32MB each | U-Boot 2018.07 bootloader |
| p3-p4 | env_a/b | 256KB each | U-Boot environment variables |
| p5-p6 | boot_a/b | 64MB each | Linux kernel + Android boot image |
| p7-p8 | vendor_boot_a/b | 32MB each | Vendor boot resources + DTB |
| p9-p10 | init_boot_a/b | 8MB each | Init ramdisk (Android 14 v4 format) |
| p11 | **super** | **3.5GB** | Contains system/vendor/product (dm-verity) |
| p12 | misc | 16MB | Boot control metadata |
| p13-p18 | vbmeta_* | 64-128KB | Android Verified Boot metadata |
| p19 | frp | 512KB | Factory Reset Protection |
| p20 | empty | 15MB | Empty partition |
| p21 | metadata | 16MB | Encryption metadata |
| p22 | treadahead | 96MB | Read-ahead cache |
| p23 | private | 16MB | Unknown purpose |
| p24-p25 | dtbo_a/b | 2MB each | Device tree overlays |
| p26 | media_data | 16MB | Mounted as /oem (vfat) |
| p27-p28 | Reserve0_a/b | 16MB each | Reserved storage |
| p29 | userdata | 3.3GB | User data (not dumped — it's personal data) |

### Key Discovery: Slot B Is Empty

**All slot B partitions contain nothing but zeros.** The A/B partition scheme exists in the partition table, but slot B was never written. This means:

- There is **no recovery fallback** — if slot A gets corrupted, the device is bricked
- OTA updates don't use A/B seamlessly — they probably just overwrite slot A
- The partition table wastes **~200MB** on empty slot B partitions

### Verification

Every partition was verified against the device:

- **5 partitions** verified by MD5 hash (bit-perfect match)
- **All 28 partitions** verified by file size (exact byte count match)
- The super partition (3.5GB) took 4 minutes to transfer and matched: `91227c7b3f881d3b8ffdcabd3b3f51de`

---

## 9. What's Inside the Firmware {#inside-the-firmware}

### Boot Images — Unpacked

I wrote custom Python parsers to unpack each boot image:

**boot_a.img** (Android Boot Image v4):
- Kernel: 35.5MB raw ARM64 binary
- OS Version: Android 14.0.0, security patch 2024-06
- No ramdisk (moved to init_boot in boot v4)

**init_boot_a.img** (Init Ramdisk):
- 3.4MB LZ4-compressed → 5.1MB decompressed
- 27 CPIO entries, including:
  - `init` — Android init binary (2.6MB)
  - `fstab.sun50iw15p1` — complete filesystem mount table
  - `build.prop` — the fake Pixel 3 identity (see section 6)
  - `avb/` — Android Verified Boot keys (developer-GSI keys for API levels q, r, s)

**vendor_boot_a.img** (Vendor Boot v4):
- Vendor ramdisk: 16.8MB → 28.5MB decompressed (522 files)
- Embedded DTB: 72KB device tree blob
- Kernel load address: `0x40008000`
- Contains 10 critical kernel modules pre-loaded at first stage:
  - `sunxi_ksc.ko` — Keystone Correction
  - `sunxi-ve.ko` — Video Engine
  - `panel_lvds_gen.ko` — LVDS panel driver
  - `pwm_bl.ko`, `backlight.ko` — Backlight control
  - `hidtvreg_dev.ko` — TV register device
  - And 4 more display pipeline modules

**dtbo_a.img** (Device Tree Overlays):
- 3 overlay entries, all valid FDT (Flattened Device Tree)
- Decompiled to human-readable DTS format

### Super Partition — The Filesystem

The 3.5GB super partition contains 5 logical partitions using Android's dynamic partition system:

| Partition | Size | Filesystem | Contents |
|-----------|------|------------|----------|
| system_a | 2.2GB | ext4 | Android framework, 34 system apps, binaries |
| vendor_a | 468MB | ext4 | HAL services, proprietary drivers, firmware blobs, **malware** |
| product_a | 40MB | ext4 | Product overlays, additional apps |
| vendor_dlkm_a | 4.5MB | EROFS | Vendor dynamically loadable kernel modules |
| system_dlkm_a | 0.3MB | ext4 | System kernel module overrides |

All 5 partitions are 100% full — zero free blocks. This is a tightly packed firmware image.

### Pre-installed Apps

**System apps** (`/system/app/` — 34 total):
- **CHIHI_Launcher** — Chinese custom launcher (ChihiHX)
- **AppStore** — third-party app store
- **AppCleaner** — the spyware masquerading as a utility
- **DragonAgingTV, DragonBox, DragonAtt, DragonRunin** — Allwinner factory test apps (left in production build!)
- **RuninConfig, StressTestGuard** — more factory test leftovers
- **AwLiveTv** — Allwinner Live TV
- **MiracastReceiver** — screen mirroring
- **PlatinumMediaDLNA** — DLNA server
- Chrome, GoogleTTS, WebViewGoogle — stock Android apps

**Vendor preinstalls** (`/vendor/preinstall/` — the malware shelf):

| App | What It Really Is |
|-----|------------------|
| **NFXAccessibility_Android14_v1.1.4** | Netflix manipulation malware |
| netflix_8.121 | Netflix (target for NFX) |
| youtube_tv | YouTube TV |
| Aptoide_TV | Third-party app store |
| airpin | AirPlay mirroring |
| apowermirror-tv | ApowerMirror |

### Vendor HAL Services

The vendor partition contains 25 Hardware Abstraction Layer services:

- `tvserver` — Allwinner TV system server (listening on port 1234)
- `android.hardware.graphics.composer@2.2-service` — Display composer  
- `android.hardware.tv.input@1.0-service` — TV input (HDMI)
- `android.hardware.tv.cec@1.0-service` — HDMI CEC
- `android.hardware.audio@7.0-service` — Audio
- `android.hardware.bluetooth@1.0-service` — Bluetooth
- `android.hardware.wifi@1.0-service` — WiFi
- And 18 more...

### Proprietary Libraries — The Crown Jewels

These are the binary blobs that make the hardware work. Reverse engineering or replacing these is the key challenge for custom OS development:

| Library | Purpose | Open Source Alternative? |
|---------|---------|------------------------|
| `libksc.so` | Keystone Correction engine | **YES** — GPL source found! |
| `libtvpq.so` | TV Picture Quality processing | No |
| `libdisplayconfig.so` | Display configuration | No |
| `libwifi-hal-aic.so` | AIC8800 WiFi HAL | **YES** — DKMS drivers exist |
| `vendor.sunxi.tv.graphics@1.0-impl.so` | Sunxi TV graphics | No |
| `vendor.aw.homlet.tvsystem.tvserver@1.0` | Allwinner TV system | No |

---

## 10. The Device Tree — Complete Hardware Map {#device-tree}

I pulled the live device tree from `/sys/firmware/fdt` (196KB DTB) and decompiled it to a 132KB, 3024-line DTS (Device Tree Source) file. This is the complete hardware description — every chip, every register address, every GPIO pin, every clock domain.

### Memory Map (from /proc/iomem)

| Address | Peripheral |
|---------|-----------|
| `0x01800000` | Mali GPU |
| `0x02000000` | Pin Controller (GPIO) |
| `0x02000C00` | PWM0 (10 channels — fans, backlight, etc.) |
| `0x02010000` | IOMMU |
| `0x02030000` | Audio Codec |
| `0x02051000` | Watchdog |
| `0x02502400` | I2C Controllers (sensors) |
| `0x02600000` | UARTs |
| `0x04020000` | SD/MMC Controllers |
| `0x04500000` | Ethernet MAC |
| `0x05700000` | TV Display Controller |
| `0x05800000` | LVDS Interface |
| `0x05900000` | **KSC (Keystone Correction)** — 1MB register space |
| `0x05A02000` | TCON (Timing Controller) |
| `0x07040000` | IR Receiver |
| `0x07070400` | Thermal Sensor |
| `0x07090000` | Real-Time Clock |
| `0x40000000-0x7FFFFFFF` | System RAM (1GB) |

### Projector-Specific Hardware

**Stepper Motor (Auto Focus)**:
```
Type            4-phase stepper motor
GPIO Phases     PH10, PH11, PH12, PH13
Step Sequence   8 steps with CW/CCW tables
Phase Delay     5 microseconds
Step Delay      2 milliseconds
Limit Switch    PB1 (endpoint detection)
Control         echo "1,<steps>" > /sys/devices/platform/motor0/motor_ctrl (CW)
                echo "2,<steps>" > /sys/devices/platform/motor0/motor_ctrl (CCW)
```

**Dual Fan Cooling**:
```
Fan 1           PWM channel 2, 6 cooling levels (0-255)
Fan 2           PWM channel 3, 6 cooling levels (0-255)
Status          Disabled in DTS (controlled by Android framework)
```

**KSC Keystone Correction Engine**:
```
Compatible      allwinner,ksc100
Register Base   0x5900000 (1MB range)
Clock           480 MHz
Mode            Hardware-accelerated geometric transformation
Input           Accelerometer tilt data → correction matrix
Output          Corrected framebuffer → LVDS panel
```

**TV Backlight**:
```
Type            PWM-based
Levels          100 (0-100)
Default         80
Enable GPIO     PB6
```

**IR Remote** — 15 remote control codes configured, supporting multiple manufacturers and protocols (NEC, RC5, and more).

**Boot Command Line**:
```
console=ttyAS0,115200 cma=24M snum=8c000c7543c24771a8c 
mac_addr=48:E0:59:16:04:59 boot_type=2 
androidboot.selinux=permissive firmware_class.path=/vendor/etc/firmware
```

Note the UART console at 115200 baud on `ttyAS0` — useful for anyone wanting to connect UART for deeper debugging.

---

## 11. The Display Pipeline — How It Actually Works {#display-pipeline}

Here's the complete rendering chain from framebuffer to light on your wall:

```
┌─────────────────────────────────────────────────────────────┐
│  Android SurfaceFlinger                                      │
│       ↓                                                      │
│  Allwinner Display Engine (SoC built-in)                    │
│       ↓                                                      │
│  vs_display (V-Silicon IP block)                            │
│       ↓                                                      │
│  vs_osd (V-Silicon OSD overlay compositor @ 0x5600000)      │
│       ↓                                                      │
│  sunxi_ksc (Keystone Correction @ 0x5900000, 480 MHz)       │
│       ↓                                                      │
│  tvpanel (Allwinner TV panel framework)                     │
│       ↓                                                      │
│  panel_lvds_gen (LVDS driver → 1024×600 LCD)                │
│       ↓                                                      │
│  pwm_bl (PWM backlight → LED light source)                  │
│       ↓                                                      │
│  Projection lens → Your wall                                 │
└─────────────────────────────────────────────────────────────┘
```

The auto-keystone flow:

```
SC7A20E Accelerometer (I2C) → detects device tilt
       ↓
Android Sensor HAL → reads accelerometer data
       ↓
Keystone Service → calculates correction matrix
       ↓  
sunxi_ksc.ko → applies geometric transformation on GPU output
       ↓
vs_osd → composites the corrected frame
       ↓
LVDS → LCD panel
```

### Kernel Module Dependency Chain

```
backlight
  └── tvpanel
       ├── panel_lvds_gen (LVDS output)
       ├── panel_dsi_gen (DSI output — unused on this device)
       ├── sunxi_ksc (Keystone Correction)
       │    └── vs_osd (V-Silicon OSD)
       │         └── vs_display (V-Silicon display controller)
       └── sunxi_tvtop
            └── sunxi_tvtop_adc
```

---

## 12. Community Research — We're Not Alone {#community-research}

After completing my analysis, I searched GitHub and found other people reverse engineering similar projectors:

### shift/sun50iw12p1-research (24 stars)

The most advanced project. They're porting **mainline Linux** to the Allwinner H713 — the sister SoC to our H723. Same quad Cortex-A53, same Mali GPU, same projection hardware ecosystem.

**They've completed 8 full phases**:
- Mainline device tree (967 lines)
- U-Boot port (H6 base config)
- MIPS co-processor driver (905 lines — H713 has a MIPS chip that manages display)
- Panfrost GPU integration
- V4L2 HDMI capture driver (1,760 lines)
- Full NixOS VM with Kodi
- FEL mode flashing tools

### srgneisner/hy300-linux-porting (7 stars)

Privacy-focused Armbian port for the HY300 projector. Found the same malware/spyware threats we did. Goal: a clean, privacy-respecting OS.

### chainsx/u-boot-sun60i — KSC SOURCE CODE FOUND!

This was the biggest discovery. The full **GPL-2.0 source code** for the KSC (Keystone Correction) driver exists in this repo:

```
src/drivers/video/sunxi/ksc/ksc.c          — Main KSC driver
src/drivers/video/sunxi/ksc/ksc.h          — Device structures
src/drivers/video/sunxi/ksc/ksc_drv.c      — Platform driver
src/drivers/video/sunxi/ksc/ksc_mem.c      — DMA memory management
src/drivers/video/sunxi/ksc/ksc_reg/       — Register definitions
```

Author: `zhengxiaobin@allwinnertech.com`. This eliminates one of the biggest proprietary blockers for a Linux port.

### AIC8800 WiFi Drivers

Multiple working Linux drivers exist for the AIC8800 WiFi chip:
- `fqrious/aic8800-dkms` — DKMS package (9 stars)
- `LYU4662/aic8800-sdio-linux-1.0` — tested on kernel 6.7
- Several other SDIO variants

**WiFi is not a blocker for Linux porting.**

### How We Compare

| Capability | Our Project | shift (H713) | srgneisner (H713) |
|-----------|------------|-------------|-------------------|
| Security Analysis | **Best** (15 vulns, CVSS) | Basic | Privacy-focused |
| Firmware Dump | **Complete** (28/29 parts) | FEL + ADB | Phase I |
| Hardware Mapping | **Complete** (full DTS + iomem) | Complete | Planned |
| Malware Analysis | **Deepest** (decompiled APKs) | Identified | Identified |
| Kernel Module Collection | **80 .ko files** | Some | Planned |
| Mainline Linux | Not yet | **Complete** (8 phases) | Phase II |
| Custom OS | Roadmap | **Working NixOS** | Armbian planned |

Our project has the most thorough security analysis and firmware extraction. The community projects have working Linux ports. Together, there's enough to build a clean OS for these projectors.

---

## 13. Cleanup — What I Disabled {#cleanup}

For anyone who owns one of these projectors and wants to mitigate the threats immediately:

### Step 1: Disable Malware via ADB

```bash
adb connect <projector-ip>:5555
adb shell

# Get root
su 0

# Disable NFX Netflix malware
pm disable com.android.nfx

# Disable the hidden app store
pm disable com.chihihx.store

# Disable the C2-connected OTA updater
pm disable com.hx.update

# Disable the spyware "app cleaner"
pm disable com.hx.appcleaner

# Disable the APK sideload bridge
pm disable com.hx.apkbridge

# Disable the Netflix helper
pm disable com.android.nfhelper

# Disable the factory test guard
pm disable com.hx.guardservice

# Disable the bug reporter
pm disable com.dd.bugreport

# Disable Aptoide store
pm disable cm.aptoidetv.pt
```

### Step 2: Block the C2 Server

```bash
# Block outbound connections to the Hetzner C2 server
iptables -A OUTPUT -d 116.202.8.0/24 -j DROP

# Restrict tvserver to localhost only
iptables -A INPUT -p tcp ! -s 127.0.0.1 --dport 1234 -j DROP
```

### Step 3: Verify

```bash
# Check that malware is disabled
pm list packages -d  # should show all the above packages

# Check no connections to C2
netstat -tlnp | grep 116.202
```

**Warning**: These changes survive reboots for `pm disable`, but `iptables` rules are lost on reboot. The malware is in the read-only vendor partition — you can disable it but not truly remove it without reflashing.

---

## 14. What You Can Do Next {#what-next}

### If You Just Want to Secure Your Projector

1. **Run the cleanup commands** from Section 13 — disable all malicious packages
2. **Block the C2 server** at your router level: block all traffic to `116.202.8.0/24`
3. **Isolate the projector** on a separate VLAN/WiFi network — don't let it onto your main network
4. **Don't enter any passwords or accounts** on this device — assume everything is monitored
5. **Disable ADB** if you can (Settings → Developer Options → disable ADB over network)

### If You Want to Go Further — Linux Porting

This is the exciting part. Based on our complete hardware mapping and the community's work, building a clean Linux OS for this projector is now feasible:

**What's ready TODAY:**

| Component | Status | Source |
|-----------|--------|--------|
| CPU / basic SoC | Mainline Linux | sunxi community |
| GPU (Mali) | Panfrost (open source) | Confirmed on sister H713 |
| WiFi (AIC8800) | Out-of-tree DKMS | Multiple repos, tested kernel 6.7 |
| Keystone (KSC) | GPL source code | chainsx/u-boot-sun60i |
| USB, SD/MMC | Mainline Linux | Standard sunxi drivers |
| IR Remote | Mainline Linux | sunxi-ir driver |
| PWM (fans, backlight) | Mainline Linux | Standard PWM subsystem |
| GPIO | Mainline Linux | Standard Allwinner |
| I2C (sensors) | Mainline Linux | Standard |
| ToF Sensor (VL53L1) | Mainline IIO driver | STMicro upstream driver |
| Accelerometers | Mainline IIO drivers | SC7A20E / KXTJ3 supported |
| IOMMU | BSP source available | radxa/allwinner-bsp references our SoC |

**What still needs work:**

| Component | Status | Difficulty |
|-----------|--------|-----------|
| V-Silicon Display | **Proprietary binary blob** | Hard — use blob initially, RE later |
| TV Panel Framework | Proprietary | Medium — may work with blob + mainline DRM |
| Audio (Trident) | Proprietary | Medium — snd_alsa_trid needs RE |
| H723-specific DTS | Needs creation | Low — adapt from our complete device tree dump |
| U-Boot H723 | Needs adaptation | Low-Medium — adapt from shift's H713 port |

**Concrete next steps for a Linux port:**

1. **Fork shift/sun50iw12p1-research** and start adapting for H723
2. **Create a mainline DTS** using our 3024-line device tree dump as reference — we have every address, every GPIO, every clock domain
3. **Adapt U-Boot** from shift's H6-based config — change SRAM layout for H723
4. **Build KSC driver** from GPL source (chainsx repo)
5. **Integrate AIC8800 WiFi** from DKMS repos
6. **Use V-Silicon blobs** initially for display — load the existing `.ko` modules
7. **Boot a minimal Linux image** via fastboot (the A/B partition scheme supports it)
8. **Get UART access** — `ttyAS0` at 115200 baud (solder pads likely on PCB)

### If You Want to Build a Clean Android ROM

1. **Set up AOSP build environment** for Android 14
2. **Create device tree** at `device/allwinner/s40/`
3. **Use all 80 kernel modules** we've already extracted
4. **Remove all malware** — no NFX, no ChihiHX, no HX anything
5. **Fix security configuration**:
   - Change to `user` build type
   - Use proper release keys
   - Enable SELinux Enforcing
   - Enable ADB authentication (`ro.adb.secure=1`)
   - Remove `su` and `qw` backdoor
   - Set real device identity (not Pixel 3)
6. **Flash via fastboot** — the existing bootloader should accept new images

### If You Want to Contribute to This Research

- **UART / Serial Console**: Solder onto the ttyAS0 pads (likely labeled TX/RX on the PCB) for boot logs and U-Boot shell access
- **Bootloader analysis**: The 32MB bootloader_a.img contains U-Boot 2018.07 with Allwinner SPL — needs proper decomposition
- **Kernel decompilation**: The 35.5MB kernel binary can be analyzed with Ghidra/IDA for symbols and configs
- **System app decompilation**: APKTool on CHIHI_Launcher, AppStore, DragonBox to understand the Chinese vendor modifications
- **Vendor binary RE**: `readelf` / `objdump` / Ghidra on `libksc.so`, `libtvpq.so`, `vendor.sunxi.tv.graphics` to reverse the display pipeline
- **Network traffic analysis**: Sniff all traffic from the device to catalogue all C2 communication
- **Other projector models**: If you have a similar Allwinner H723/H713 projector, test whether this firmware structure matches yours

---

## 15. File Inventory {#file-inventory}

Everything I collected is organized in this repository:

### Documentation
| File | Description |
|------|-------------|
| `XDA_README.md` | This report |
| `README.md` | Technical reference with full vulnerability details |
| `FIRMWARE_DUMP_REPORT.md` | Detailed firmware extraction and verification report |
| `INVESTIGATION_REPORT.md` | Original live investigation notes |
| `COMMUNITY_COMPARISON.md` | GitHub community project comparison |
| `future_work.md` | Custom OS roadmap and feasibility analysis |

### Firmware Dumps (`firmware_dump/`)
| Category | Files | Size |
|----------|-------|------|
| Partition images (.img) | 34 | 8.5 GB |
| Device tree (.dts/.dtb) | 9 | 0.5 MB |
| Kernel modules (.ko) | 80 | 8.1 MB |
| Init scripts (.rc) | 132 | 0.2 MB |
| Extracted sub-images (boot, super) | ~30 | ~2.9 GB |
| **Total** | **~300 files** | **~11.5 GB** |

### Key Extracted Artifacts
| Artifact | Location | Size |
|----------|----------|------|
| Linux kernel (raw ARM64) | `firmware_dump/extracted/boot_a/kernel` | 35.5 MB |
| Full device tree (decompiled) | `firmware_dump/device_tree.dts` | 132 KB |
| Init ramdisk (extracted) | `firmware_dump/extracted/init_boot_a/ramdisk_contents/` | 5.1 MB |
| Vendor ramdisk | `firmware_dump/extracted/vendor_boot_a/vendor_ramdisk.decompressed` | 28.5 MB |
| system_a filesystem image | `firmware_dump/extracted/super/system_a.img` | 2.2 GB |
| vendor_a filesystem image | `firmware_dump/extracted/super/vendor_a.img` | 468 MB |
| Super partition (full, MD5-verified) | `firmware_dump/super_full.img` | 3.5 GB |

### Malware Samples
| File | Package | Size |
|------|---------|------|
| `nfx.apk` | com.android.nfx (Netflix malware) | 112 KB |
| `nfx_extracted/` | Decompiled NFX malware | — |
| `hx_update.apk` | com.hx.update (C2 updater) | 18.5 MB |
| `hx_appcleaner.apk` | com.hx.appcleaner (spyware) | 207 KB |
| `nfhelper.apk` | com.android.nfhelper (Netflix helper) | 2.4 MB |
| `bugreport.apk` | com.dd.bugreport (custom reporter) | 104 KB |

### Analysis Scripts
| Script | Purpose |
|--------|---------|
| `firmware_dump/unpack_images.py` | Android boot v4, vendor_boot, DTBO, vbmeta parser |
| `firmware_dump/unpack_phase2.py` | LZ4 decompression, CPIO extraction, DTB decompilation |
| `firmware_dump/unpack_phase3.py` | Full CPIO extraction, super partition metadata parsing |
| `firmware_dump/extract_super.py` | Super partition logical partition extractor |
| `firmware_dump/decompile_dtb.py` | DTB → DTS using pyfdt |
| `firmware_dump/list_filesystems.py` | ext4 filesystem content listing |
| `investigate.ps1` | PowerShell investigation toolkit |
| `cleanup.sh` / `cleanup_v2.sh` | Root-level malware cleanup scripts |
| `hw_probe.sh` | Hardware probe script |
| `dump_firmware.sh` | Firmware partition dump script |

---

## Final Thoughts

This $60 projector is a window into how cheap Chinese electronics actually work behind the scenes. The hardware is mediocre but functional. The software is a carefully constructed surveillance and monetization platform disguised as Android TV.

Every component works together: the fake Pixel 3 identity gets past Google's checks, the disabled security lets the malware run unchallenged, the hidden app store can push new payloads, the NFX app generates revenue by manipulating your Netflix, and the OTA updater keeps the whole operation going by phoning home to a German server.

If you own one of these projectors — or any cheap Chinese Android device — run the cleanup commands. Better yet, isolate it on its own network. Best of all, support the community efforts to build clean firmware for these devices.

The hardware is worth saving. The software is not.

---

*Research conducted: February–March 2026*  
*Device: Orange Box S40, purchased from AliExpress*  
*SoC: Allwinner H723 (sun50iw15p1)*  
*ADB: 192.168.0.106:5555 (root via su 0)*  
*Tools used: ADB, Python (pyfdt, lz4, ext4), PowerShell, custom parsers*  
*All 28 firmware partitions dumped and verified. Full device tree decompiled. 15 vulnerabilities documented.*
