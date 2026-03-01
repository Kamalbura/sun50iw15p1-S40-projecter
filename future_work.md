# Future Work: Custom OS Build for Orange Box S40

## Overview

This document outlines the feasibility, approach, and requirements for building a clean custom OS image for the Orange Box S40 projector that **preserves all hardware features** while **eliminating all security vulnerabilities**.

---

## 1. Custom OS Options

### Option A: Clean Android 14 (AOSP) — RECOMMENDED

**Feasibility: HIGH**

Build a clean Android 14 (AOSP) image from source with proper security configuration.

#### Pros
- Same kernel (5.15.167), same drivers — maximum hardware compatibility
- All existing .ko modules can be reloaded as-is
- Android TV Launcher available from AOSP
- A/B partition scheme already supports flashing
- U-Boot bootloader can be reused

#### Cons
- No Google certification (no Play Store, no Widevine L1 without licensing)
- Must extract and repackage proprietary blobs
- Display pipeline is vendor-specific (V-Silicon IP)

#### Required Proprietary Blobs

| Blob | Source | Purpose |
|------|--------|---------|
| mali_kbase.ko | /vendor/lib/modules/ | ARM Mali GPU driver |
| aic8800_fdrv.ko + firmware | /vendor/lib/modules/ + /vendor/firmware/ | WiFi driver |
| aic8800_bsp.ko | /vendor/lib/modules/ | WiFi BSP |
| aic8800_btlpm.ko | /vendor/lib/modules/ | Bluetooth LPM |
| vs_display.ko | /vendor/lib/modules/ | V-Silicon display |
| vs_osd.ko | /vendor/lib/modules/ | V-Silicon OSD |
| tvpanel.ko | /vendor/lib/modules/ | Allwinner TV panel |
| sunxi_ksc.ko | /vendor/lib/modules/ | Keystone correction |
| sunxi_tvtop.ko | /vendor/lib/modules/ | TV top controller |
| sunxi_tvtop_adc.ko | /vendor/lib/modules/ | TV ADC input |
| panel_lvds_gen.ko | /vendor/lib/modules/ | LVDS panel driver |
| motor_control.ko | /vendor/lib/modules/ | Stepper motor |
| motor_limiter.ko | /vendor/lib/modules/ | Motor limiter |
| stmvl53l1.ko | /vendor/lib/modules/ | ToF sensor |
| sc7a20e.ko | /vendor/lib/modules/ | Accelerometer |
| kxtj3.ko | /vendor/lib/modules/ | Accelerometer (alt) |
| sunxi_ir_rx.ko | /vendor/lib/modules/ | IR receiver |
| sunxi_ve.ko | /vendor/lib/modules/ | Video engine (Cedar) |
| hidtvreg_dev.ko | /vendor/lib/modules/ | HiDTV register |
| snd_alsa_trid.ko | /vendor/lib/modules/ | Audio driver |
| All sunxi audio .ko | /vendor/lib/modules/ | Audio subsystem |

All 80 kernel modules have been pulled to `firmware_dump/kernel_modules/`.

#### Build Steps

1. **Set up AOSP build environment** for Android 14 (API 34)
2. **Create device tree** for Allwinner H723 (`device/allwinner/s40/`)
3. **Extract vendor blobs** (already done — `firmware_dump/kernel_modules/`)
4. **Reuse existing kernel** (boot_a.img already dumped) OR build from Allwinner BSP sources
5. **Configure proper security**:
   - `ro.build.type=user`
   - `ro.build.tags=release-keys`
   - SELinux = Enforcing
   - `ro.adb.secure=1`
   - Remove su/qw binaries
   - Remove all com.hx.* and com.chihihx.* packages
   - Remove NFX malware
   - Remove preinstall scripts
6. **Flash via fastboot** (A/B scheme supports this)
7. **Test all hardware features**

---

### Option A.5: Fork shift's H713 Linux Work → Adapt for H723 — NEW RECOMMENDED

**Feasibility: HIGH**

