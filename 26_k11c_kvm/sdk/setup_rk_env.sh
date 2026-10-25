#!/usr/bin/env bash
# KICKPI K11C — rk-linux6.1 SDK 编译环境安装 v3
# 依据 https://doc.kickpi.cn/Products/SDK-Compilation/RK356x-RK3588/Linux_SDK/
# 用法： bash ~/setup_rk_env.sh 2>&1 | tee ~/setup_rk_env.log
#
# v3 修正：去掉 python-pip（与 python3-pip 互斥，实测 Breaks 导致整批不装）
# v2 修正：ncurses-dev->libncurses-dev, lib32ncurses5-dev->libncurses-dev:i386, expect-dev->tcl8.6-dev
set -uo pipefail

PKGS="autoconf bc binfmt-support bison build-essential bzip2
chrpath cmake cpp-aarch64-linux-gnu curl device-tree-compiler diffstat
expat expect tcl8.6-dev fakeroot flex
g++ g++-multilib gawk gcc gcc-multilib git gnupg gperf gpgv2 imagemagick
libncurses-dev libncurses-dev:i386 lib32readline-dev lib32z1-dev libgmp-dev
libgucharmap-2-90-dev liblz4-tool libmpc-dev
libncurses5-dev libsdl1.2-dev libssl-dev libwxgtk3.0-gtk3-dev
libxml2 libxml2-utils live-build lzop
make module-assistant openjdk-8-jdk
patchelf pngcrush python2 python-is-python3 python3-pip
qemu-user-static rsync schedtool squashfs-tools ssh sudo
texinfo u-boot-tools unzip
xsltproc yasm zip zlib1g-dev"

echo ">>> apt-get update"
sudo -n true 2>/dev/null || sudo apt-get update || sudo apt-get update

echo ">>> 第一步：整批装（快路径）"
if sudo apt-get install -y $PKGS; then
  echo "    整批成功"
  FAILED=""
else
  echo "    整批失败，改为逐包安装定位冲突（失败的会列出来）"
  FAILED=""
  for p in $PKGS; do
    if sudo apt-get install -y "$p" >/dev/null 2>&1; then
      :
    else
      FAILED="$FAILED $p"
    fi
  done
fi

echo ">>> 补装 pyelftools"
python3 -m pip install --user pyelftools || sudo pip3 install pyelftools

echo ">>> binfmt + qemu（官方要求 --reinstall）"
sudo apt-get install -y --reinstall binfmt-support qemu-user-static

echo ">>> python -> python2 软链（官方最后一条；回退： sudo ln -sf /usr/bin/python3 /usr/bin/python）"
sudo ln -sf /usr/bin/python2 /usr/bin/python

echo ""
echo "================ 装完自检 ================"
for t in git tar curl rsync make bc bison flex dtc python python2 python3 java pip3; do
  printf "%-10s " "$t"; command -v "$t" 2>/dev/null || echo "缺"
done
echo "python 指向： $(readlink -f "$(command -v python || echo /bin/false)")"
echo ""
if [ -n "${FAILED:-}" ]; then
  echo "!!! 这些包没装上，需要人工决定：$FAILED"
  for p in $FAILED; do echo "  --- $p ---"; sudo apt-get install -y "$p" 2>&1 | grep -E "Breaks|Depends|unmet|Unable|E:" | head -4; done
else
  echo "全部包安装成功"
fi
