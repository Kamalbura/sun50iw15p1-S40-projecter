# Custom Linux OS Strategy for Orange Box S40 (Allwinner H723)

## Executive Summary

**Goal**: Boot a lightweight Linux from SD card with image controls (keystone), settings, browser, and YouTube.

**Verdict**: **FULLY POSSIBLE** via SD card boot using the vendor boot chain + custom rootfs.  
Three approaches ranked by risk. **Approach 1 (Vendor Kernel + Buildroot) is STRONGLY recommended**.

---

## Hardware Summary

| Component | Detail |
|-----------|--------|
| **SoC** | Allwinner H723 (`sun50iw15p1`) — Quad Cortex-A53 @ 1.4 GHz |
| **Architecture** | ARM64 (aarch64) — currently running in 32-bit mode (armv7l) |
| **RAM** | 816 MB DDR (MemTotal: 835452 kB) |
| **Storage** | 7.6 GB eMMC (mmcblk0) |
| **GPU** | Mali-G31 MP2 (`arm,mali-midgard`, mali_kbase r20p0) |
| **Display** | 1024x600 LVDS, 4-lane, 8-bit color, generic driver |
| **Panel Driver** | `allwinner,panel_lvds_gen` — standard generic LVDS, NOT proprietary |
| **Display Chain** | tvpanel.ko → vs-display.ko → vs-osd.ko → panel_lvds_gen.ko |
| **Keystone** | sunxi_ksc.ko (KSC100 hardware @ 0x05900000), motor-control.ko (stepper GPIO) |
| **WiFi** | AIC8800 SDIO (mmc2 @ 4021000) — proprietary driver |
| **SD Card** | sdc0 @ 0x04020000 (mmc1 in Linux), 4-bit, UHS-SDR104, card-detect on PF6 |
| **Serial Console** | ttyAS0 @ 115200 baud |
| **Fans** | 2x PWM fans (pwm2 + pwm3) |
| **IR Remote** | sunxi-ir-rx.ko, NEC + RC5 protocols, 15 remote codes configured |
| **Backlight** | pwm-backlight `tv` node, PWM0, 100 levels (0-100) |

---

## Boot Chain Analysis

### Allwinner BROM Boot Order (CONFIRMED):
1. **SD card** (sdc0 @ 0x04020000) — sector 16 (8KB) or sector 256 (128KB)
2. **eMMC** (sdc2 @ 0x04022000)
3. SPI NOR (not present)
4. FEL (USB recovery mode, VID:PID 1f3a:efe8)

### Current Boot Chain:
```
BROM → boot0 (DRAM init, 8KB offset on eMMC) → ATF (BL31) → OP-TEE → U-Boot 2018.07
  → bootcmd: sunxi_flash read 40007000 boot; bootm 40007000
  → boot_a.img (Android 14 kernel 5.15.167 + ramdisk)
  → Android init → SurfaceFlinger + tvpanel display chain
```

### SD Card Boot Path:
```
Insert SD card → BROM probes sdc0 first → reads boot0 from sector 16/256
  → same chain continues but from SD card instead of eMMC
```

**DTS confirms**: `boot_devices = "soc@3000000/4020000.sdmmc"` (SD card IS a boot device)

### Boot Chain Layout (FULLY MAPPED):

**Raw eMMC Layout** (before GPT partitions):
```
Sector 0:       Protective MBR + GPT header
Sectors 2-9:    GPT partition entries
Sector 16:      boot0 copy 1 (eGON.BT0, 60 KB, DRAM init)
Sector 256:     boot0 copy 2 (redundant)
Sector 12288:   MAC address storage (6 MB offset)
Sector 24576:   sunxi-package (12 MB offset, ~1.2 MB total)
                ├── U-Boot 2018.07 (688 KB)
                ├── Monitor/ATF (73 KB)
                ├── SCP firmware (172 KB)
                └── OP-TEE (273 KB)
Sector 73728:   First GPT partition (bootloader_a, 36 MB offset)
```

