#!/bin/sh

cd `dirname $0`

export PYTHONPATH=src/:src/ermak:$PATH

mkdir -p var/log
screen -c all.screenrc

