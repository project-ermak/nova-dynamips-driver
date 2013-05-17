#!/bin/sh

glance image-create --name $1 --property hypervisor_type=qemu --disk-format iso --container-format bare --is-public True