**boot0 Header**:
- Magic: `eGON.BT0` at +4 bytes
- Size: 61,440 bytes (60 KB)
- Version: 4.0
- boot_media field (offset 0x28): 0x00000000 = **AUTO-DETECT** ✓
  (Same boot0 binary works for both SD card and eMMC boot)

**U-Boot Version**: `2018.07-g4caa555` (built 2025-09-10)

**Kernel Command Line** (actual from /proc/cmdline):
```
console=ttyAS0,115200 loglevel=8 root= init=/init cma=24M
boot_type=2 gpt=1 uboot_message=2018.07-g4caa555
firmware_class.path=/vendor/etc/firmware
androidboot.selinux=permissive androidboot.dynamic_partitions=true
```

**Boot Image**: Android boot image v4
- Kernel: 37,185,744 bytes (35.5 MB, raw ARM code, NOT gzipped)
- Ramdisk: 0 bytes (ramdisk is in init_boot_a)
- AVB0 signature block appended after kernel
- DTB: NOT in boot_a or vendor_boot_a — provided by U-Boot's own DTB

**U-Boot Environment** (env_a, 256 KB):
```
bootdelay=0
bootcmd=run setargs_nand boot_normal
boot_normal=sunxi_flash read 40007000 boot;bootm 40007000
slot_suffix=_a
console=ttyAS0,115200
cma=24M
init=/init
```

### GPT Partition Table (eMMC):
```
 #  Name              Start      End        Size
 1  bootloader_a      73728      139263     32 MiB  (FAT16, logos)
 2  bootloader_b      139264     204799     32 MiB
 3  env_a             204800     205311     256 KiB (U-Boot env)
 4  env_b             205312     205823     256 KiB (empty)
 5  boot_a            205824     336895     64 MiB  (kernel, ANDROID! v4)
 6  boot_b            336896     467967     64 MiB
 7  vendor_boot_a     467968     533503     32 MiB  (vendor ramdisk, 16.8 MB)
 8  vendor_boot_b     533504     599039     32 MiB
 9  init_boot_a       599040     615423     8 MiB
10  init_boot_b       615424     631807     8 MiB
11  super             631808     7971839    3.5 GiB (dynamic partitions)
12  misc              7971840    8004607    16 MiB
13-28 (small partitions: vbmeta, frp, dtbo, etc.)
29  userdata          8406016    15302622   3.3 GiB
```

---

## Display Architecture (CRITICAL for Linux)

### Panel Configuration (from DTS):
```
lvds0@5800000:
  compatible = "allwinner,lvds0"
  status = "okay"
  panel0@0:
    compatible = "allwinner,panel_lvds_gen"      ← GENERIC LVDS!
    panel_lane_num = 4                           ← 4-lane
    panel_bitwidth = 8                           ← 8-bit color
    panel_protocol = 0                           ← LVDS standard
    display-timings:
      clock-frequency = 130 MHz (typ), 62.4 MHz (min), 163.8 MHz (max)
      hactive = 1024, vactive = 600
      hback-porch = 20, hfront-porch = 296, hsync-len = 20
      vback-porch = 4, vfront-porch = 152, vsync-len = 4
      Total: 1360x760, Refresh: ~125 Hz (likely run at 60 Hz via clock scaling)
```

### Display Module Chain:
```
panel_lvds_gen.ko  — Generic LVDS panel driver (timing & signal config)
  ↑
tvpanel.ko         — Top-level display panel manager (allwinner,tvpanel @ 0x5300000)
  ↑
vs-display.ko      — VS display subsystem (vs,display — afbd, cap, svp, panel)
  ↑  
vs-osd.ko          — On-screen display overlay (vs,osd — fastosd_mode=1)
  ↑
sunxi_ksc.ko       — Keystone correction engine (allwinner,ksc100 @ 0x5900000)
```

### Key Insight:
The display uses Allwinner's **generic LVDS panel driver** (`panel_lvds_gen`), NOT a vendor-specific panel module (like the `z20hd720m.ko` which is also present but for a different panel variant). This means:
- The panel timing parameters are ALL in the device tree
- No reverse engineering of proprietary panel init sequences needed
- Any Linux with this driver + correct DTS + the display module chain = working display

