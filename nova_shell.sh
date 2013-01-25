#!/bin/sh
alias nova-manage="nova-manage --config-file $(readlink -f ./etc/nova.conf)"
source `dirname $0`/cfg/novarc
bash
