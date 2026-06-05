#!/bin/bash
# OpenDaylight + Mininet 启动脚本
# 用法: ./start-odl.sh [start|stop|restart|status]

WSL2_IP=172.18.162.66
ODL_DIR=

start_odl() {
    echo "[1/4] 启动 ODL 容器..."
    cd 
    docker compose up -d
    echo "等待 60 秒让 ODL 初始化..."
    sleep 60
    echo "ODL 已启动"
}

install_features() {
    echo "[2/4] 安装 ODL 功能..."
    docker exec odl-controller /opt/opendaylight/bin/client -b <<< 'feature:list -i' | grep -q odl-dluxapps-topology
    if [ 1 -ne 0 ]; then
        echo "安装功能..."
        docker exec odl-controller /opt/opendaylight/bin/client -b <<< 'feature:install odl-restconf'
        docker exec odl-controller /opt/opendaylight/bin/client -b <<< 'feature:install odl-restconf-all'
        docker exec odl-controller /opt/opendaylight/bin/client -b <<< 'feature:install odl-openflowplugin-flow-services-ui'
        docker exec odl-controller /opt/opendaylight/bin/client -b <<< 'feature:install odl-dlux-core'
        docker exec odl-controller /opt/opendaylight/bin/client -b <<< 'feature:install odl-dluxapps-topology'
        echo "重启 ODL..."
        docker restart odl-controller
        sleep 60
    else
        echo "功能已安装，跳过"
    fi
}

start_mininet() {
    echo "[3/4] 启动 Mininet 拓扑..."
    sudo mn -c 2>/dev/null
    sudo service openvswitch-switch start 2>/dev/null
    sudo python3 -c "
import os, time
from mininet.net import Mininet
from mininet.node import RemoteController, OVSSwitch
from mininet.log import setLogLevel
setLogLevel('info')

class ODLSwitch(OVSSwitch):
    def start(self, controllers):
        super().start(controllers)
        os.system('ovs-vsctl set bridge %s protocols=OpenFlow13' % self.name)

net = Mininet(controller=RemoteController, switch=ODLSwitch)
c0 = net.addController('c0', controller=RemoteController, ip='', port=6633)
s1 = net.addSwitch('s1')
for i in range(1, 4):
    net.addHost('h%d' % i)
    net.addLink(eval('h%d' % i), s1)

net.start()
time.sleep(2)
os.system('ovs-vsctl show')
print('拓扑运行中...')
try:
    while True:
        time.sleep(60)
except:
    net.stop()
" &
    sleep 5
    echo "Mininet 已启动"
}

verify() {
    echo "[4/4] 验证..."
    echo "ODL REST API: curl -u admin:admin http://localhost:8181/restconf/operational/opendaylight-inventory:nodes"
    curl -su admin:admin http://localhost:8181/restconf/operational/opendaylight-inventory:nodes | python3 -m json.tool
    echo "Web 界面: http://:8181/index.html"
}

case "" in
    start)
        start_odl
        install_features
        start_mininet
        verify
        ;;
    stop)
        sudo pkill -f mininet 2>/dev/null
        sudo pkill -f python3 2>/dev/null
        cd  && docker compose down
        ;;
    restart)
        /bin/bash stop
        sleep 5
        /bin/bash start
        ;;
    status)
        docker ps | grep odl-controller
        curl -su admin:admin http://localhost:8181/restconf/operational/opendaylight-inventory:nodes | python3 -m json.tool 2>/dev/null
        echo "Web 界面: http://:8181/index.html"
        ;;
    *)
        echo "用法: /bin/bash {start|stop|restart|status}"
        ;;
esac
