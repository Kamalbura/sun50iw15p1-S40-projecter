# Orange Box S40 Projector — Complete Hardware Architecture

## Device Identity

| Property | Value |
|---|---|
| Model | Orange Box S40 |
| SoC | Allwinner H723 (`sun50iw15p1`) |
| Android | 14 (API 34) |
| Build | `ro.build.characteristics = optics` |
| Platform | H723 (`persist.vendor.launcher.platform`) |
| Auto Keystone Model | S40 (`persist.vendor.auto_keystone.model`) |
| Native Resolution | 1024x600 (`persist.vendor.disp.screensize`) |
| Gsensor | sc7a20e (`persist.vendor.gsensor.model`) |
| Audio Output | OUT_SPK (internal speaker) |
| CEC Address | 36 (`persist.vendor.cec_address`) |

---

## HIDL / Vendor Services (lshal)

| Service | Interface | PID | Status |
|---|---|---|---|
| TV Server | `vendor.aw.homlet.tvsystem.tvserver@1.0::ITvServer/default` | 195 | Active |
| Display Config | `vendor.display.config@1.0::IDisplayConfig/default` | 279 | Active |
| TV Graphics | `vendor.sunxi.tv.graphics@1.0::IDisplay/default` | 195 | Active |

## Android System Services

| Service Name | Interface | Purpose |
|---|---|---|
| `display` | `IDisplayManager` | Android display management |
| `color_display` | `IColorDisplayManager` | Color/night light |
| `tv_input` | `ITvInputManager` | TV input source management (HDMI/CVBS) |
| `input` | `IInputManager` | IR remote / touch input |
| `media_projection` | `IMediaProjectionManager` | Screen mirroring |

---

## 1. Keystone Correction Architecture

### Control Chain (App → Hardware)

```
User Input (IR Remote / Touch)
    │
    ▼
┌─────────────────────────────────┐
│  UI Layer                       │
│  CircleView / ScaleCircleView   │
│  (corner drag interface)        │
│  ManuelCorrectionActivity       │
│  AngleActivity (V/H adjustment) │
└───────────────┬─────────────────┘
                │
                ▼
┌─────────────────────────────────┐
│  Logic Layer                    │
│  SetTrapezoid                   │
│  - getKeyStoneParame(int idx)   │
│  - setKeyStoneParame(int,int)   │
│  - resetKeyStone()              │
│  - writeParcelToFlinger(int[])  │
└───────────────┬─────────────────┘
                │
        ┌───────┴───────┐
        ▼               ▼
┌───────────────┐ ┌──────────────────────────────┐
│ SurfaceFlinger│ │ AwTvDisplayManager            │
│ Binder Path   │ │ .setKeystoreValue(            │
│ (alternate)   │ │   F zoom_h, F zoom_v,         │
│               │ │   I ltx,lty, I rtx,rty,       │
│ Parcel with   │ │   I lbx,lby, I rbx,rby)       │
│ ISurfaceComp- │ └──────────┬───────────────────┘
│ oser token    │            │
│ + 8 floats    │            ▼
│ → transact()  │  ┌─────────────────────────────┐
└───────────────┘  │ IDisplayConfig HIDL Service   │
                   │ vendor.display.config@1.0     │
                   │                               │
                   │ .keystoneSetCoordinates(       │
                   │   F zoom_h, F zoom_v,          │
                   │   KscPoint lt, KscPoint rt,    │
                   │   KscPoint lb, KscPoint rb)    │
                   │                               │
                   │ .keystoneFlip(bool h, bool v)  │
                   └──────────┬────────────────────┘
                              │
                              ▼
                   ┌──────────────────────┐
                   │ Allwinner Display     │
                   │ Engine (DE2)          │
                   │ Hardware Transform    │
                   └──────────────────────┘
```

### KscPoint Structure (vendor.display.config@1.0)
```java
class KscPoint {
    int x;  // pixel offset from corner
    int y;  // pixel offset from corner
}
```

### System Properties — Keystone