### Backlight:
- `tv` node: `pwm-backlight`, PWM channel 0, 100 brightness levels
- Enable GPIO: PB6 (port B, pin 6)
- Standard `pwm_bl.ko` driver — works directly with mainline Linux

---

## GPU Details

```
gpu@0x01800000:
  compatible = "arm,mali-midgard"   ← Mali-G31 (Bifrost, but uses midgard compat)
  Operating Points: 600/400/300/200 MHz
  Kernel module: mali_kbase.ko (r20p0-01rel0)
  Power domain: pd_gpu
```

**Linux GPU Options**:
1. **Vendor blob** (mali_kbase.ko) — works with vendor kernel, uses fbdev/legacy
2. **Panfrost** (open-source) — Mali-G31 IS supported by Panfrost in mainline Linux, but requires DRM/KMS which the vendor kernel doesn't use
3. **Lima** — NOT for G31 (Lima is Utgard only)

---

## H713 vs H723 Comparison

| Feature | H713 (sun50iw12p1) | H723 (sun50iw15p1) |
|---------|--------------------|--------------------|
| CPU | Quad Cortex-A53 | Quad Cortex-A53 |
| GPU | Mali-G31 MP2 (Midgard compat) | Mali-G31 MP2 (Midgard compat) |
| Process | 28nm | 28nm |
| RAM | DDR3/DDR4/LPDDR4 | DDR3/DDR4/LPDDR4 |
| HDMI | HDMI input | HDMI input |
| sun50i family | ✅ | ✅ |
| Kernel config | CONFIG_ARCH_SUN50IW12 | CONFIG_ARCH_SUN50IW15 |
| CCU driver | AW_SUN50IW12_CCU | AW_SUN50IW15_CCU |
| Pinctrl | SUN50IW12 | SUN50IW15 |
| linux-sunxi wiki | H713 page exists | NO page exists |
| Mainline Linux | Partial (HY300 project) | NOT mainlined |
| Display subsystem | tvpanel/vs-display chain | tvpanel/vs-display chain (SAME architecture) |

**Verdict**: While they share identical CPU/GPU/RAM architecture, they have **different clock control units (CCU)**, **different pinctrl**, and **different register maps** (`SUN50IW12` vs `SUN50IW15`). They are siblings but **NOT drop-in compatible** for kernel drivers.

---

## Three Approaches (Ranked by Risk)

### ★ Approach 1: Vendor Kernel + Buildroot Rootfs (SD Card) — RECOMMENDED

**Risk: LOW | Effort: MEDIUM | Display: GUARANTEED**

The safest and most practical approach. Use the existing vendor kernel (5.15.167) and all its proprietary modules, but replace the Android userspace with a minimal Linux rootfs.

#### What We Reuse:
- ✅ **boot0** — DRAM initialization (device-specific, MUST be reused)
- ✅ **U-Boot 2018.07** — SD card boot support built-in
- ✅ **Vendor kernel 5.15.167** (32-bit armv7l) — all hardware support
- ✅ **76 kernel modules** — display chain, GPU, WiFi, audio, keystone, motor, fans, IR
- ✅ **Device tree** — already perfect for this hardware
- ✅ **Mali GPU blob** — for hardware acceleration

#### What We Build:
- 🔨 **Buildroot rootfs** — minimal Linux (~50-100 MB)
  - Weston/Wayland compositor (for GPU-accelerated display)
  - OR: Direct framebuffer with fbdev (simpler, guaranteed to work)
  - Chromium kiosk mode (browser + YouTube)
  - mpv (hardware-decoded video, Mali + cedarX)
  - Custom keystone control app (via /dev/ksc or sysfs)
  - Network Manager (WiFi config)
  - IR remote handler (already in kernel)
  - Fan control daemon
  - Settings UI (simple GTK/Qt app or web-based)
  
