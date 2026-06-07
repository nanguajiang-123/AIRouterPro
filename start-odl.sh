#!/bin/bash
# OpenDaylight One-Click Start
# Usage: ./start-odl.sh

WSL2_IP=$(ip addr show eth0 2>/dev/null | grep 'inet ' | awk '{print $2}' | cut -d/ -f1)

echo "=============================="
echo " ODL One-Click Start"
echo " IP: $WSL2_IP"
echo "=============================="

# 1. 启动 ODL
echo ""
echo "[1/4] Starting ODL..."
cd ~/AIRouterPro
docker compose down 2>/dev/null
docker compose up -d
echo "  Waiting 60s..."
sleep 60

# 2. 安装功能
echo ""
echo "[2/4] Installing features..."
for feat in odl-restconf odl-openflowplugin-flow-services-ui odl-dlux-core odl-dluxapps-topology; do
    echo "  $feat ..."
    echo "feature:install $feat" | docker exec -i odl-controller /opt/opendaylight/bin/client -b 2>/dev/null | grep -v WARN | grep -v 'client:' || true
done

# 3. 重启
echo ""
echo "[3/4] Restarting ODL..."
docker restart odl-controller
sleep 90

# 4. 验证 + 打开网页
echo ""
echo "[4/4] Verifying..."
curl -s -o /dev/null -w "  HTTP %{http_code}\n" -u admin:admin http://localhost:8181/restconf/operational/opendaylight-inventory:nodes

echo ""
echo "=============================="
echo " ODL Ready!"
echo " URL: http://$WSL2_IP:8181/index.html"
echo " User: admin / Pass: admin"
echo "=============================="