| Property | Type | Current Value | Description |
|---|---|---|---|
| `persist.display.keystone_ltx` | int | 66 | Left-top X offset |
| `persist.display.keystone_lty` | int | 77 | Left-top Y offset |
| `persist.display.keystone_rtx` | int | 66 | Right-top X offset |
| `persist.display.keystone_rty` | int | 77 | Right-top Y offset |
| `persist.display.keystone_lbx` | int | 0 | Left-bottom X offset |
| `persist.display.keystone_lby` | int | 0 | Left-bottom Y offset |
| `persist.display.keystone_rbx` | int | 0 | Right-bottom X offset |
| `persist.display.keystone_rby` | int | 0 | Right-bottom Y offset |
| `persist.display.keystone_zoom_h` | float | 100.0 | Horizontal zoom % |
| `persist.display.keystone_zoom_v` | float | 100.0 | Vertical zoom % |
| `persist.sys.filp.mode` | int | 0 | Flip/mirror mode (0=normal) |

**Secondary property sets** (used by SetTrapezoid for angle-based control):
| Property | Type | Description |
|---|---|---|
| `persist.keystone.vertical.degree` | int | Vertical angle correction |
| `persist.keystone.horizontal.degree` | int | Horizontal angle correction |
| `persist.keystone.rotation.degree` | int | Rotation correction |
| `persist.keystone.zoom.percent` | int | Zoom percentage |
| `persist.cus.keystone.{ltx,lty,rtx,rty,lbx,lby,rbx,rby}` | int | Custom corner offsets |

### Mirror/Flip Control
```
factorySetPanelValue(E_AW_PANEL_CONFIG_MIRROR, value)
    → checks ro.build.characteristics == "optics"
    → IDisplayConfig.keystoneFlip(horizontal_bool, vertical_bool)
```
Mirror modes (4 combinations): Normal, H-flip, V-flip, H+V flip.

---

## 2. Auto Keystone (Gsensor-Based)

### Gsensor: sc7a20e Accelerometer

| Property | Description |
|---|---|
| `persist.vendor.gsensor.enable` | boolean, enables auto-keystone |
| `persist.vendor.gsensor.model` | "sc7a20e" — accelerometer IC |
| `persist.vendor.gsensor.delay` | 600ms polling delay |
| `persist.vendor.gsensor.calcAverage` | Use averaging filter |
| `persist.vendor.gsensor.moving_dly` | Movement delay threshold |
| `persist.vendor.gsensor.upper` | Upper/lower mounting orientation |
| `persist.vendor.gsensor.debug` | Debug logging |

Previously (stk8ba58 accelerometer variant):
| Property | Description |
|---|---|
| `persist.vendor.gsensor.acc_x/y/z` | Raw accelerometer values |
| `persist.vendor.gsensor.gyr_x/y/z` | Raw gyroscope values |
| `persist.vendor.gsensor.acc_x/y/z_offset` | Calibration offsets |
| `persist.vendor.gsensor.gyr_x/y/z_offset` | Calibration offsets |

**sysfs**: `/sys/class/stk8ba58/` (if stk8ba58 variant; sc7a20e may use different path)

### Auto Keystone Flow
```
Gsensor daemon reads accelerometer
    → Writes persist.vendor.gsensor.acc_x/y/z
    → CheckGsensorActivity reads values
    → Applies offset calibration
    → Computes keystone correction angles
    → SetTrapezoid.setKeyStoneParame()
    → writeParcelToFlinger()
    → AwTvDisplayManager.setKeystoreValue()
    → IDisplayConfig.keystoneSetCoordinates()
```

---

## 3. Motor Control (Auto-Focus)

### Sysfs Interface
```
/sys/devices/platform/motor/motor_ctrl
```

**Usage**:
```bash
# Clockwise rotation
echo "1" > /sys/devices/platform/motor/motor_ctrl

# Counter-clockwise rotation
echo "2" > /sys/devices/platform/motor/motor_ctrl

# With step count
echo "1,100" > /sys/devices/platform/motor/motor_ctrl    # CW, 100 steps
echo "2,50"  > /sys/devices/platform/motor/motor_ctrl    # CCW, 50 steps
```

### Motor Limiter
```
/sys/devices/platform/motor_limiter/motor_limiter → "1" (at limit)
/sys/devices/platform/motor_limiter/motor-limiter  (driver control)
```

### Related Properties
| Property | Description |
|---|---|
| `persist.vendor.auto_focus.hysd` | Auto-focus hysteresis/distance parameter |

---

## 4. Projection Mode

### Sysfs
```
/sys/class/projection/mode  → "0" (current mode)
/sys/class/projection/model → "2" (model identifier)
```

### Related Properties
| Property | Description |
|---|---|
| `persist.sys.projection` | Projection mode setting |

---

## 5. Video Input Source Switching

