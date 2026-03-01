#!/usr/bin/env powershell
# S40 Projector Security Investigation & Defense Toolkit
# Usage: .\investigate.ps1 -IP "192.168.0.106" -Port 5555

param(
    [string]$IP = "192.168.0.106",
    [int]$Port = 5555,
    [switch]$DisableSuspicious,
    [switch]$MonitorNetwork,
    [switch]$PullAPKs
)

$Device = "${IP}:${Port}"
$OutputDir = ".\investigation_$(Get-Date -Format 'yyyyMMdd_HHmmss')"

function Write-Banner {
    Write-Host "`n========================================" -ForegroundColor Cyan
    Write-Host " S40 Projector Security Toolkit" -ForegroundColor Cyan
    Write-Host "========================================`n" -ForegroundColor Cyan
}

function Connect-Device {
    Write-Host "[*] Connecting to $Device..." -ForegroundColor Yellow
    $result = adb connect $Device 2>&1
    if ($result -match "connected") {
        Write-Host "[+] Connected successfully!" -ForegroundColor Green
        return $true
    } else {
        Write-Host "[-] Connection failed: $result" -ForegroundColor Red
        return $false
    }
}

function Get-DeviceInfo {
    Write-Host "`n[*] Gathering device information..." -ForegroundColor Yellow
    
    $info = @{
        "Model (Fake)"     = (adb -s $Device shell getprop ro.product.model)
        "Model (Real)"     = (adb -s $Device shell getprop oem.product.model)
        "Brand"            = (adb -s $Device shell getprop ro.product.brand)
        "Manufacturer"     = (adb -s $Device shell getprop ro.product.manufacturer)
        "Device"           = (adb -s $Device shell getprop ro.product.device)
        "Android Version"  = (adb -s $Device shell getprop ro.build.version.release)
        "SDK"              = (adb -s $Device shell getprop ro.build.version.sdk)
        "Build Type"       = (adb -s $Device shell getprop ro.build.type)
        "Build Tags"       = (adb -s $Device shell getprop ro.build.tags)
        "SELinux"          = (adb -s $Device shell getenforce)
        "ADB Secure"       = (adb -s $Device shell getprop ro.adb.secure)
        "Hardware"         = (adb -s $Device shell getprop ro.boot.hardware)
        "Platform"         = (adb -s $Device shell getprop ro.board.platform)
        "Fingerprint"      = (adb -s $Device shell getprop ro.build.fingerprint)
        "Firmware"         = (adb -s $Device shell getprop persist.sys.firmware)
        "Display (Real)"   = (adb -s $Device shell getprop persist.vendor.disp.screensize)
        "Serial"           = (adb -s $Device shell getprop ro.boot.serialno)
        "RAM Config"       = (adb -s $Device shell getprop persist.sys.ramconfig)
    }
    
    foreach ($key in $info.Keys | Sort-Object) {
        $value = $info[$key].Trim()
        $color = "White"
        if ($key -match "Fake" -or ($key -eq "Brand" -and $value -eq "google") -or ($key -eq "SELinux" -and $value -eq "Permissive")) {
            $color = "Red"
        }
        Write-Host "  $($key.PadRight(20)): $value" -ForegroundColor $color
    }
    
    # Security assessment
    Write-Host "`n[!] SECURITY ISSUES:" -ForegroundColor Red
    $selinux = (adb -s $Device shell getenforce).Trim()
    $adbSecure = (adb -s $Device shell getprop ro.adb.secure).Trim()
    $buildType = (adb -s $Device shell getprop ro.build.type).Trim()
    $buildTags = (adb -s $Device shell getprop ro.build.tags).Trim()
    
    if ($selinux -eq "Permissive") { Write-Host "  [CRITICAL] SELinux is PERMISSIVE - security disabled!" -ForegroundColor Red }
    if ($adbSecure -eq "0") { Write-Host "  [CRITICAL] ADB has NO authentication!" -ForegroundColor Red }
    if ($buildType -eq "userdebug") { Write-Host "  [HIGH] Running userdebug build (not production)" -ForegroundColor Red }
    if ($buildTags -eq "test-keys") { Write-Host "  [HIGH] Signed with test-keys (insecure)" -ForegroundColor Red }
}

