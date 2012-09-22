#!/bin/sh

NOVA="../nova"
VENV=".venv"
ERMAK_PIP_REQUIRES="ermak-requires"
NOVA_PIP_REQUIRES=$NOVA/tools/pip-requires
TEST_PIP_REQUIRES=$NOVA/tools/test-requires

virtualenv --distribute -q --no-site-packages --unzip-setuptools $VENV
source $VENV/bin/activate

easy_install "pip>1.0"
pip install --upgrade pip
pip install --upgrade greenlet

pip install --upgrade -r $ERMAK_PIP_REQUIRES
pip install --upgrade -r $NOVA_PIP_REQUIRES
pip install --upgrade -r $TEST_PIP_REQUIRES

LOC=$(readlink -f `pwd`)
cd ../nova
python setup.py install
cd $LOC

