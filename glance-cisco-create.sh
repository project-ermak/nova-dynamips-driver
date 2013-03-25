#!/bin/sh
glance --os-auth-token=empty --os-image-url=http://localhost:9292 image-create --name 'c2691' --disk-format raw --container-format bare --is-public True
