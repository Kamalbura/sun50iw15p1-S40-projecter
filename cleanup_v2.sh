#!/system/bin/sh
echo "=== AGGRESSIVE CLEANUP v2 - ROOT ==="
echo "Running as: $(id)"

echo ""
echo "=== PHASE 1: FORCE-STOP + DISABLE (prevents respawn) ==="
for pkg in com.android.nfx com.chihihx.store com.chihihx.launcher com.hx.appcleaner com.hx.update com.hx.apkbridge com.android.nfhelper com.hx.videotest com.hx.guardservice com.dd.bugreport cm.aptoidetv.pt; do
    am force-stop $pkg 2>/dev/null
    pm disable $pkg 2>/dev/null
    echo "  Disabled: $pkg"
done

echo ""
echo "=== PHASE 2: KILL ALL REMNANT PIDS ==="
for pkg in com.hx.appcleaner com.hx.videotest com.android.nfhelper com.chihihx.launcher com.android.nfx com.chihihx.store com.hx.update; do
    PIDS=$(ps -A -o PID,NAME | grep "$pkg" | awk '{print $1}')
    for PID in $PIDS; do
        kill -9 $PID 2>/dev/null
        echo "  Killed PID $PID ($pkg)"
    done
done

echo ""
echo "=== PHASE 3: REMOVE NFX ACCESSIBILITY SERVICE CONFIG ==="
settings put secure enabled_accessibility_services ""
settings put secure accessibility_enabled 0
echo "  Accessibility services cleared and disabled"

echo ""
echo "=== PHASE 4: REVOKE ALL PERMISSIONS ==="
for pkg in com.android.nfx com.hx.appcleaner com.chihihx.store com.hx.update com.hx.apkbridge com.android.nfhelper com.hx.videotest; do
    pm clear --user 0 $pkg 2>/dev/null
    echo "  Cleared data for $pkg"
done

echo ""
echo "=== PHASE 5: NETWORK LOCKDOWN ==="
# Block known C2
iptables -D OUTPUT -d 116.202.8.16 -j DROP 2>/dev/null
iptables -D OUTPUT -d 116.202.8.0/24 -j DROP 2>/dev/null
iptables -A OUTPUT -d 116.202.8.16 -j DROP
iptables -A OUTPUT -d 116.202.8.0/24 -j DROP

# Block port 1234 from external
iptables -D INPUT -p tcp --dport 1234 -j DROP 2>/dev/null
iptables -A INPUT -p tcp ! -s 127.0.0.1 --dport 1234 -j DROP

# Block the disabled apps from talking to network via UID
# uid 1000 = system (shared by the malware apps)
# We can't block uid 1000 entirely as it would break system, but we can log it
iptables -D OUTPUT -m owner --uid-owner 1000 -j LOG --log-prefix "SYSTEM_NET: " 2>/dev/null
iptables -A OUTPUT -m owner --uid-owner 1000 -j LOG --log-prefix "SYSTEM_NET: "

echo "  Network lockdown rules applied"

echo ""
echo "=== PHASE 6: VERIFY ==="
echo "--- Suspicious processes ---"
ps -A -o USER,PID,NAME | grep -E "nfx|chihihx|hx\.|nfhelper|aptoid" || echo "  CLEAN!"

echo ""
echo "--- Network connections ---"
netstat -tnp 2>/dev/null

echo ""
echo "--- Listening ports ---"
netstat -tlnp 2>/dev/null

echo ""
echo "--- Disabled packages ---"
pm list packages -d 2>/dev/null

echo ""
echo "--- iptables OUTPUT chain ---"
iptables -L OUTPUT -n --line-numbers

echo ""
echo "=== AGGRESSIVE CLEANUP COMPLETE ==="
