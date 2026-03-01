#!/usr/bin/env python3
"""Focused analysis of CHIHI_Launcher and critical projector APKs."""
import sys, os

# Suppress androguard's loguru debug output  
os.environ['LOGURU_LEVEL'] = 'ERROR'
import loguru
loguru.logger.remove()
loguru.logger.add(sys.stderr, level="ERROR")

from androguard.core.apk import APK
from androguard.core.dex import DEX

out = open('analysis_output.txt', 'w', encoding='utf-8')

def p(s=''):
    print(s, file=out, flush=True)

def analyze_manifest(apk_path):
    a = APK(apk_path)
    p(f"\n{'='*70}")
    p(f"  {apk_path}")
    p(f"{'='*70}")
    p(f"Package: {a.get_package()}")
    p(f"Version: {a.get_androidversion_name()} (code {a.get_androidversion_code()})")
    p(f"Main Activity: {a.get_main_activity()}")
    uid = a.get_attribute_value("manifest", "sharedUserId")
    if uid:
        p(f"Shared UID: {uid}")
    
    p(f"\nActivities ({len(a.get_activities())}):")
    for x in a.get_activities(): p(f"  {x}")
    p(f"\nServices ({len(a.get_services())}):")
    for x in a.get_services(): p(f"  {x}")
    p(f"\nReceivers ({len(a.get_receivers())}):")
    for x in a.get_receivers(): p(f"  {x}")
    p(f"\nProviders ({len(a.get_providers())}):")
    for x in a.get_providers(): p(f"  {x}")
    p(f"\nPermissions ({len(a.get_permissions())}):")
    for pr in sorted(a.get_permissions()):
        p(f"  {pr}")
    return a

def find_hw_strings(apk_path):
    a = APK(apk_path)
    for i, dex_data in enumerate(a.get_all_dex()):
        d = DEX(dex_data)
        classes = list(d.get_classes())
        p(f"\nDEX {i}: {len(classes)} classes")
        
        hw_classes = []
        for cls in classes:
            name = cls.get_name()
            nl = name.lower()
            if any(k in nl for k in [
                'keystone', 'projection', 'motor', 'focus', 'backlight',
                'fan', 'hdmi', 'cec', 'display', 'ksc', 'tvserver',
                'videoinput', 'dispconfig', 'panel', 'sensor', 'brightness',
                'softwinner', 'projector', 'systemcontrol', 'inputsource',
                'launcher', 'hxmanager', 'awmanager', 'screensaver',
                'hxext', 'pddev', 'remote', 'irkey', 'hxsetting',
                'tvcontrol', 'displaymanager'
            ]):
                hw_classes.append(name)
        
        if hw_classes:
            p(f"\nProjector-related classes ({len(hw_classes)}):")
            for c in sorted(hw_classes):
                p(f"  {c}")
                # Show methods for projector-related classes
                for cls in d.get_classes():
                    if cls.get_name() == c:
                        for m in cls.get_methods():
                            mname = m.get_name()
                            if mname not in ('<init>', '<clinit>'):
                                p(f"    .{mname}()")
                        break
        
        strings = list(d.get_strings())
        hw_strings = set()
        for s in strings:
            sl = s.lower()
            if any(pt in sl for pt in [
                '/sys/class/projection', '/sys/devices/platform/motor',
                '/dev/hxext', '/dev/pddev', 'bl_power', 'bl_pwm',
                'fan_pwm', 'motor_ctrl', 'motor_trip', 'ksc',
                'dispconfig', 'tvserver', 'vendor.sunxi', 'vendor.aw',
                'ro.hx.', 'persist.hx.', 'auto_keystone', 'auto_focus',
                'input_source', 'hdmi_in', 'projection/mode',
                'adc_value', 'adc_ctl', '/sys/', '/dev/',
                'sysfs', 'ioctl', 'projector', 'keystone',
                'screen_scale', 'backlight'
            ]):
                hw_strings.add(s)
        
        if hw_strings:
            p(f"\nHardware strings ({len(hw_strings)}):")
            for s in sorted(hw_strings):
                p(f'  "{s}"')

for apk in ['CHIHI_Launcher.apk', 'KeystoneCorrection.apk', 'VideoInputService.apk', 'AwManager.apk', 'SettingsAssist.apk']:
    try:
        analyze_manifest(apk)
        find_hw_strings(apk)
    except Exception as e:
        p(f"  ERROR: {e}")

out.close()
print("Done! Output in analysis_output.txt")
