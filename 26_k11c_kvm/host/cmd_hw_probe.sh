#!/bin/sh
echo '=== gst rockchip ==='
gst-inspect-1.0 2>/dev/null | grep -iE 'mpp|rga|rkximagesink|omx|mali'
echo '=== dri by-path ==='
ls -l /dev/dri/by-path/
echo '=== mpp dmesg ==='
dmesg | grep -iE 'mpp_|rkvenc|rkvdec|vdpu|vepu|rga|mali|RKNPU' | head -50
echo '=== lsmod ==='
lsmod | grep -iE 'mpp|rga|npu|mali|vpu' | head
echo '=== top snapshot ==='
top -bn1 | head -20
ps -eo pcpu,comm,args --sort=-pcpu | head -12