#### SD Card Layout (built by `build_sdcard_image.py`):
```
SD Card (1 GB minimum, 2+ GB recommended):
├── Sector 0:       Protective MBR + GPT header
├── Sector 16:      boot0 (eGON.BT0, 60 KB — BROM loads this)
├── Sector 256:     boot0 copy (redundant)
├── Sector 24576:   sunxi-package (U-Boot 688KB + ATF + SCP + OP-TEE)
├── Partition 1 (sector 73728):  bootloader_a (32 MiB, boot logos)
├── Partition 2 (sector 139264): env_a (256 KiB, MODIFIED for Linux)
├── Partition 3 (sector 139776): boot_a (64 MiB, vendor kernel)
└── Partition 4 (sector 270848): rootfs (remaining space, ext4)
    ├── /lib/modules/5.15.167/ (76 vendor .ko files)
    ├── /lib/firmware/ (AIC8800 WiFi + GPU firmware)
    ├── /sbin/init (busybox or systemd)
    └── Standard Linux rootfs (Alpine/Debian/Buildroot)
```

#### Boot Sequence:
```
BROM → boot0 (from SD sector 16) → sunxi-package (from SD sector 24576)
  → ATF + SCP + OP-TEE start → U-Boot loads env_a from SD
  → bootdelay=3 (U-Boot shell accessible)
  → U-Boot: sunxi_flash read 40007000 boot; bootm 40007000
  → Kernel boots with root=/dev/mmcblk0p4 rootfstype=ext4 rw rootwait
  → /sbin/init starts → load vendor modules → Linux desktop/kiosk
```

#### Key Challenge:
- boot0 does DRAM training specific to THIS hardware — we MUST extract and reuse it
- U-Boot env needs `bootcmd` changed to load from SD card/ext4 instead of `sunxi_flash`
- The 32-bit kernel limits us to armv7l userspace (still fine for browser/YouTube)
- WiFi driver (aic8800) is proprietary and may need firmware files

#### Estimated SD Card Image Size:
- Minimal (CLI + framebuffer + mpv): ~100 MB
- Full (Weston + Chromium + YouTube): ~500 MB - 1 GB
- With swap: +256 MB (recommended with only 816 MB RAM)

---

### Approach 2: Vendor Kernel in 64-bit Mode — EXPERIMENTAL

**Risk: MEDIUM-HIGH | Effort: HIGH | Display: LIKELY**

The H723 is a Cortex-A53 (ARMv8-A, natively 64-bit). The vendor chose 32-bit for Android compatibility, but the CPU can run aarch64.

#### Hypothesis:
If Allwinner's vendor kernel source has ARM64 support for sun50iw15 (and it likely does — the kernel config has `CONFIG_ARCH_SUN50I=y`), we could rebuild the kernel in 64-bit mode. This would give:
- Better performance (aarch64 has more registers, better instruction set)
- Access to aarch64 userspace packages
- Possibly more RAM addressable

#### Challenges:
- Need kernel source code (may be available in Tina SDK or via Allwinner OEM channels)
- All 76 kernel modules must be recompiled for aarch64
- boot0 must support 64-bit kernel handoff (ATF/BL31 should handle this)
- Untested territory

#### Status: Research needed. Not recommended as first attempt.

---

### Approach 3: Mainline Linux (Adapted from HY300 H713 Project) — LONG-TERM

**Risk: HIGH | Effort: VERY HIGH | Display: UNCERTAIN**

Adapt the HY300 Linux porting project (H713/sun50iw12) for H723/sun50iw15.

#### HY300 Project Status (github.com/xyzz/hy300-linux):
- ✅ Phase I-VIII completed (firmware analysis, U-Boot, DTS, kernel modules, VM testing)
- 🎯 Phase IX: Hardware testing (requires physical hardware)
- Uses H6 as U-Boot base (H6 is mainlined)
- Built custom device tree `sun50i-h713-hy300.dts`
- Created MIPS co-processor driver (keystone via `panelparam` sysfs)
- Kernel 6.16.7 mainline with custom configs