The GitHub project [shift/sun50iw12p1-research](https://github.com/shift/sun50iw12p1-research) (24 ⭐) has completed 8 full phases of mainline Linux porting for the **Allwinner H713** — the sister SoC to our H723. Their software stack is **complete** and entering hardware testing. Their work is directly transferable.

#### What Already Exists (from shift)

| Component | Status | Lines/Size |
|-----------|--------|------------|
| Mainline device tree | ✅ Complete | 967 lines (14KB DTB) |
| U-Boot binary | ✅ Built | 732KB (H6 base config) |
| MIPS co-processor driver | ✅ Complete | 905 lines (NOT needed for H723) |
| Panfrost GPU | ✅ Integrated | Mainline Mali T720 |
| V4L2 HDMI capture | ✅ Complete | 1,760 lines |
| NixOS VM + Kodi | ✅ Built | Full OS image |
| FEL mode tooling | ✅ Patched | sunxi-fel with H713 fixes |
| KSC keystone source | ✅ Found | GPL-2.0 in chainsx/u-boot-sun60i |
| AIC8800 WiFi driver | ✅ Found | Multiple DKMS repos |

#### What We Need to Adapt for H723

| Task | Effort | Notes |
|------|--------|-------|
| Fork DTS, change to H723 addresses | Medium | Remove MIPS co-proc, add V-Silicon display |
| Update U-Boot SRAM layout | Low-Medium | May differ from H713 (0x104000) |
| Add V-Silicon display support | Hard | Use binary blob initially |
| Test FEL mode for H723 | Low | May have same BROM bug as H713 |
| Build AIC8800D80 WiFi | Low | DKMS packages exist |
| Build KSC from source | Low | Full GPL source available |

#### Key Repos

- **shift/sun50iw12p1-research** — Complete H713 Linux stack
- **srgneisner/hy300-linux-porting** — Privacy-focused Armbian for H713
- **chainsx/u-boot-sun60i** — KSC keystone source code (GPL-2.0)
- **radxa/allwinner-bsp** — IOMMU driver references our sun50iw15 SoC
- **fqrious/aic8800-dkms** — AIC8800 WiFi DKMS for Linux

See [COMMUNITY_COMPARISON.md](COMMUNITY_COMPARISON.md) for full analysis.

---

### Option B: Armbian / Mainline Linux

**Feasibility: MEDIUM-HIGH** (upgraded from LOW-MEDIUM after community research)

Build a Linux distribution (Armbian) for the H723 SoC.

#### Pros
- True open-source OS, full security control
- Active sunxi community (linux-sunxi.org)
- Armbian has templates for Allwinner H-series

#### Cons
- H723 is relatively new — limited mainline support
- Display pipeline (V-Silicon) has NO Linux mainline driver
- Keystone correction (sunxi_ksc) is proprietary
- tvpanel/tvtop drivers are proprietary Allwinner Android-only
- Motor control needs custom userspace driver
- WiFi (AIC8800) has no mainline driver
- Would need to port all modules or find alternatives
- No Android TV apps (Netflix, YouTube, etc.)

#### Mainline Kernel Status for H723 (UPDATED after community research)

| Component | Mainline Status | Notes |
|-----------|----------------|-------|
| CPU | YES (sunxi, DT exists) | A53 is well-supported |
| USB | YES (EHCI/OHCI/OTG) | Mainline drivers work |
| SD/MMC | YES (sunxi-mmc) | Standard Allwinner |
| IR | YES (sunxi-ir) | Mainline driver exists |
| PWM | YES (sunxi-pwm) | Fan/backlight should work |
| GPIO | YES | Standard Allwinner |
| I2C | YES | For sensors |
| GPU (Mali) | ✅ YES (Panfrost) | **Confirmed working on sister H713** by shift project |
| WiFi (AIC8800) | ✅ OUT-OF-TREE | **DKMS packages exist** (fqrious/aic8800-dkms, tested kernel 6.7) |
| Display (V-Silicon) | **NO** | Completely proprietary — ONLY remaining critical blocker |
| Keystone (sunxi_ksc) | ✅ **SOURCE EXISTS** | **GPL-2.0 source found in chainsx/u-boot-sun60i** |
| Video Engine (Cedar) | PARTIAL (cedrus) | cedrus supports H.264/H.265 |
| Audio (Trident) | **NO** | snd_alsa_trid is proprietary |
| ToF (VL53L1) | YES (iio) | Mainline IIO driver exists |
| Accelerometers | YES (iio) | SC7A20E/KXTJ3 supported |
| IOMMU | ✅ YES | **Source exists in radxa/allwinner-bsp, references sun50iw15** |

**Revised Verdict**: Only **V-Silicon display** and **Trident audio** remain proprietary. KSC keystone and WiFi now have open source. Use binary blobs for display initially, reverse engineer later. **Feasibility has increased significantly.**

---

### Option C: Android TV Custom ROM (community)

**Feasibility: MEDIUM**

Find or adapt an existing Android TV ROM for Allwinner TV SoCs.

#### Pros
- Community ROMs may already exist for similar H6/H616/H618 boards
- Shares much of the same driver ecosystem
- Android TV framework handles HDMI CEC natively

#### Cons
- H723 is a specialized TV SoC — not common in SBC community
- Would still need same proprietary blobs
- OrangePi / Tanix TV boxes use different display pipelines
- No known community ROM specifically for H723

---

## 2. Hardware Feature Preservation Plan

### Feature: Auto Keystone Correction

**Driver chain**: SC7A20E accelerometer → Android sensor HAL → keystone service → sunxi_ksc.ko → vs_osd → display

**Preservation approach**:
1. Keep all kernel modules: `sc7a20e.ko`, `kxtj3.ko`, `sunxi_ksc.ko`, `vs_osd.ko`, `vs_display.ko`, `tvpanel.ko`, `panel_lvds_gen.ko`
2. Keep vendor init scripts that load these modules (`init.hx.rc` contains module loading)
3. Identify and preserve the Android keystone correction service (likely in framework or HX system APK)
4. Test: Write to `/sys/class/projection/mode` and verify keystone adjusts

**Risk**: Medium — The keystone correction may depend on a proprietary Android framework service (ChihiHX or Allwinner TV framework app). Need to identify this service.

**Research needed**:
- Decompile `framework.jar` and `services.jar` to find keystone-related classes
- Identify which system service reads the accelerometer and writes to sunxi_ksc
- Check if `tvserver` (port 1234) handles keystone coordination
- Look for `com.softwinner` or `com.allwinner` packages

### Feature: Auto Focus

**Driver chain**: VL53L1 ToF sensor → distance measurement → motor_control.ko → stepper motor → lens movement

**Preservation approach**:
1. Keep: `stmvl53l1.ko`, `motor_control.ko`, `motor_limiter.ko`
2. Preserve any Android service that manages auto-focus (likely HX app)
3. Test script exists: `/system/bin/stepper_motor_test.sh`
4. Manual control: `echo "1,100" > /sys/devices/platform/motor0/motor_ctrl`

**Risk**: Low — Motor control is straightforward GPIO/sysfs. ToF sensor has mainline support.

### Feature: HDMI CEC

**Driver chain**: Allwinner CEC controller (built-in) → Android HDMI CEC HAL → CEC framework

**Preservation approach**:
1. CEC is built into the kernel (not a module) — no driver issue
2. Android CEC HAL is standard: `android.hardware.tv.cec@1.0-service`
3. Keep CEC configuration in init scripts
4. Test: `dumpsys hdmi_control` should show ports and CEC status

**Risk**: Very Low — CEC is standard Android/Allwinner functionality.

### Feature: IR Remote Control

**Driver chain**: sunxi_ir_rx → rc-core → NEC/RC5 decoder → Android input → KeyEvent

**Preservation approach**:
1. Keep: `sunxi_ir_rx.ko`, `ir_nec_decoder.ko`, `ir_rc5_decoder.ko`
2. Keep keylayout files in `/system/usr/keylayout/` and `/vendor/usr/keylayout/`
3. IR is standard Linux input subsystem — fully compatible

**Risk**: Very Low.

### Feature: WiFi

**Preservation approach**:
1. Keep: `aic8800_fdrv.ko`, `aic8800_bsp.ko`, `aic8800_btlpm.ko`
2. Keep firmware: `/vendor/firmware/aic8800D80/` (fmacfw.bin, agcram.bin, etc.)
3. Keep calibration: `/vendor/firmware/` WiFi calibration files
4. Keep: `sunxi_rfkill.ko` (RF kill switch)

**Risk**: Low — Same driver, same firmware.

### Feature: Audio

**Preservation approach**:
1. Keep all `snd_*` modules (snd_alsa_trid, sunxi audio modules)
2. Keep ALSA configuration files
3. Keep audio HAL

**Risk**: Low.

---

## 3. Security Hardening Checklist (for Custom OS)

### Must Fix (Critical/High)

- [ ] **SELinux**: Set to Enforcing mode in kernel cmdline
- [ ] **ADB**: Set `ro.adb.secure=1`, disable WiFi ADB by default
- [ ] **Root access**: Remove `/system/xbin/su` and `/system/bin/qw`
- [ ] **Build type**: Change to `user` with proper release keys
- [ ] **NFX Malware**: Remove `com.android.nfx` and all traces
- [ ] **ChihiHX Store**: Remove `com.chihihx.store`
- [ ] **OTA C2**: Remove `com.hx.update`, block C2 IPs
- [ ] **Device identity**: Set genuine device properties
- [ ] **Fake Play Store**: Remove Tubesky (`com.android.vending` impostor)
- [ ] **Root scripts**: Remove `apply_patch.sh`, `copy_rom.sh`, `oem_preinstall.sh`
- [ ] **Preinstall**: Remove `/vendor/preinstall/` directory contents

### Should Fix (Medium)

- [ ] **Device permissions**: Restrict `/dev/hxext`, `/dev/pddev`, `/dev/video0`
- [ ] **GMS disabler**: Remove `appsdisable` script
- [ ] **Excessive perms**: Strip unnecessary permissions from HX apps

### Nice to Have (Low)

- [ ] **NFS/CIFS**: Blacklist unnecessary network filesystem modules
- [ ] **Firewall**: Add basic iptables rules in init

---

## 4. Flashing & Recovery Plan

### Current Backup Status

All critical partitions have been dumped to `firmware_dump/`:
- bootloader_a.img — Can restore bootloader
- boot_a.img — Can restore kernel/ramdisk
- vendor_boot_a.img — Can restore vendor boot
- init_boot_a.img — Can restore init boot
- super.img — **PARTIAL** (needs re-dump, see below)
- All vbmeta partitions backed up
- DTBO backed up

### Restoring to Factory State

```bash
# Connect via ADB
adb connect 192.168.0.106:5555

# Reboot to fastboot/bootloader
adb reboot bootloader

# Flash partitions (fastboot mode)
fastboot flash bootloader_a bootloader_a.img
fastboot flash boot_a boot_a.img
fastboot flash vendor_boot_a vendor_boot_a.img
fastboot flash init_boot_a init_boot_a.img
fastboot flash dtbo_a dtbo_a.img
fastboot flash vbmeta_a vbmeta_a.img
fastboot flash vbmeta_system_a vbmeta_system_a.img
fastboot flash vbmeta_vendor_a vbmeta_vendor_a.img
# super partition (once complete dump obtained)
fastboot flash super super.img
```

### TODO: Complete Super Partition Dump

The super partition dump is incomplete (1.75GB of 3.5GB). Options:

1. **Stream directly to PC** (recommended):
```bash
adb exec-out "su 0 dd if=/dev/block/mmcblk0p11 bs=1048576" > firmware_dump/super_full.img
```

2. **Dump to USB/SD on device**:
```bash
# Insert USB drive, mount it
adb shell su 0 mount /dev/block/sda1 /mnt/usb
adb shell su 0 dd if=/dev/block/mmcblk0p11 of=/mnt/usb/super.img bs=65536
# Then pull from USB
adb pull /mnt/usb/super.img firmware_dump/super_full.img
```

3. **Dump in chunks**:
```bash
# Dump 500MB chunks
for i in 0 1 2 3 4 5 6; do
  adb exec-out "su 0 dd if=/dev/block/mmcblk0p11 bs=1048576 skip=$((i*500)) count=500" > super_part_$i.img
done
# Concatenate on PC
cat super_part_*.img > super_full.img
```

---

## 5. Research Tasks

### Immediate Priority

- [ ] **Complete super partition dump** — Required for full backup/restore
- [ ] **Identify keystone Android service** — Which APK/service orchestrates auto-keystone?
  - Check `tvserver` source/behavior
  - Dump `framework.jar` and search for keystone classes
  - Check for `com.allwinner` or `com.softwinner` packages
- [ ] **Test fastboot mode** — Verify device enters fastboot and accepts flashing
  - `adb reboot bootloader` — does it enter fastboot?
  - Or Allwinner FEL mode (hold button during boot)?
- [ ] **Identify Allwinner FEL/PhoenixSuit support** — Alternative flashing via USB
  - Allwinner devices often use `sunxi-fel` or PhoenixSuit for flashing
  - Check if holding a button during boot enters FEL mode
  - `lsusb` should show VID 1f3a (Allwinner) in FEL mode

### Medium Priority

- [ ] **Allwinner H723 BSP source code** — Check if Allwinner SDK is available
  - Often leaked on Chinese forums/GitHub
  - Lichee SDK for sun50iw15p1
  - **UPDATE**: radxa/allwinner-bsp IOMMU driver references sun50iw15 — BSP exists!
  - **UPDATE**: chainsx/u-boot-sun60i has KSC source code (GPL-2.0)
  - Needed for kernel source, device tree, display driver source
- [ ] **V-Silicon display driver documentation** — Required for any non-Android port
  - **This is now the ONLY critical blocker** — all other drivers have source
- [ ] **AIC8800 WiFi driver source** — ~~AiCsemi may provide GPL source~~ **FOUND**
  - fqrious/aic8800-dkms — DKMS package ready to install
  - LYU4662/aic8800-sdio-linux-1.0 — Tested on H618, kernel 6.7
  - 0x754C/aic8800-sdio-linux — SDIO variant
  - susers/aic8800_linux_drvier — kernel 6.17+ support
- [ ] **Verify A/B slot switching** — Can we safely flash slot B as test?
  - `bootctl` commands to switch active slot
  - Flash custom image to slot B, test, switch back to A if fails

### Long Term

- [ ] **ARM Mali GPU driver** — ~~Check Panfrost compatibility for this exact Mali variant~~ **CONFIRMED**: Panfrost works on H713 Mali T720 (same Mali Midgard family as our H723)
- [ ] **Cedar VPU driver** — Check if cedrus mainline supports H723's video decoder features
- [ ] **Upstream ToF/accel drivers** — Both have mainline IIO drivers; may enable Linux port for focus/keystone
- [ ] **Reverse engineer vs_display/vs_osd** — If V-Silicon won't provide docs, RE the .ko files — **THIS IS NOW THE #1 PRIORITY BLOCKER**
- [ ] **Community engagement** — Post findings to linux-sunxi.org wiki, XDA Developers
- [ ] **Collaborate with shift project** — Fork sun50iw12p1-research, adapt H713 DTS for H723
- [ ] **Collaborate with srgneisner** — Share security findings, align on privacy hardening
- [ ] **KSC keystone from source** — Build sunxi_ksc.ko from chainsx/u-boot-sun60i GPL source for any kernel version

---

## 6. Tools & Resources

### Required Tools

| Tool | Purpose | URL |
|------|---------|-----|
| AOSP Source | Android build system | source.android.com |
| sunxi-tools | Allwinner FEL mode tools | github.com/linux-sunxi/sunxi-tools |
| PhoenixSuit | Allwinner Windows flashing tool | (Allwinner SDK) |
| lpunpack | Unpack super.img | AOSP tools |
| mkbootimg | Create boot images | AOSP tools |
| simg2img | Sparse to raw image conversion | AOSP tools |
| Ghidra | Binary analysis of .ko modules | ghidra-sre.org |
| binwalk | Firmware analysis | github.com/ReFirmLabs/binwalk |

### Useful References

| Resource | Topic |
|----------|-------|
| linux-sunxi.org/H723 | H723 SoC wiki page |
| linux-sunxi.org/FEL | FEL boot mode documentation |
| linux-sunxi.org/Mainline_Kernel | Mainline kernel status |
| source.android.com/docs/core/architecture/partitions | A/B partition docs |
| android.googlesource.com | AOSP source trees |
| github.com/nicknisi/android-device-tree | Device tree examples |

---

## 7. Risk Assessment

| Activity | Risk Level | Mitigation |
|----------|-----------|------------|
| Flash custom boot.img to slot B | LOW | Can switch back to slot A |
| Flash custom system in super | MEDIUM | Keep backup of super.img |
| Modify bootloader | **HIGH** | Could brick — have FEL recovery ready |
| Enable SELinux Enforcing | LOW | Can revert in boot cmdline |
| Remove su/qw | LOW | Backed up in firmware dump |
| Remove malware packages | LOW | APKs already pulled/backed up |
| Full custom AOSP build | MEDIUM | Test in slot B first |

---

## 8. Estimated Effort

### Option A: Secure AOSP Build (Recommended)

| Task | Complexity | Dependencies |
|------|-----------|-------------|
| Set up AOSP build env | Medium | 300GB+ disk, Ubuntu |
| Create device tree | Hard | Allwinner BSP knowledge |
| Extract/integrate vendor blobs | Medium | Already have .ko files |
| Security hardening | Easy | Config changes |
| Build & flash | Medium | Fastboot/FEL access |
| Test all hardware features | Medium | Physical device access |
| **Total** | **Hard** | Kernel source ideal |

### Shortcut: Repackage Existing System

Instead of building from scratch, repackage the existing super partition:

1. `lpunpack super.img` → extract system, vendor, product images
2. Mount each, remove malware, fix security config
3. Repack with `lpmake`
4. Flash modified super.img

This is **faster** but keeps the vendor's base code (minus malware).

---

*Document created: March 1, 2026*
*Last updated: March 1, 2026*
