#!/bin/sh
cd `dirname $0`
echo " 
alias quantum='quantum --os-auth-strategy=none --os-url=http://0.0.0.0:9696/ '
" > var/quantum-shell-alias

bash --rcfile var/quantum-shell-alias