### Architecture
```
CHIHI_Launcher
    │ (startActivity)
    ▼
┌─────────────────────────────────┐
│ VideoInputService               │
│ (com.softwinner.vis)            │
│                                 │
│ ├─ HdmiInputService            │
│ │  └─ SessionImpl              │
│ │     ├─ HdmiSignalReceiver    │
│ │     │  (broadcast: signal_id,│
│ │     │   device_id, dvi_mode) │
│ │     └─ HardwareCallback      │
│ │        (stream config change)│
│ │                              │
│ └─ CvbsInputService           │
│    └─ SessionImpl              │
│       ├─ CvbsSignalReceiver   │
│       └─ HardwareCallback     │
└───────────────┬─────────────────┘
                │ uses
                ▼
┌─────────────────────────────────┐
│ Android TvInputManager          │
│ (service: tv_input)             │
│                                 │
│ TvInputManager.HardwareCallback │
│ TvStreamConfig                  │
└───────────────┬─────────────────┘
                │ depends on
                ▼
┌─────────────────────────────────┐
│ ITvServer HIDL                  │
│ vendor.aw.homlet.tvsystem.     │
│ tvserver@1.0                    │
│                                 │
│ SubDeviceSetSource(int sourceId)│
│ SubDeviceGetSource() → int      │
│ SubDeviceSetSourceAsync(int)    │
│ SubDeviceGetSourceSignalInfo()  │
│  → THalSignalInfo              │
└─────────────────────────────────┘
```

### Source IDs (from VideoInputService strings)
| Source | ID Enum |
|---|---|
| HDMI1 | `TV_INPUT_SOURCE_HDMI1` |
| HDMI2 | `TV_INPUT_SOURCE_HDMI2` |
| HDMI3 | `TV_INPUT_SOURCE_HDMI3` |
| CVBS1 | `TV_INPUT_SOURCE_CVBS1` |
| CVBS2 | `TV_INPUT_SOURCE_CVBS2` |
| ATV | `TV_INPUT_SOURCE_ATV` |
| DTV | `TV_INPUT_SOURCE_DTV` |
| NULL | `TV_INPUT_SOURCE_NULL` |

### Signal Broadcast Extras
| Extra | Type | Description |
|---|---|---|
| `signal_id` | int | Signal state (maps to OverScanTiming enum) |
| `device_id` | int | Hardware device identifier |
| `dvi_mode` | int | 1=DVI mode, 0=HDMI mode |

### AwOverlayView
VideoInputService uses `AwOverlayView` to show:
- No signal / unknown signal messages
- Resolution/timing info overlay
- DVI vs HDMI mode indicator

---

## 6. Picture Quality (PQ) Control

### AwTvDisplayManager API
All methods go through `runIntCmd()` → ITvServer HIDL calls:

| Method | Parameters | Description |
|---|---|---|
| `setBasicControl(type, value)` | EnumPQBasicType, int | Set brightness/contrast/saturation/hue/sharpness |
| `getBasicControl(type)` | EnumPQBasicType | Get current value |
| `setBacklight(value)` | int | Set backlight level |
| `getBacklight()` | → int | Get backlight level |
| `setColorTemp(mode)` | EnumColorTempMode | Set color temperature |
| `setPictureModeByName(mode)` | EnumPictureMode | Set picture preset |
| `getPictureModeName()` | → String | Get current picture mode |
| `setDynamicBacklight(enabled)` | boolean | Enable/disable dynamic BL |
| `getDynamicBacklight()` | → int | Get dynamic BL state |
| `setSNR(value)` | int | Spatial noise reduction |
| `getSNR()` | → int | Get SNR level |
| `setTNR(value)` | int | Temporal noise reduction |
| `getTNR()` | → int | Get TNR level |
| `setDLC(value)` | int | Dynamic luminance control |
| `getDLC()` | → int | Get DLC level |
| `setBlackExtension(value)` | int | Black level extension |
| `getBlackExtension()` | → int | Get black extension |
| `setGammaFactor(value)` | int | Gamma correction factor |
| `getGammaFactor()` | → int | Get gamma factor |
| `setHDMIVideoPCMode(mode)` | EnumVideoPCMode | HDMI PC mode |
| `setSourceAspectRatio(mode)` | EnumOverScanScreenMode | Aspect ratio |
| `getSourceAspectRatio()` | → EnumOverScanScreenMode | Get aspect ratio |
| `setOverScanState(enabled)` | boolean | Enable overscan |
| `setStorePictureMode(store)` | boolean | Persist picture mode |
| `getPannelWidth()` | → int | Panel physical width |
| `getPannelHeight()` | → int | Panel physical height |
| `getVideoRange()` | → int | Video range (limited/full) |
| `resetAllPictureSettings()` | void | Factory reset PQ |