function Get-SuspiciousPackages {
    Write-Host "`n[*] Checking for suspicious packages..." -ForegroundColor Yellow
    
    $suspiciousPackages = @(
        @{ Name = "com.android.nfx"; Risk = "CRITICAL"; Desc = "Netflix AccessibilityService malware" },
        @{ Name = "com.chihihx.store"; Risk = "HIGH"; Desc = "Custom app store (runs as SYSTEM)" },
        @{ Name = "com.chihihx.launcher"; Risk = "MEDIUM"; Desc = "Custom launcher (runs as SYSTEM)" },
        @{ Name = "com.hx.update"; Risk = "HIGH"; Desc = "OTA updater with INSTALL_PACKAGES (SYSTEM)" },
        @{ Name = "com.hx.appcleaner"; Risk = "HIGH"; Desc = "App cleaner with excessive permissions (SYSTEM)" },
        @{ Name = "com.hx.apkbridge"; Risk = "MEDIUM"; Desc = "APK sideload bridge" },
        @{ Name = "com.android.nfhelper"; Risk = "MEDIUM"; Desc = "Netflix helper (SYSTEM)" },
        @{ Name = "com.hx.guardservice"; Risk = "LOW"; Desc = "Factory stress test guard" },
        @{ Name = "com.dd.bugreport"; Risk = "LOW"; Desc = "Custom bug report service" },
        @{ Name = "cm.aptoidetv.pt"; Risk = "MEDIUM"; Desc = "Third-party app store (Aptoide)" }
    )
    
    foreach ($pkg in $suspiciousPackages) {
        $installed = adb -s $Device shell pm list packages $pkg.Name 2>&1
        if ($installed -match $pkg.Name) {
            $enabled = adb -s $Device shell pm list packages -e $pkg.Name 2>&1
            $status = if ($enabled -match $pkg.Name) { "ENABLED" } else { "DISABLED" }
            $color = switch ($pkg.Risk) {
                "CRITICAL" { "Red" }
                "HIGH" { "DarkYellow" }
                "MEDIUM" { "Yellow" }
                default { "Gray" }
            }
            Write-Host "  [$($pkg.Risk)] $($pkg.Name) [$status] - $($pkg.Desc)" -ForegroundColor $color
        }
    }
}

function Get-NetworkConnections {
    Write-Host "`n[*] Checking network connections..." -ForegroundColor Yellow
    
    $netstat = adb -s $Device shell "netstat -tnp 2>/dev/null; netstat -tlnp 2>/dev/null; netstat -ulnp 2>/dev/null"
    Write-Host $netstat
    
    # Check for external connections
    $external = $netstat | Select-String -Pattern "\d+\.\d+\.\d+\.\d+.*(?!192\.168|10\.|172\.1[6-9]|172\.2|172\.3[01]|127\.0)" | 
        Where-Object { $_ -notmatch "0\.0\.0\.0" -and $_ -notmatch "192\.168\." -and $_ -notmatch "\[::\]" }
    
    if ($external) {
        Write-Host "`n  [!] EXTERNAL CONNECTIONS DETECTED:" -ForegroundColor Red
        $external | ForEach-Object { Write-Host "    $_" -ForegroundColor Red }
    }
    
    # Check listening ports
    Write-Host "`n  Listening ports:" -ForegroundColor Yellow
    $listening = $netstat | Select-String "LISTEN"
    $listening | ForEach-Object { Write-Host "    $_" -ForegroundColor White }
}

