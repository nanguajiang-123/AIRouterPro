#!/bin/bash

# 清理可能残留的 OVS 进程
sudo pkill -f ovs 2>/dev/null

# 启动 OVS 数据库服务器
sudo ovsdb-server --remote=punix:/var/run/openvswitch/db.sock \
                  --remote=db:Open_vSwitch,Open_vSwitch,manager_options \
                  --pidfile --detach

# 初始化 OVS 数据库（如果未初始化）
sudo ovs-vsctl --no-wait init

# 启动 OVS 守护进程
sudo ovs-vswitchd --pidfile --detach

# 等待一秒，确保服务启动
sleep 1

# 验证 OVS 状态
if sudo ovs-vsctl show > /dev/null 2>&1; then
    echo "✅ Open vSwitch started successfully."
else
    echo "❌ Failed to start Open vSwitch."
    exit 1
fi

# 设置 DISPLAY（如果未设置）
if [ -z "$DISPLAY" ]; then
    export DISPLAY=$(ip route | grep default | awk '{print $3}'):0
    echo "Set DISPLAY to $DISPLAY"
fi

# 启动 MiniEdit
echo "Launching MiniEdit..."
sudo python3 /usr/lib/python3/dist-packages/mininet/examples/miniedit.py