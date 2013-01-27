#!/bin/sh
cd `dirname $0`
echo " 
alias quantum='quantum --logfile $(readlink -f $(dirname $0)/var/log/quantum-client.log)'
" > var/quantum-shell-alias

bash --rcfile var/quantum-shell-alias