### PQ Basic Types (EnumPQBasicType)
- `E_AW_PQ_BASIC_TYPE_BRIGHTNESS`
- `E_AW_PQ_BASIC_TYPE_CONTRAST`
- `E_AW_PQ_BASIC_TYPE_SATURATION`
- `E_AW_PQ_BASIC_TYPE_HUE`
- `E_AW_PQ_BASIC_TYPE_SHARPNESS`

### Factory Methods
| Method | Description |
|---|---|
| `factorySetBasicControl(idx, name, type, value)` | Factory PQ set |
| `factorySetBacklight(idx, name, value)` | Factory backlight |
| `factorySetPWMFrequency(value)` | PWM frequency control |
| `factorySetPanelValue(type, value)` | Panel config (mirror/flip) |
| `factorySetOverScan(src, idx, mode, type, value)` | Overscan per-source |
| `factoryGetPanelValue(type)` | Read panel config |
| `factoryGetPWMFrequency()` | Read PWM freq |
| `factorySetColorTemperature(idx, name, value)` | Color temp per-mode |
| `factorySetSNR/TNR(idx, name, value)` | Per-source NR |
| `factorySetDynamicBacklight(idx, name, enabled)` | Per-source dynamic BL |
| `factorySetGammaFactor(idx, name, value)` | Per-source gamma |
| `factorySetWbGainOffsetNotSave(src, ct, type, value)` | White balance |
| `factoryCopyWbGainOffsetToOtherSrcNotSave(src)` | Copy WB across sources |
| `factoryResetWbGainOffset()` | Reset white balance |
| `factorySetPictureParam/Level(type, idx, value)` | Picture parameters |
| `factoryAdvanceSetColorManager(src, item, idx, value)` | Color management |
| `factoryCvbsSetPedestalMode(enabled)` | CVBS pedestal |
| `factoryCvbsGetPedestalMode()` | Get CVBS pedestal |
| `factoryResetPanelSettings()` | Reset panel to defaults |

---

## 7. ITvServer HIDL — Full Method Inventory

Interface: `vendor.aw.homlet.tvsystem.tvserver@1.0::ITvServer`

### Source Control
- `SubDeviceSetSource(int) → int`
- `SubDeviceGetSource() → int`
- `SubDeviceSetSourceAsync(int) → int`
- `SubDeviceGetSourceSignalInfo(int) → THalSignalInfo`

### HDMI
- `SubDeviceHDMIGetStatus(int) → int`
- `SubDeviceHDMICheckPlugIn(int) → int`
- `SubDeviceHDMIGetPlugInFlag(int) → int`
- `SubDeviceHDMISetAudioOutMode(int,int) → int`
- `SubDeviceHDMISetEdidData(int, vec<int8_t>) → int`
- `SubDeviceHDMIGetEdidData(int, int) → vec<int8_t>`

### CEC
- `SubDeviceCECSendMsg(tag_cec_message) → int`
- `SubDeviceCECSetLogicalAddr(int) → int`
- `SubDeviceCECGetPhysicalAddr() → int`
- `SubDeviceCECEnable(int) → int`
- `SubDeviceCECDisable(int) → int`

### Picture Quality
- `setPQValue(int,int) → int`
- `getPQValue(int) → int`
- `setGammaRGBValue(int,int,int) → int`

### Factory
- `factorySet*(...)` — 20+ factory calibration methods
- `factoryGet*(...)` — matching getter methods

### Environment
- `getEnv(string) → string`
- `setEnv(string, string) → int`
- `saveEnv() → int`

### Data Types
- `THalSignalInfo { int sigFormat; int sigStatus; }`
- `THalResolution { int width; int height; }`
- `ScreenWin { int x; int y; int w; int h; }`
- `tag_cec_message { int8_t dest; int8_t opcode; vec<int8_t> operand; }`
- `McuCommParam_t { vec<int8_t> data; }`
- `AudioSettingParams { ... }`

### Callbacks
- `ITvCallback { hotplug_callback(int,int); signal_callback(int,int); }`
- `IPQCallback { picture_mode_callback(int,int); }`
- `ICecmsgCallback { cecmsg_callback(tag_cec_message); }`

---

## 8. TV Graphics Service