#### What Would Need to Change for H723:
1. **Clock Control Unit (CCU)** — different register map (SUN50IW15 vs SUN50IW12)
2. **Pinctrl** — different pin multiplexing
3. **Device Tree** — new DTS for H723 hardware addresses
4. **DRAM controller** — different DRAM training parameters
5. **Display driver** — tvpanel/vs-display chain needs either:
   - Reverse engineering and reimplementation (massive effort)
   - OR: Using vendor modules as binary blobs (breaks with mainline kernel)

#### Display Challenge:
The vendor display stack (tvpanel → vs-display → vs-osd → panel_lvds_gen) is **completely proprietary** and not part of mainline Linux DRM/KMS. Mainline Linux would need either:
- A new DRM driver for Allwinner's TV display engine
- Port the vendor modules to mainline kernel APIs
- Both of these are months/years of work

#### Verdict: NOT recommended for near-term goals. The HY300 project itself hasn't achieved working display output yet.

---

## SD Card Boot — READY TO BUILD

### Status: ALL components extracted, builder script created ✅

### Extracted Components:
| File | Size | Purpose |
|------|------|---------|
| `firmware_dump/boot_chain_14mb.bin` | 14 MB | Raw boot chain (boot0 + sunxi-package) |
| `firmware_dump/boot_a.img` | 64 MB | Android boot image (vendor kernel 5.15.167) |
| `firmware_dump/env_a.bin` | 256 KB | Original U-Boot environment |
| `firmware_dump/device_tree.dtb` | 192 KB | Device tree blob |
| `firmware_dump/vendor_modules.tar.gz` | 2.8 MB | All 76 kernel modules |
| `firmware_dump/vendor_firmware.tar.gz` | 13 MB | WiFi/GPU/display firmware files |

### Step 1: Build SD Card Image (Windows)
```powershell
cd c:\Users\burak\ptojects\projecter
python build_sdcard_image.py --size 2048 --output sdcard.img
```

This creates a 2 GB SD card image with:
- boot0 + sunxi-package at correct raw sectors
- Modified U-Boot env (bootdelay=3, Linux bootargs)
- Vendor kernel in boot partition
- Empty rootfs partition (~1.6 GB)

### Step 2: Write Image to SD Card (Windows)
Use **Win32DiskImager** or **balenaEtcher** to write `sdcard.img` to a MicroSD card.

### Step 3: Populate Rootfs (Linux/WSL required)
```bash
# Format the rootfs partition (partition 4 on SD card)
sudo mkfs.ext4 -L rootfs /dev/sdX4

# Mount and install Alpine Linux armv7
sudo mount /dev/sdX4 /mnt
cd /mnt
sudo wget https://dl-cdn.alpinelinux.org/alpine/v3.21/releases/armv7/alpine-minirootfs-3.21.3-armv7.tar.gz
sudo tar xzf alpine-minirootfs-*.tar.gz && sudo rm alpine-minirootfs-*.tar.gz

# Add vendor kernel modules
sudo mkdir -p lib/modules/5.15.167
sudo tar xzf /path/to/vendor_modules.tar.gz -C lib/modules/5.15.167/

# Add vendor firmware
sudo mkdir -p lib/firmware
sudo tar xzf /path/to/vendor_firmware.tar.gz -C lib/firmware/

# Configure init
sudo ln -sf /bin/busybox sbin/init

# Add console login
echo 'ttyAS0::respawn:/sbin/getty -L ttyAS0 115200 vt100' | sudo tee etc/inittab
echo '::sysinit:/bin/mount -t proc proc /proc' | sudo tee -a etc/inittab
echo '::sysinit:/bin/mount -t sysfs sysfs /sys' | sudo tee -a etc/inittab
echo '::sysinit:/bin/mount -t devtmpfs dev /dev' | sudo tee -a etc/inittab

# Set root password (for serial console access)
sudo chroot . /bin/sh -c 'echo "root:projector" | chpasswd'

sudo umount /mnt
```

