#/bin/env bash
MYHOSTS="$WIN_IP\twindows"
grep windows /etc/hosts >> /dev/null || echo -e $MYHOSTS | sudo tee -a /etc/hosts >> /dev/null
