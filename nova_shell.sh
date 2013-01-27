#!/bin/sh
cd `dirname $0`
echo "
alias nova-manage='nova-manage --config-file $(readlink -f `dirname $0`/etc/nova.conf)'
" > var/nova-shell-alias
source `dirname $0`/etc/novarc
bash --rcfile var/nova-shell-alias

