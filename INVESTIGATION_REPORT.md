# S40 Projector Security Investigation Report
**Date:** March 1, 2026  
**Device:** Orange Box S40 "4K FHD" Projector  
**IP:** 192.168.0.106  
**MAC:** 34:FC:F4:DD:82:16  

---

## EXECUTIVE SUMMARY

This device is a **security nightmare**. It ships with multiple layers of deception, pre-installed suspicious software, critically weak security configurations, and a Netflix manipulation toolkit built into the firmware. The device **masquerades as a Google Pixel 3** to bypass DRM/certification checks.

**Threat Level: HIGH**

---

## HARDWARE PROFILE

| Property | Value |
|---|---|
| **Real SoC** | Allwinner H723 (`sun50iw15p1`) |
| **CPU** | ARMv7 Cortex-A53 (4 cores @ ~60 BogoMIPS) |
| **RAM** | ~835 MB (advertised likely as 1GB) |
| **Storage** | eMMC (mmcblk0) |
| **Platform** | `hermes` / `exdroid` (Allwinner/Softwinner) |
| **GPU** | Mali (ARM) |
| **WiFi Chip** | AIC8800D80 (SDIO, Chinese chip) |
| **G-Sensor** | SC7A20E |
| **Display** | 1024x600 native (NOT 4K!) |
| **Kernel** | Linux 5.15.167 (armv7l, Sep 10 2025) |

### Key Hardware Deceptions:
- **"4K FHD" claim is FALSE** - native display is **1024x600** (`persist.vendor.disp.screensize`)
- The SoC is a budget Allwinner chip, NOT capable of true 4K processing

---

## SOFTWARE/OS PROFILE

| Property | Value |
|---|---|
| **Android Version** | 14 (SDK 34) |
| **Build Type** | `userdebug` (NOT production!) |
| **Build Keys** | `test-keys` (INSECURE - not signed with release keys) |
| **SELinux** | **PERMISSIVE** (security essentially disabled) |
| **ADB Secure** | `0` (NO authentication required) |
| **Build ID** | `h723_evb1-userdebug` (EVB = Evaluation Board!) |
| **Firmware Date** | September 12, 2025 |
| **Build Fingerprint** | `google/blueline/blueline:14` (FAKE - Pixel 3!) |
| **Security Patch** | 2024-06-05 |

### Critical Security Issues:
1. **FAKE DEVICE IDENTITY** - Spoofs Google Pixel 3 (`blueline`) to pass Google CTS/DRM checks
2. **SELinux PERMISSIVE** - All mandatory access controls are disabled
3. **test-keys** - Firmware signed with test keys, meaning anyone can sign system apps
4. **ADB wide open** - No authentication, anyone on the network can connect
5. **userdebug build** - Debug build shipped to consumers, exposes extra attack surface
6. **Root daemon on port 1234** - SuperUser daemon (`qw`) listening on all interfaces

---

## SUSPICIOUS NETWORK ACTIVITY

### Active Connections Found:
| Local | Remote | State | Owner |
|---|---|---|---|
| 0.0.0.0:1234 | * | LISTEN | root (uid=0) |
| *:5555 | * | LISTEN | shell (ADB) |
| 192.168.0.106:33936 | **116.202.8.16:443** | CLOSE_WAIT | system (uid=1000) |

### Analysis:
- **Port 1234** - Root-owned SuperUser daemon (`/system/bin/qw`), accessible to anyone on the network
- **116.202.8.16** - Hetzner Online GmbH server (German hosting, commonly used by Chinese services). Connection initiated by system-level process (likely `com.hx.update` OTA service)
- **Port 5555** - ADB over WiFi (open to all, no authentication)

---

## MALWARE / SUSPICIOUS APPS ANALYSIS

### 1. `com.android.nfx` - **Netflix Manipulation Malware** (CRITICAL)
- **Path:** `/data/app/` (sideloaded during manufacturing)
- **Installed by:** `com.android.shell` (ADB during factory setup)
- **Has AccessibilityService** (`NfxAccessibilityService`) - can control entire UI
- **Targets Netflix** - contains hardcoded Netflix UI element IDs for automation
- **System integration** - WindowManager has built-in `enableNfxAccessibility` toggle
- **Capabilities:** Gesture dispatch, screen reading, Netflix profile navigation
- **System properties:** `sys.nfx_bound`, `sys.nfx_bound_shown`, `sys.nfx_key_pass`
- **Purpose:** Automate Netflix interaction, likely for DRM bypass/account manipulation

### 2. `com.chihihx.store` - **Custom App Store** (HIGH RISK)
- **Runs as SYSTEM** (uid=1000)
- **Auto-starts on boot** (BootReceiver + ServiceTriggerProvider)
- **Uses `codeZeng.lib_autorun`** library for persistent background execution
- **Can install apps silently** as system user
- Potential backdoor for remote app installation

