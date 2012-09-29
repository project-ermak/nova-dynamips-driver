#!/bin/sh

cd `dirname $0`

OPTS="--config-file=./cfg/nova.conf"
ADMIN=admin
USER=guest
PROJECT=ermak

nova-manage $OPTS db sync
nova-manage $OPTS user create --name="$USER" --access="" --secret=""
nova-manage $OPTS user $ADMIN --name="admin" --access="" --secret=""
nova-manage $OPTS project create --project="PROJECT" --user="$ADMIN"
nova-manage $OPTS user revoke --name="$USER" --project="PROJECT"
