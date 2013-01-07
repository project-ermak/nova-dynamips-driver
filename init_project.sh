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

nova-manage $OPTS flavor create --name r1.c2691 --memory 128 --cpu 1 --root_gb=0 --ephemeral_gb=0 --flavor 10 --swap 0 --rxtx_factor 1
