#!/bin/sh
# 交叉编译云客户端（现在挂 JetKVM 的云，将来可以指我们自己搭的那套，见 15_ §9）。
#
# 编译器在 rk-vm 上：Go 解在 ~/go-toolchain/go，模块缓存 ~/gopath，构建缓存 ~/gocache。
# go.mod 里必须写 `go 1.24.0`：pion/rtp v1.10.5 要求 go >= 1.24，而 GOTOOLCHAIN=auto
# 只看主模块的 go 指令、不看依赖的要求 —— 写 1.23 会直接报
# "requires go >= 1.24.0 (running go 1.23.4)"（2026-11-01 踩过两次）。
#
# 用法：
#   sh build.sh            只编译，产物 ./k11c-cloud（不进 git）
#   sh build.sh --deploy   顺带推到板上、覆盖并拉起（板子上还没有 systemd 单元）
set -e
VM=${VM:-rk@192.168.234.141}
BOARD=${BOARD:-kickpi@192.168.31.89}
SUDO=${K11C_SUDO:-kickpi}
# 注意：这里写"相对路径"（落在 VM 的 $HOME 下），不能写 ~/k11c-cloud ——
# 那会被本地 shell 展开成 Windows 的家目录，scp 直接报 No such file or directory。
D=k11c-cloud

scp -q main.go go.mod go.sum "$VM:$D/"
ssh "$VM" "export PATH=\$HOME/go-toolchain/go/bin:\$PATH GOPATH=\$HOME/gopath GOCACHE=\$HOME/gocache;
           cd $D && gofmt -w *.go && go vet . &&
           GOOS=linux GOARCH=arm64 CGO_ENABLED=0 go build -ldflags='-s -w' -o k11c-cloud . && ls -l k11c-cloud"
scp -q "$VM:$D/k11c-cloud" ./k11c-cloud
echo "产物 ./k11c-cloud（不进 git；部署目标 /opt/k11c-kvm/k11c-cloud）"

if [ "$1" = "--deploy" ]; then
    # 运行中的二进制不能直接 cp（Text file busy），必须先停再覆盖
    scp -q ./k11c-cloud "$BOARD:/tmp/k11c-cloud.new"
    ssh "$BOARD" "printf '%s\n' '$SUDO' | sudo -S -p '' sh -c '
        pkill -x k11c-cloud; sleep 1
        cp /tmp/k11c-cloud.new /opt/k11c-kvm/k11c-cloud
        chmod 755 /opt/k11c-kvm/k11c-cloud
        setsid nohup /opt/k11c-kvm/k11c-cloud --state /etc/k11c/cloud.json \
            --rtp 127.0.0.1:5005 >/tmp/cloudkvm.log 2>&1 </dev/null &
        sleep 4; pgrep -ax k11c-cloud; tail -3 /tmp/cloudkvm.log'"
    echo "看上线与推流：ssh $BOARD 'tail -f /tmp/cloudkvm.log'（需要 sudo 才读得到）"
fi
