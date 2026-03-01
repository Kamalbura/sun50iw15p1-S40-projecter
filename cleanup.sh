#!/system/bin/sh
echo "=== ROOT CLEANUP SCRIPT ==="
echo "Running as: $(id)"

echo ""
echo "=== KILLING MALWARE PROCESSES ==="
for pkg in com.hx.appcleaner com.hx.videotest com.android.nfhelper com.chihihx.launcher com.android.nfx com.chihihx.store com.hx.update com.hx.apkbridge; do
    PID=$(ps -A -o PID,NAME | grep "$pkg" | awk '{print $1}')
    if [ -n "$PID" ]; then
        kill -9 $PID
        echo "  KILLED $pkg (PID $PID)"
    else
        echo "  $pkg not running"
    fi
done

echo ""
echo "=== DISABLING NFX ACCESSIBILITY SERVICE ==="
settings put secure enabled_accessibility_services ""
echo "  Accessibility services: $(settings get secure enabled_accessibility_services)"

echo ""
echo "=== BLOCKING OUTBOUND TO KNOWN C2 SERVERS ==="
iptables -A OUTPUT -d 116.202.8.16 -j DROP
iptables -A OUTPUT -d 116.202.8.0/24 -j DROP
echo "  Blocked 116.202.8.0/24 (Hetzner C2)"

echo ""
echo "=== BLOCKING QW DAEMON PORT 1234 ==="
iptables -A INPUT -p tcp --dport 1234 -j DROP
iptables -A INPUT -p tcp --dport 1234 ! -s 127.0.0.1 -j DROP
echo "  Blocked external access to port 1234"

echo ""
echo "=== REVOKING DANGEROUS PERMISSIONS ==="
for pkg in com.android.nfx com.hx.appcleaner com.chihihx.store com.hx.update; do
    pm revoke $pkg android.permission.INTERNET 2>/dev/null
    pm revoke $pkg android.permission.ACCESS_NETWORK_STATE 2>/dev/null
    pm revoke $pkg android.permission.ACCESS_WIFI_STATE 2>/dev/null
    echo "  Revoked network permissions from $pkg"
done

echo ""
echo "=== VERIFYING CLEANUP ==="
echo "  Remaining suspicious processes:"
ps -A -o USER,PID,NAME | grep -E "nfx|chihihx|hx\.|nfhelper|aptoid" || echo "    NONE - all clean!"

echo ""
echo "  Active outbound connections:"
netstat -tnp 2>/dev/null | grep -v "127.0.0.1\|0.0.0.0\|\[::\]" || echo "    No external connections"

echo ""
echo "  Listening ports:"
netstat -tlnp 2>/dev/null

echo ""
echo "  iptables rules:"
iptables -L -n --line-numbers 2>/dev/null

echo ""
echo "=== CLEANUP COMPLETE ==="
