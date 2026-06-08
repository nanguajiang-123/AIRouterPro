#!/bin/bash

sudo pkill -f ovs 2>/dev/null
sudo ovsdb-server --remote=punix:/var/run/openvswitch/db.sock \
                  --remote=db:Open_vSwitch,Open_vSwitch,manager_options \
                  --pidfile --detach
sudo ovs-vsctl --no-wait init
sudo ovs-vswitchd --pidfile --detach
sleep 1

sudo ovs-vsctl show > /dev/null 2>&1 && echo "✅ OVS ready" || { echo "❌ OVS failed"; exit 1; }

[ -z "$DISPLAY" ] && export DISPLAY=$(ip route | grep default | awk '{print $3}'):0

# Launch MiniEdit (patched: Run auto-exports topology + opens xterm)
sudo python3 /usr/lib/python3/dist-packages/mininet/examples/miniedit.py
