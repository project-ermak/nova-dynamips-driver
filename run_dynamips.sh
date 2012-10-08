#!/bin/sh

DATADIR=${DATADIR:-$(dirname $0)/var/dynamips}
HOST=127.0.0.1
PORT=7200

cd $DATADIR
dynamips -H $HOST:$PORT