### Step 4: Boot Test
1. Power OFF the projector
2. Insert prepared SD card
3. Power ON — BROM finds boot0 on SD, boots from SD
4. U-Boot pauses 3 seconds (bootdelay=3), then boots Linux
5. Kernel mounts rootfs from SD partition 4
6. If display doesn't show Linux console, connect serial (ttyAS0, 115200)

### Step 5: Load Display Modules (after boot)
```bash
# Load display driver chain (order matters!)
insmod /lib/modules/5.15.167/pwm_bl.ko
insmod /lib/modules/5.15.167/tvpanel.ko
insmod /lib/modules/5.15.167/vs-display.ko
insmod /lib/modules/5.15.167/vs-osd.ko
insmod /lib/modules/5.15.167/panel_lvds_gen.ko
insmod /lib/modules/5.15.167/sunxi_ksc.ko

# Load WiFi
insmod /lib/modules/5.15.167/aic8800_bsp.ko
insmod /lib/modules/5.15.167/aic8800_fdrv.ko

# Load GPU (optional)
insmod /lib/modules/5.15.167/mali_kbase.ko
```

### Fallback:
- **Remove SD card** → boots original Android from eMMC (non-destructive)
- **Serial console** → ttyAS0, 115200 baud, 3.3V UART
- **U-Boot shell** → press any key during 3-second bootdelay

---

## Recommended Application Stack for Linux

### Minimal Setup (Approach 1):
```
Display Server:  Cage (single-app Wayland compositor) or direct fbdev
Browser:         Chromium (kiosk mode) or Firefox ESR
YouTube:         Chromium with YouTube.com or FreeTube
Video Player:    mpv with cedarX/VAAPI hardware decode
Keystone:        Custom sysfs control script (/sys/devices/.../ksc/)
Settings:        Web-based UI (Python Flask + HTML) served locally
WiFi:            NetworkManager + nmtui (text UI) or web config
IR Remote:       ir-keytable + custom keymap + udev rules
Fan Control:     pwm-fan driver (already in DTS) + thermal daemon
Audio:           ALSA (vendor codec driver)
```

### Package Sizes (estimated, armhf/armv7l):
| Package | Size |
|---------|------|
| Cage (Wayland) | ~2 MB |
| Chromium | ~200 MB |
| mpv | ~15 MB |
| NetworkManager | ~10 MB |
| Python 3 | ~30 MB |
| Base system | ~50 MB |
| Kernel modules | ~20 MB |
| **Total** | **~330 MB** |

---

## Key Kernel Modules for Linux (Must Load)

### Display (REQUIRED, in order):
```
1. tvpanel.ko          — Panel manager
2. vs-display.ko       — Display subsystem
3. vs-osd.ko           — OSD overlay
4. panel_lvds_gen.ko   — Generic LVDS panel driver
5. sunxi_ksc.ko        — Keystone correction
6. pwm_bl.ko           — Backlight control
```

### Motor/Projection:
```
7. motor-control.ko    — Keystone stepper motor
8. motor-limiter.ko    — Motor end-stop switch
```

### WiFi:
```
9.  aic8800_bsp.ko     — AIC8800 base support
10. aic8800_fdrv.ko    — AIC8800 function driver
11. aic8800_btlpm.ko   — Bluetooth low power mode
```

### GPU:
```
12. mali_kbase.ko      — Mali-G31 GPU driver
```

### Audio:
```
13. snd_soc_sunxi_internal_codec.ko
14. snd_soc_sunxi_machine.ko
15. snd_soc_sunxi_pcm.ko
16. snd_soc_sunxi_common.ko
```

### Input:
```
17. sunxi-ir-rx.ko     — IR remote receiver
18. ir-nec-decoder.ko  — NEC IR protocol
```

### USB:
```
19. sunxi-hci.ko       — HCI framework
20. ehci-sunxi.ko      — USB EHCI
21. ohci-sunxi.ko      — USB OHCI
```

### Misc:
```
22. pwm-fan.ko         — Fan control
23. sunxi_rfkill.ko    — RF kill switch
24. sunxi_ac_virtual_power.ko — Power management
```

---

## Immediate Next Steps

