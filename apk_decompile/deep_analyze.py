#!/usr/bin/env python3
"""Deep analysis - extract actual method bytecode for hardware control classes."""
import os, sys
os.environ['LOGURU_LEVEL'] = 'ERROR'
import loguru; loguru.logger.remove(); loguru.logger.add(sys.stderr, level="ERROR")

from androguard.core.apk import APK
from androguard.core.dex import DEX

out = open('deep_analysis.txt', 'w', encoding='utf-8')
def p(s=''): print(s, file=out, flush=True)

def deep_analyze(apk_path, target_packages):
    """Analyze classes in target packages - show methods with their bytecode strings."""
    p(f"\n{'='*70}")
    p(f"  DEEP ANALYSIS: {apk_path}")
    p(f"{'='*70}")
    
    a = APK(apk_path)
    for i, dex_data in enumerate(a.get_all_dex()):
        d = DEX(dex_data)
        for cls in d.get_classes():
            name = cls.get_name()
            # Filter to target packages only
            if not any(pkg in name for pkg in target_packages):
                continue
            
            p(f"\n--- {name} ---")
            
            for m in cls.get_methods():
                mname = m.get_name()
                if mname in ('<clinit>',):
                    continue
                
                p(f"  {mname}()")
                
                # Try to get string references from method code
                code = m.get_code()
                if code is None:
                    p(f"    [no code - abstract/native]")
                    continue
                
                # Look at bytecode for string references
                try:
                    bc = code.get_bc()
                    for inst in bc.get_instructions():
                        op = inst.get_name()
                        output = inst.get_output()
                        
                        # Show string constants, method calls, and field accesses
                        if 'string' in op.lower() or 'const-string' in op.lower():
                            p(f"    STR: {output}")
                        elif 'invoke' in op.lower():
                            # Show method calls that are hardware-related
                            if any(kw in output.lower() for kw in [
                                'keystone', 'projection', 'motor', 'focus',
                                'backlight', 'fan', 'display', 'tvserver',
                                'systemproperties', 'setprop', 'getprop',
                                'surfaceflinger', 'parcel', 'writefloat',
                                'writeint', 'transact', 'binder',
                                'keystonecorrection', 'dispconfig',
                                'inputsource', 'setsource', 'getsource',
                                'hdmi', 'brightness', 'bl_power',
                                'runtime.exec', 'file', 'fileoutput',
                                'writetoparcel', 'flinger',
                                'motorctrl', 'setkeystonepar', 'getkeystonepar',
                                'setTrapezoid', 'gsensor', 'sensor',
                                'screenzoom', 'scalecircle', 'circleview',
                                'settings.system', 'settings.secure', 'settings.global',
                                'contentresolver', 'putint', 'putfloat', 'putstring',
                                'getint', 'getfloat', 'getstring',
                                'hxext', 'pddev', 'adcvalue',
                            ]):
                                p(f"    CALL: {output}")
                except Exception as e:
                    p(f"    [bytecode error: {e}]")

# 1. CHIHI_Launcher projector-related classes
p("============ CHIHI_Launcher - Projector Control Code ============")
deep_analyze('CHIHI_Launcher.apk', [
    'Lcom/shudong/lib_base/',
    'Lcom/chihihx/launcher/ui/activity/ProjectorActivity',
    'Lcom/chihihx/launcher/ui/activity/ScaleScreenActivity',
    'Lcom/chihihx/launcher/ui/fragment/ProjectorFragment',
    'Lcom/chihihx/launcher/ui/fragment/FocusFragment',
    'Lcom/chihihx/launcher/ui/fragment/ScaleScreenFragment',
    'Lcom/chihihx/launcher/service/',
    'Lcom/chihihx/launcher/ui/fragment/SettingFragment',
    'Lcom/chihihx/launcher/ui/fragment/MainFragment',
])

# 2. KeystoneCorrection core classes
p("\n\n============ KeystoneCorrection - Core Classes ============")
deep_analyze('KeystoneCorrection.apk', [
    'Lcom/softwinner/keystone/',
    'Lcom/softwinner/tcorrection/',
])

# 3. AwManager
p("\n\n============ AwManager - Board Management ============")
deep_analyze('AwManager.apk', [
    'Lcom/softwinner/awmanager/',
])

out.close()
print("Done! Output in deep_analysis.txt")