Interface: `vendor.sunxi.tv.graphics@1.0::IDisplay/default`

Purpose: Low-level display engine control (framebuffer/overlay management). Shares PID 195 with ITvServer.

---

## 9. Thermal Management

| Zone | Type | Current Temp |
|---|---|---|
| zone0 | `cpu_thermal_zone` | 73.8°C |
| zone1 | `gpu_thermal_zone` | 72.6°C |
| zone2 | `cpu_idle_zone` | N/A |
| zone3 | `board_thermal_zone` | N/A |

Cooling devices: `cooling_device0`, `cooling_device1`

---

## 10. Board Management System (awbms)

The `awbms.jar` runs as a service (`ServiceManager.addService("background")`):
- Monitors audio playback state via `IAudioService.registerPlaybackCallback()`
- Manages background music behavior (mute/unmute when apps play audio)
- Config-driven via `AwbmsConfig`

---

## 11. Installed APK Architecture

### Critical System Apps (SharedUID: android.uid.system)

| APK | Package | Version | Role |
|---|---|---|---|
| CHIHI_Launcher | `com.chihihx.launcher` | 1.0.5 | Main launcher (MALWARE-INFESTED, needs replacement) |
| KeystoneCorrection | `com.softwinner.tcorrection` | 14 | Keystone UI + hardware control |
| VideoInputService | `com.softwinner.vis` | 1.3 | HDMI/CVBS input service |
| AwManager | `com.softwinner.awmanager` | - | App launcher selector |
| SettingsAssist | `com.softwinner.settingsassist` | 14 | OTA + Recovery |

### Framework JARs (bootclasspath / systemserver)

| JAR | Package | Role |
|---|---|---|
| `com.softwinner.tv.jar` | AwTvDisplayManager, ITvServer | TV/display/PQ control API |
| `awbms.jar` | BackgroundManagerService | Background audio management |
| `softwinner.audio.jar` | AudioSettingParams | Audio framework extensions |

---

## 12. CHIHI_Launcher Projector Integration

### How the launcher controls projector features:

```
MainActivity
    ├── ProjectorFragment (projector settings list)
    │   └── clickItem(item) → ViewModel dispatches to:
    │       ├── KeystoneCorrection activities via Intent:
    │       │   • com.softwinner.tcorrection/.projection.ProjectionSettingActivity
    │       │   • com.softwinner.tcorrection/.projection.AngleActivity
    │       │   • com.softwinner.tcorrection/.MainActivity (4-point correction)
    │       ├── ScaleScreenActivity (zoom/fit control)
    │       └── FocusFragment (auto-focus motor guide)
    │
    ├── SettingFragment (general settings list)
    │   └── clickItem(item type) dispatches to:
    │       ├── SettingActivity (display settings)
    │       ├── com.android.tv.settings/.device.display.DisplayActivity
    │       ├── Config helper calls (oe2 class):
    │       │   • .g() - toggle auto keystone
    │       │   • .p() - picture mode cycle
    │       │   • .E(ctx) - language settings
    │       │   • .q(ctx) - WiFi settings
    │       │   • .z() - Bluetooth settings
    │       │   • .w() - sound settings
    │       │   • .A() - about/info
    │       └── Factory test (y5.A(ctx))
    │
    └── FocusFragment (initial setup guide)
        └── Shows focus tip text
        └── "Next" → GuideLanguageFragment
```

The launcher itself does NOT directly control hardware. It launches `KeystoneCorrection` activities and uses a config helper class (obfuscated as `oe2`, `re2`, `Loe2`) to manage projector-related settings.

### Key observation for replacement launcher:
A replacement launcher only needs to:
1. Launch `com.softwinner.tcorrection` activities for keystone control
2. Use Android Settings intents for WiFi/BT/display
3. Optionally read SystemProperties for status display
4. Does NOT need `android.uid.system` SharedUID just for launching!

---

## 13. Requirements for Clean Replacement OS

### Must Keep (vendor-specific, cannot be replaced)
- `com.softwinner.tcorrection` (KeystoneCorrection.apk) — hardware keystone control
- `com.softwinner.vis` (VideoInputService.apk) — HDMI/CVBS input
- `com.softwinner.tv.jar` — TV framework (AwTvDisplayManager, ITvServer)
- `awbms.jar` — background audio management
- `softwinner.audio.jar` — audio extensions
- HIDL services: IDisplayConfig, ITvServer, IDisplay (in vendor partition)
- Gsensor daemon (auto-keystone, reads sc7a20e accelerometer)
- Motor driver (`/sys/devices/platform/motor/motor_ctrl`)

