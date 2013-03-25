#!/bin/sh

alias quantum='quantum --os-auth-strategy=none --os-url=http://0.0.0.0:9696/ '

NET=`quantum net-create mynet --tenant-id=test_tenant -f shell | grep "^id=" | sed -re 's/id=//;s/\"//g'`
echo "Net is $NET"
PORT=`quantum port-create $NET --tenant-id=test_tenant -f shell | grep "^id=" | sed -re 's/id=//;s/\"//g'`
echo "Port is $PORT"
# quantum ??? test_tenant $NET $PORT myiface0
# quantum ??? test_tenant $NET $PORT
quantum port-delete $PORT
quantum net-delete $NET
