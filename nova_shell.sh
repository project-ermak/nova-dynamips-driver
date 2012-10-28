alias nova-manage="nova-manage --config-file $(readlink -f ./cfg/nova.conf)"
source `dirname $0`/cfg/novarc
bash