### Can Replace
- **CHIHI_Launcher** → Any Android TV launcher
- **AwManager** → Not needed (simple app launcher)
- **SettingsAssist** → Can use stock Android TV settings
- All malware components → ALREADY REMOVED ✅

### Launcher Replacement Options
1. **FLauncher** — Open source, customizable, no system UID needed
2. **Projectivy Launcher** — Designed for projectors, has focus/keystone shortcuts
3. **ATV Launcher** — Full-featured Android TV launcher
4. **Wolf Launcher** — Highly customizable
5. **Custom launcher** — Can integrate projector controls via Intent:
   ```kotlin
   // Launch keystone correction
   startActivity(Intent().setComponent(
       ComponentName("com.softwinner.tcorrection",
           "com.softwinner.tcorrection.projection.ProjectionSettingActivity")))
   
   // Launch 4-point keystone
   startActivity(Intent().setComponent(
       ComponentName("com.softwinner.tcorrection",
           "com.softwinner.tcorrection.MainActivity")))
   
   // Read current keystone values
   val ltx = SystemProperties.getInt("persist.display.keystone_ltx", 0)
   
   // Control motor (requires shell/root)
   Runtime.getRuntime().exec("echo 1,100 > /sys/devices/platform/motor/motor_ctrl")
   ```

---

## 14. All System Properties Reference

### Keystone (Display)
```
persist.display.keystone_ltx = 66
persist.display.keystone_lty = 77
persist.display.keystone_rtx = 66
persist.display.keystone_rty = 77
persist.display.keystone_lbx = 0
persist.display.keystone_lby = 0
persist.display.keystone_rbx = 0
persist.display.keystone_rby = 0
persist.display.keystone_zoom_h = 100.0
persist.display.keystone_zoom_v = 100.0
```

### Keystone (Angle-based / Custom)
```
persist.keystone.vertical.degree
persist.keystone.horizontal.degree
persist.keystone.rotation.degree
persist.keystone.zoom.percent
persist.cus.keystone.{ltx,lty,rtx,rty,lbx,lby,rbx,rby}
persist.sys.keystone.{lt,lb,rt,rb,mirror,update,zoom}
```

### Projection/Display
```
persist.sys.projection
persist.sys.filp.mode = 0
persist.vendor.disp.screensize = 1024x600
ro.build.characteristics = optics
```

### Gsensor
```
persist.vendor.gsensor.enable = 1
persist.vendor.gsensor.model = sc7a20e
persist.vendor.gsensor.delay = 600
persist.vendor.gsensor.calcAverage = false
persist.vendor.gsensor.moving_dly = 1
persist.vendor.gsensor.upper = false
persist.vendor.gsensor.debug = false
```

### Vendor
```
persist.vendor.auto_keystone.model = S40
persist.vendor.launcher.platform = H723
persist.vendor.audio.output.active = OUT_SPK
persist.vendor.cec_address = 36
persist.vendor.arc_port = 0
persist.vendor.bluetooth_port = /dev/ttyAS1
persist.vendor.singlevolume = 0
persist.vendor.hpd_interval_ms = 200
persist.vendor.adc_pwr_off_poll = 1
persist.vendor.dtv.area = cn
persist.vendor.dtv.standard = dtmb
```

### Auto-Focus
```
persist.vendor.auto_focus.hysd
```

---

## 15. Sysfs Hardware Nodes

| Path | Type | Description |
|---|---|---|
| `/sys/class/projection/mode` | R/W | Projection mode (0=normal) |
| `/sys/class/projection/model` | R | Model identifier (2) |
| `/sys/devices/platform/motor/motor_ctrl` | W | Motor control (dir[,steps]) |
| `/sys/devices/platform/motor_limiter/motor_limiter` | R | Limit switch state (1=at limit) |
| `/sys/class/thermal/thermal_zone0/temp` | R | CPU temperature (milli-°C) |
| `/sys/class/thermal/thermal_zone1/temp` | R | GPU temperature (milli-°C) |
| `/sys/class/pwm/pwmchip0/` | R/W | PWM channel 0 |
| `/sys/class/pwm/pwmchip10/` | R/W | PWM channel 10 |
| `/sys/class/graphics/fb0` | - | Framebuffer 0 |
| `/sys/class/stk8ba58/` | R/W | Accelerometer (stk8ba58 variant) |
