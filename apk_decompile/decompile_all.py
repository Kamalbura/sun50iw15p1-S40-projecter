#!/usr/bin/env python3
"""Decompile projector APKs and extract control architecture."""

import os
import sys
import zipfile
from pathlib import Path

# Use androguard for APK analysis
from androguard.core.apk import APK
from androguard.core.dex import DEX

APK_DIR = Path(__file__).parent

def analyze_apk(apk_path):
    """Analyze APK: manifest, permissions, activities, services, receivers, and key code patterns."""
    print(f"\n{'='*80}")
    print(f"  ANALYZING: {apk_path.name}")
    print(f"{'='*80}")
    
    try:
        a = APK(str(apk_path))
    except Exception as e:
        print(f"  ERROR: {e}")
        return
    
    print(f"\n  Package:     {a.get_package()}")
    print(f"  Version:     {a.get_androidversion_name()} (code: {a.get_androidversion_code()})")
    print(f"  Min SDK:     {a.get_min_sdk_version()}")
    print(f"  Target SDK:  {a.get_target_sdk_version()}")
    print(f"  Main Activity: {a.get_main_activity()}")
    
    # Shared UID
    shared_uid = a.get_attribute_value("manifest", "sharedUserId")
    if shared_uid:
        print(f"  Shared UID:  {shared_uid}")
    
    # Permissions
    perms = a.get_permissions()
    if perms:
        print(f"\n  Permissions ({len(perms)}):")
        for p in sorted(perms):
            short = p.split('.')[-1] if '.' in p else p
            print(f"    - {short}")
    
    # Activities
    activities = a.get_activities()
    if activities:
        print(f"\n  Activities ({len(activities)}):")
        for act in activities:
            short = act.replace(a.get_package(), '~')
            print(f"    - {short}")
    
    # Services
    services = a.get_services()
    if services:
        print(f"\n  Services ({len(services)}):")
        for svc in services:
            short = svc.replace(a.get_package(), '~')
            print(f"    - {short}")
    
    # Receivers
    receivers = a.get_receivers()
    if receivers:
        print(f"\n  Receivers ({len(receivers)}):")
        for rcv in receivers:
            short = rcv.replace(a.get_package(), '~')
            print(f"    - {short}")
    
    # Content Providers
    providers = a.get_providers()
    if providers:
        print(f"\n  Content Providers ({len(providers)}):")
        for prov in providers:
            short = prov.replace(a.get_package(), '~')
            print(f"    - {short}")
    
    # Intent Filters (what triggers this app)
    print(f"\n  Intent Filters:")
    # Get raw manifest XML for intent analysis
    try:
        manifest_xml = a.get_android_manifest_axml().get_xml()
        if isinstance(manifest_xml, bytes):
            manifest_xml = manifest_xml.decode('utf-8', errors='replace')
        
        # Search for key hardware-related strings
        hw_keywords = [
            'keystone', 'projection', 'motor', 'focus', 'backlight', 'brightness',
            'fan', 'hdmi', 'cec', 'display', 'ksc', 'tvserver', 'tvinput',
            'video_input', 'dispconfig', 'vs_osd', 'panel', 'accelerometer',
            'sensor', 'bl_power', 'pwm', 'sysfs', '/sys/', '/dev/',
            'softwinner', 'allwinner', 'sunxi', 'hxext', 'pddev',
            'INPUT_SOURCE', 'HDMI', 'projection_mode', 'auto_keystone',
            'boot_completed', 'SCREEN_ON', 'SCREEN_OFF'
        ]
        
        found_keys = []
        for kw in hw_keywords:
            if kw.lower() in manifest_xml.lower():
                found_keys.append(kw)
        
        if found_keys:
            print(f"  Hardware-related manifest strings: {', '.join(found_keys)}")
    except Exception:
        pass
    
    # Now analyze DEX code for hardware control patterns
    print(f"\n  Code Analysis (DEX):")
    try:
        dex_files = a.get_all_dex()
        for i, dex_data in enumerate(dex_files):
            d = DEX(dex_data)
            classes = list(d.get_classes())
            print(f"    DEX {i}: {len(classes)} classes")
            
            # Find projector-specific classes
            hw_classes = []
            for cls in classes:
                name = cls.get_name()
                name_lower = name.lower()
                if any(kw in name_lower for kw in [
                    'keystone', 'projection', 'motor', 'focus', 'backlight',
                    'fan', 'hdmi', 'cec', 'display', 'ksc', 'tvserver',
                    'video_input', 'videoinput', 'dispconfig', 'panel',
                    'sensor', 'accelerometer', 'brightness', 'hxext',
                    'softwinner', 'tvinput', 'tvcontrol', 'projector',
                    'systemcontrol', 'displaymanager', 'inputsource',
                    'screensaver', 'launcher', 'hxmanager', 'awmanager'
                ]):
                    hw_classes.append(name)
            
            if hw_classes:
                print(f"    Hardware-related classes ({len(hw_classes)}):")
                for cls_name in sorted(hw_classes)[:50]:  # Limit to 50
                    print(f"      {cls_name}")
            
            # Search for sysfs/device paths in strings
            strings = list(d.get_strings())
            hw_strings = []
            for s in strings:
                s_lower = s.lower()
                if any(pattern in s_lower for pattern in [
                    '/sys/class/projection',
                    '/sys/devices/platform/motor',
                    '/dev/hxext', '/dev/pddev', '/dev/video',
                    'bl_power', 'bl_pwm', 'fan_pwm',
                    'ksc', 'keystone',
                    'motor_ctrl', 'motor_trip',
                    'dispconfig', 'tvserver',
                    'sysfs', 'ioctl',
                    'vendor.sunxi', 'vendor.aw',
                    'ro.hx.', 'persist.hx.',
                    'auto_keystone', 'auto_focus',
                    'input_source', 'hdmi_in',
                    'projection/mode', 'projection/model',
                    'adc_value', 'adc_ctl',
                ]):
                    hw_strings.append(s)
            
            if hw_strings:
                print(f"\n    Hardware control strings ({len(hw_strings)}):")
                for s in sorted(set(hw_strings))[:80]:
                    print(f"      \"{s}\"")
    except Exception as e:
        print(f"    DEX analysis error: {e}")
    
    return a


