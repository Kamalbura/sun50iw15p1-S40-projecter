#!/usr/bin/env python3
"""Focused analysis of CHIHI_Launcher and critical projector APKs."""
import logging
logging.disable(logging.CRITICAL)  # Suppress all androguard debug output

from androguard.core.apk import APK
from androguard.core.dex import DEX
import zipfile

def analyze_manifest(apk_path):
    a = APK(apk_path)
    print(f"\n{'='*70}")
    print(f"  {apk_path}")
    print(f"{'='*70}")
    print(f"Package: {a.get_package()}")
    print(f"Version: {a.get_androidversion_name()} (code {a.get_androidversion_code()})")
    print(f"Main Activity: {a.get_main_activity()}")
    uid = a.get_attribute_value("manifest", "sharedUserId")
    if uid:
        print(f"Shared UID: {uid}")
    
    print(f"\nActivities ({len(a.get_activities())}):")
    for x in a.get_activities(): print(f"  {x}")
    print(f"\nServices ({len(a.get_services())}):")
    for x in a.get_services(): print(f"  {x}")
    print(f"\nReceivers ({len(a.get_receivers())}):")
    for x in a.get_receivers(): print(f"  {x}")
    print(f"\nProviders ({len(a.get_providers())}):")
    for x in a.get_providers(): print(f"  {x}")
    print(f"\nPermissions ({len(a.get_permissions())}):")
    for p in sorted(a.get_permissions()):
        print(f"  {p}")
    return a

def find_hw_strings(apk_path):
    """Find hardware-related strings in DEX files."""
    a = APK(apk_path)
    for i, dex_data in enumerate(a.get_all_dex()):
        d = DEX(dex_data)
        classes = list(d.get_classes())
        print(f"\nDEX {i}: {len(classes)} classes")
        
        # Find projector-related classes
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
            print(f"\nProjector-related classes ({len(hw_classes)}):")
            for c in sorted(hw_classes):
                print(f"  {c}")
        
        # Hardware strings
        strings = list(d.get_strings())
        hw_strings = set()
        for s in strings:
            sl = s.lower()
            if any(p in sl for p in [
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
            print(f"\nHardware strings ({len(hw_strings)}):")
            for s in sorted(hw_strings):
                print(f'  "{s}"')

# Analyze critical APKs
for apk in ['CHIHI_Launcher.apk', 'KeystoneCorrection.apk', 'VideoInputService.apk', 'AwManager.apk', 'SettingsAssist.apk']:
    try:
        analyze_manifest(apk)
        find_hw_strings(apk)
    except Exception as e:
        print(f"  ERROR: {e}")
