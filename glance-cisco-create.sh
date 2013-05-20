#!/bin/sh
glance image-create --disk-format raw --container-format bare --is-public True --name "$1" --property hypervisor_type=dynamips --property dynamips_platform="$2"