function Disable-SuspiciousApps {
    Write-Host "`n[*] Disabling suspicious packages..." -ForegroundColor Yellow
    
    $toDisable = @(
        "com.android.nfx",
        "com.chihihx.store",
        "com.hx.apkbridge",
        "com.hx.appcleaner",
        "com.hx.update",
        "com.dd.bugreport",
        "com.hx.guardservice"
    )
    
    foreach ($pkg in $toDisable) {
        Write-Host "  Disabling $pkg..." -NoNewline
        $result = adb -s $Device shell "pm disable-user --user 0 $pkg" 2>&1
        if ($result -match "disabled") {
            Write-Host " OK" -ForegroundColor Green
        } else {
            Write-Host " $result" -ForegroundColor Yellow
        }
    }
}

function Start-NetworkMonitor {
    Write-Host "`n[*] Starting network monitor (Ctrl+C to stop)..." -ForegroundColor Yellow
    Write-Host "  Watching for new connections every 5 seconds...`n"
    
    $previousConnections = @()
    
    while ($true) {
        $current = adb -s $Device shell "cat /proc/net/tcp /proc/net/tcp6 2>/dev/null"
        $timestamp = Get-Date -Format "HH:mm:ss"
        
        $newConnections = $current | Where-Object { $_ -notin $previousConnections -and $_ -match "^\s+\d+:" }
        
        if ($newConnections) {
            foreach ($conn in $newConnections) {
                Write-Host "  [$timestamp] NEW: $conn" -ForegroundColor Yellow
            }
        }
        
        $previousConnections = $current
        Start-Sleep -Seconds 5
    }
}

function Export-APKs {
    Write-Host "`n[*] Pulling suspicious APKs for analysis..." -ForegroundColor Yellow
    
    New-Item -ItemType Directory -Path $OutputDir -Force | Out-Null
    
    $apks = @{
        "com.android.nfx" = "nfx_malware"
        "com.hx.update" = "hx_update"
        "com.hx.appcleaner" = "hx_appcleaner"
        "com.android.nfhelper" = "nfhelper"
        "com.chihihx.store" = "chihihx_store"
        "com.dd.bugreport" = "bugreport"
        "com.hx.apkbridge" = "apkbridge"
    }
    
    foreach ($pkg in $apks.Keys) {
        $path = (adb -s $Device shell pm path $pkg 2>&1) -replace "package:", ""
        if ($path -and $path -notmatch "not found") {
            $outFile = Join-Path $OutputDir "$($apks[$pkg]).apk"
            Write-Host "  Pulling $pkg -> $outFile..." -NoNewline
            adb -s $Device pull $path.Trim() $outFile 2>&1 | Out-Null
            Write-Host " OK" -ForegroundColor Green
        }
    }
    
    # Also dump all props and logcat
    Write-Host "  Dumping system properties..." -NoNewline
    adb -s $Device shell getprop > (Join-Path $OutputDir "all_properties.txt") 2>&1
    Write-Host " OK" -ForegroundColor Green
    
    Write-Host "  Dumping logcat..." -NoNewline
    adb -s $Device shell "logcat -d -b all" > (Join-Path $OutputDir "logcat.txt") 2>&1
    Write-Host " OK" -ForegroundColor Green
    
    Write-Host "`n  [+] All files saved to: $OutputDir" -ForegroundColor Green
}

# Main execution
Write-Banner

if (-not (Connect-Device)) { exit 1 }

Get-DeviceInfo
Get-SuspiciousPackages
Get-NetworkConnections

if ($DisableSuspicious) {
    Disable-SuspiciousApps
}

if ($PullAPKs) {
    Export-APKs
}

if ($MonitorNetwork) {
    Start-NetworkMonitor
}

Write-Host "`n[*] Investigation complete. See INVESTIGATION_REPORT.md for full analysis." -ForegroundColor Cyan
Write-Host "[*] Run with -DisableSuspicious to disable malware apps" -ForegroundColor Cyan
Write-Host "[*] Run with -MonitorNetwork to watch for new connections" -ForegroundColor Cyan
Write-Host "[*] Run with -PullAPKs to extract suspicious APKs`n" -ForegroundColor Cyan