### 3. `com.hx.update` - **OTA Update Service** (HIGH RISK)
- **Runs as SYSTEM** (uid=1000)
- **Permissions:** INTERNET, INSTALL_PACKAGES, RECOVERY, QUERY_ALL_PACKAGES
- **Auto-starts on boot**
- **Connects to external servers** (116.202.8.16:443)
- Can silently download and install any APK with system privileges

### 4. `com.hx.appcleaner` - **App Cleaner** (SUSPICIOUS)
- **Runs as SYSTEM** (uid=1000)
- **Permissions far exceed stated purpose:** FORCE_STOP_PACKAGES, RECOVERY, ACCESS_CACHE_FILESYSTEM, WRITE_SETTINGS, BIND_ATTENTION_SERVICE
- **Auto-starts on boot**
- An "app cleaner" should NOT need recovery or cache filesystem access

### 5. `com.hx.apkbridge` - **APK Bridge** (SUSPICIOUS)
- **System privileged app**
- **Can request package installation** (REQUEST_INSTALL_PACKAGES)
- Acts as intermediary for sideloading apps

### 6. `com.android.vending` (Tubesky) - **Repackaged Play Store** (MODERATE)
- **APK directory named "Tubesky"** but uses `com.android.vending` package name
- Installed as system privileged app with INSTALL_PACKAGES, DELETE_PACKAGES permissions
- Signature appears to match genuine Google Play Store

### 7. `com.android.nfhelper` - **Netflix Helper** (SUSPICIOUS)
- **Runs as SYSTEM**
- Part of the Netflix manipulation toolkit
- Works alongside `com.android.nfx`

### 8. `com.hx.guardservice` (StressTestGuard) - **Factory Test Guard** (LOW)
- Factory testing remnant left in production firmware

### 9. `com.dd.bugreport` - **Bug Report** (SUSPICIOUS)
- Custom bug report app, likely phones home with device diagnostics

---

## ROOT-LEVEL SERVICES

| Process | PID | Purpose | Risk |
|---|---|---|---|
| `qw` | 308 | SuperUser daemon (port 1234) | **CRITICAL** |
| `tvserver` | 193 | Allwinner TV server | Medium |
| `systemmixservice` | 457 | System mix service | Medium |
| `gpioservice` | 448 | GPIO control | Low |
| `vohci` | 1125 | Virtual OHCI USB | Low |
| `wletd` | 1132 | Wireless LET daemon | Medium |

---

## DEVICE IDENTITY SPOOFING

The device systematically fakes its identity:

| Property | Fake Value | Real Value |
|---|---|---|
| `ro.product.model` | Pixel 3 | Projector |
| `ro.product.brand` | google | Unknown Chinese |
| `ro.product.manufacturer` | Google | Allwinner/Softwinner |
| `ro.product.device` | blueline | h723_evb1 |
| `ro.build.fingerprint` | google/blueline/blueline:14/... | Custom firmware |
| Display resolution | "4K FHD" (marketing) | 1024x600 |

**Why Pixel 3?** - The Pixel 3 (blueline) is a Widevine L1 certified device. By spoofing this identity, the projector can:
1. Pass Netflix device verification for HD/4K streaming
2. Pass Google CTS (Compatibility Test Suite)
3. Access DRM-protected content at higher quality levels
4. Use Google Play services that require device certification

---

## RECOMMENDATIONS

### Immediate Actions:
1. **Block outbound connections** from this device at your router (except streaming services you trust)
2. **Disable ADB** if not actively investigating: `adb shell settings put global adb_enabled 0`
3. **Block port 1234** at your firewall - the SuperUser daemon is accessible to anyone on your network
4. **Disable the NFX accessibility service** if it gets enabled

### Disable Suspicious Apps:
```bash
adb shell pm disable-user --user 0 com.android.nfx
adb shell pm disable-user --user 0 com.chihihx.store
adb shell pm disable-user --user 0 com.hx.apkbridge
adb shell pm disable-user --user 0 com.hx.appcleaner
adb shell pm disable-user --user 0 com.hx.update
adb shell pm disable-user --user 0 com.dd.bugreport
adb shell pm disable-user --user 0 com.hx.guardservice
```

### Network-Level Protection:
1. Put this device on an **isolated VLAN/guest network**
2. Only allow traffic to known streaming service IPs
3. Block all China-range IPs if possible
4. Monitor DNS queries from this device

### Long-term:
- Consider this device **compromised by design**
- Use only via your Mi Box 4K (which is a legitimate device)
- Do NOT enter any credentials directly on the projector's OS
- Do NOT connect USB drives with sensitive data to the projector

---

## FILES COLLECTED

| File | Description |
|---|---|
| `nfx.apk` | Netflix manipulation malware APK |
| `hx_update.apk` | OTA update service APK |
| `hx_appcleaner.apk` | Suspicious app cleaner APK |
| `nfhelper.apk` | Netflix helper APK |
| `bugreport.apk` | Bug report APK |
| `all_props.txt` | Complete system properties |
| `logcat_full.txt` | System logs |
| `build_prop.txt` | Build configuration |
