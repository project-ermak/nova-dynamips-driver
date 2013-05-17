#!/bin/sh
glance image-create --name $1 --property hypervisor_type=dynamips --disk-format raw --container-format bare --is-public True