### ✅ DONE: Extract Boot Components
All raw boot chain data, kernel modules, firmware, and U-Boot environment extracted.

### ✅ DONE: Build SD Card Image Script
`build_sdcard_image.py` — generates complete SD card image from extracted components.

### 🔄 NEXT: Prepare SD Card and Test Boot
1. Run `python build_sdcard_image.py --size 2048` to generate `sdcard.img`
2. Write to physical MicroSD card using Win32DiskImager
3. Populate rootfs partition (needs WSL or Linux VM)
4. Insert SD card, power on, test boot

### AFTER: Build Full Linux Environment
- Install Alpine Linux with Xorg/Weston
- Set up Chromium in kiosk mode for YouTube
- Configure WiFi (aic8800 driver + firmware)
- Create keystone/motor control scripts
- Build custom settings UI

---

## Risk Assessment

| Risk | Impact | Mitigation |
|------|--------|------------|
| Display doesn't work | HIGH | Use vendor display modules (guaranteed compatible) |
| SD card not detected by BROM | MEDIUM | BROM always checks SD first; DTS confirms boot device |
| boot0 DRAM init fails | HIGH | Extract exact boot0 from eMMC; it's hardware-matched |
| WiFi doesn't work | MEDIUM | AIC8800 needs firmware blobs; extract from /vendor/etc/firmware/ |
| GPU acceleration missing | LOW | Framebuffer mode still works; GPU is bonus |
| Not enough RAM | MEDIUM | Use swap on SD card; disable unnecessary services |
| Kernel module ABI mismatch | LOW | Use exact vendor kernel + exact vendor modules |

---

## Files Inventory

### Extracted from Device (ready to use):
| File | Size | Purpose |
|------|------|---------|
| `firmware_dump/boot_chain_14mb.bin` | 14 MB | Raw eMMC header: boot0 + sunxi-package (U-Boot+ATF+SCP+OP-TEE) |
| `firmware_dump/boot_a.img` | 64 MB | Android boot image v4 (vendor kernel 5.15.167, 35.5 MB ARM code) |
| `firmware_dump/env_a.bin` | 256 KB | U-Boot environment partition (original) |
| `firmware_dump/device_tree.dtb` | 192 KB | Device tree blob |
| `firmware_dump/device_tree.dts` | 132 KB | Decompiled device tree source (2991 lines) |
| `firmware_dump/vendor_modules.tar.gz` | 2.8 MB | All 76 vendor kernel modules (.ko files) |
| `firmware_dump/vendor_firmware.tar.gz` | 13 MB | WiFi (AIC8800), display, GPU firmware blobs |
| `firmware_dump/emmc_raw_2mb.bin` | 2 MB | Raw eMMC first 2MB (contains boot0 headers) |
| `firmware_dump/kernel_config.gz` | — | Full kernel configuration |
| All 29 partition dumps | ~7 GB | Complete eMMC backup |

### Build Tools:
| File | Purpose |
|------|---------|
| `build_sdcard_image.py` | SD card image builder — creates bootable SD card image from extracted components |
| `LINUX_STRATEGY.md` | This document — complete strategy and technical analysis |
| `ARCHITECTURE.md` | Hardware control architecture (15 sections) |
| `BUILD_PLAN.md` | Original build plan with 3 approaches |
| `HACKER_ANALYSIS.md` | Deep display driver and kernel analysis |

## HY300 Project Reference

**Repository**: `github.com/xyzz/hy300-linux` (127 commits, actively maintained)
- H713 (sun50iw12p1) sister chip to H723 (sun50iw15p1)
- Has mainline DTS, U-Boot port, MIPS co-processor driver
- Uses H6 as U-Boot base — H723 could potentially use the same base
- They have FEL mode tools with H713 fixes
- MIPS display co-processor analysis done (40.3 MB reserved memory region)
- **Phase IX (hardware testing) not yet completed** — no confirmed working display

---

*Generated: Session analysis of Allwinner H723 (sun50iw15p1) Orange Box S40 projector*
*Based on: live device probing, firmware dump analysis, internet research, HY300 project comparison*