def analyze_jar(jar_path):
    """Analyze JAR file (vendor framework)."""
    print(f"\n{'='*80}")
    print(f"  ANALYZING JAR: {jar_path.name}")
    print(f"{'='*80}")
    
    try:
        with zipfile.ZipFile(str(jar_path), 'r') as z:
            names = z.namelist()
            dex_files = [n for n in names if n.endswith('.dex')]
            print(f"  Files: {len(names)} total, {len(dex_files)} DEX files")
            
            for dex_name in dex_files:
                dex_data = z.read(dex_name)
                d = DEX(dex_data)
                classes = list(d.get_classes())
                print(f"\n  {dex_name}: {len(classes)} classes")
                
                for cls in sorted(classes, key=lambda c: c.get_name()):
                    name = cls.get_name()
                    print(f"    {name}")
                    
                    # Show methods for each class
                    methods = list(cls.get_methods())
                    if methods:
                        for m in methods:
                            print(f"      - {m.get_name()}({', '.join(str(p) for p in m.get_descriptor().split(')')[:1])})")
                
                # Get hardware strings
                strings = list(d.get_strings())
                hw_strings = [s for s in strings if any(p in s.lower() for p in [
                    '/sys/', '/dev/', 'keystone', 'projection', 'motor', 'focus',
                    'backlight', 'fan', 'hdmi', 'dispconfig', 'tvserver',
                    'ksc', 'ioctl', 'sysfs', 'vendor.sunxi', 'vendor.aw',
                    'projection/mode', 'bl_power', 'adc', 'pwm'
                ])]
                
                if hw_strings:
                    print(f"\n  Hardware strings:")
                    for s in sorted(set(hw_strings))[:50]:
                        print(f"    \"{s}\"")
    except Exception as e:
        print(f"  ERROR: {e}")


if __name__ == '__main__':
    # Analyze APKs in order of importance
    apk_order = [
        'CHIHI_Launcher.apk',
        'KeystoneCorrection.apk',
        'VideoInputService.apk',
        'AwManager.apk',
        'SettingsAssist.apk',
        'HxProjectorTest.apk',
    ]
    
    jar_order = [
        'com.softwinner.tv.jar',
        'awbms.jar',
        'softwinner.audio.jar',
    ]
    
    for apk_name in apk_order:
        apk_path = APK_DIR / apk_name
        if apk_path.exists():
            analyze_apk(apk_path)
    
    for jar_name in jar_order:
        jar_path = APK_DIR / jar_name
        if jar_path.exists():
            analyze_jar(jar_path)
