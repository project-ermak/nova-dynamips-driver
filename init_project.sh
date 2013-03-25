#!/bin/sh

cd `dirname $0`
export PYTHONPATH=src/:src/ermak:$PATH

OPTS="--config-file=./etc/nova.conf"
ADMIN=admin
USER=guest
PROJECT=ermak

nova-manage $OPTS db sync
nova-manage $OPTS flavor create --name r1.c2691 --memory 128 --cpu 1 --root_gb=0 --ephemeral_gb=0 --flavor 10 --swap 0 --rxtx_factor 1
