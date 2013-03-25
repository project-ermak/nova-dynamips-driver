#!/bin/sh

NOVA="../nova"
GLANCE="../glance"
QUANTUM="../quantum"
VENV=".venv"
ERMAK_PIP_REQUIRES="ermak-requires"
NOVA_PIP_REQUIRES=$NOVA/tools/pip-requires
QUANTUM_PIP_REQUIRES=$QUANTUM/tools/pip-requires
GLANCE_PIP_REQUIRES=$GLANCE/tools/pip-requires
TEST_PIP_REQUIRES=$NOVA/tools/test-requires

virtualenv --distribute -q --no-site-packages --unzip-setuptools -p /opt/local/bin/python2.7 $VENV
source $VENV/bin/activate

easy_install "pip>1.0"
pip install --upgrade pip
pip install --upgrade greenlet

pip install --upgrade -r $ERMAK_PIP_REQUIRES
pip install --upgrade -r $NOVA_PIP_REQUIRES
pip install --upgrade -r $GLANCE_PIP_REQUIRES
pip install --upgrade -r $QUANTUM_PIP_REQUIRES
pip install --upgrade -r $TEST_PIP_REQUIRES

LOC=$(readlink -f `pwd`)
for d in $NOVA $GLANCE $QUANTUM; do
  pushd $d
  python setup.py install
  popd
done

