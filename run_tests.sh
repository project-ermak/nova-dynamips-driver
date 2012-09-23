#!/bin/sh

PYTHONPATH=src/:src/ermak:$PATH python -mnova.testing.runner -w src/ermak/test/
