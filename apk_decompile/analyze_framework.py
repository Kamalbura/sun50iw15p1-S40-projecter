#!/usr/bin/env python3
"""Deep analysis of com.softwinner.tv.jar AwTvDisplayManager, VideoInputService, and CHIHI_Launcher projector fragments"""
import os, sys
os.environ['LOGURU_LEVEL'] = 'ERROR'
import loguru
loguru.logger.remove()
loguru.logger.add(sys.stderr, level="ERROR")

from androguard.core.apk import APK
from androguard.core.dex import DEX

def analyze_dex_classes(dex_data, target_packages, label):
    """Analyze all classes matching target package prefixes"""
    dex = DEX(dex_data)
    results = []
    
    for cls in dex.get_classes():
        cls_name = cls.get_name()
        # Check if class matches any target package
        if not any(cls_name.startswith(p) for p in target_packages):
            continue
        
        results.append(f"\n--- {cls_name} ---")
        
        for method in cls.get_methods():
            method_name = method.get_name()
            # Get method descriptor for parameter info
            desc = method.get_descriptor()
            results.append(f"  {method_name}{desc}")
            
            code = method.get_code()
            if code is None:
                results.append(f"    (abstract/native)")
                continue
            
            bc = code.get_bc()
            if bc is None:
                continue
            
            for inst in bc.get_instructions():
                op = inst.get_name()
                output = inst.get_output()
                
                # Capture string constants
                if 'const-string' in op and output:
                    val = output.split(',')[-1].strip().strip("'\"")
                    if val and len(val) > 1:
                        results.append(f"    STR: {val}")
                
                # Capture all method calls (invoke-*)
                if 'invoke' in op and output:
                    # Extract the method reference
                    parts = output.split(',')
                    if len(parts) > 0:
                        method_ref = parts[-1].strip()
                        if '->' in method_ref:
                            results.append(f"    CALL: {method_ref}")
                
                # Capture field access (sget/sput/iget/iput)
                if ('sget' in op or 'sput' in op or 'iget' in op or 'iput' in op) and output:
                    parts = output.split(',')
                    if len(parts) > 0:
                        field_ref = parts[-1].strip()
                        if '->' in field_ref:
                            results.append(f"    FIELD: {op} {field_ref}")
    
    return results

def analyze_jar(jar_path, target_packages, label):
    """Analyze a JAR file's DEX contents"""
    import zipfile
    results = [f"\n{'='*70}", f"  {label}: {os.path.basename(jar_path)}", f"{'='*70}"]
    
    with zipfile.ZipFile(jar_path, 'r') as zf:
        for name in zf.namelist():
            if name.endswith('.dex'):
                dex_data = zf.read(name)
                results.extend(analyze_dex_classes(dex_data, target_packages, label))
    
    return results

def analyze_apk(apk_path, target_packages, label):
    """Analyze an APK file's DEX contents"""
    results = [f"\n{'='*70}", f"  {label}: {os.path.basename(apk_path)}", f"{'='*70}"]
    
    apk = APK(apk_path)
    for dex_data in apk.get_all_dex():
        results.extend(analyze_dex_classes(dex_data, target_packages, label))
    
    return results

basedir = r"c:\Users\burak\ptojects\projecter\apk_decompile"
all_results = []

# 1. AwTvDisplayManager from com.softwinner.tv.jar - THE critical hardware bridge
all_results.append("\n" + "="*70)
all_results.append("  SECTION 1: AwTvDisplayManager (Hardware Bridge)")
all_results.append("="*70)
all_results.extend(analyze_jar(
    os.path.join(basedir, "com.softwinner.tv.jar"),
    ["Lcom/softwinner/tv/AwTvDisplayManager", "Lcom/softwinner/tv/AwTvCommon"],
    "TV Framework - AwTvDisplayManager"
))

# 2. Full ITvServer proxy class (the actual implementation that calls HIDL)
all_results.append("\n" + "="*70)
all_results.append("  SECTION 2: ITvServer Proxy (HIDL Client)")
all_results.append("="*70)
all_results.extend(analyze_jar(
    os.path.join(basedir, "com.softwinner.tv.jar"),
    ["Lvendor/aw/homlet/tvsystem/tvserver/V1_0/ITvServer$Proxy"],
    "ITvServer HIDL Proxy"
))

# 3. VideoInputService - HDMI/CVBS input handling
all_results.append("\n" + "="*70)
all_results.append("  SECTION 3: VideoInputService (HDMI/CVBS)")
all_results.append("="*70)
all_results.extend(analyze_apk(
    os.path.join(basedir, "VideoInputService.apk"),
    [
        "Lcom/softwinner/vis/",
        "Lcom/softwinner/tvinput/",
    ],
    "VideoInputService"
))

# 4. CHIHI_Launcher projector-related classes
all_results.append("\n" + "="*70)
all_results.append("  SECTION 4: CHIHI_Launcher Projector Integration")
all_results.append("="*70)
all_results.extend(analyze_apk(
    os.path.join(basedir, "CHIHI_Launcher.apk"),
    [
        "Lcom/chihihx/launcher/ui/activity/Projector",
        "Lcom/chihihx/launcher/ui/activity/Setting",
        "Lcom/chihihx/launcher/ui/activity/ScaleScreen",
        "Lcom/chihihx/launcher/ui/activity/Focus",
        "Lcom/chihihx/launcher/ui/fragment/Projector",
        "Lcom/chihihx/launcher/ui/fragment/Setting",
        "Lcom/chihihx/launcher/ui/fragment/Focus",
        "Lcom/chihihx/launcher/utils/Projector",
        "Lcom/chihihx/launcher/utils/Hardware",
        "Lcom/chihihx/launcher/utils/Display",
        "Lcom/chihihx/launcher/utils/System",
        "Lcom/chihihx/launcher/model/Projector",
        "Lcom/chihihx/launcher/model/Setting",
        "Lcom/hx/",
    ],
    "CHIHI_Launcher Projector"
))

# 5. awbms.jar - board management system
all_results.append("\n" + "="*70)
all_results.append("  SECTION 5: awbms.jar (Board Management System)")
all_results.append("="*70)
all_results.extend(analyze_jar(
    os.path.join(basedir, "awbms.jar"),
    ["L"],  # all classes
    "AW Board Management System"
))

# 6. softwinner.audio.jar - Audio framework
all_results.append("\n" + "="*70)
all_results.append("  SECTION 6: softwinner.audio.jar (Audio Framework)")
all_results.append("="*70)
all_results.extend(analyze_jar(
    os.path.join(basedir, "softwinner.audio.jar"),
    ["Lcom/softwinner/", "Landroid/media/"],
    "Softwinner Audio Framework"
))

outfile = os.path.join(basedir, "framework_analysis.txt")
with open(outfile, 'w', encoding='utf-8') as f:
    f.write('\n'.join(all_results))

print(f"Written {len(all_results)} lines to {outfile}")
print(f"File size: {os.path.getsize(outfile)} bytes")
