#!/bin/sh
# 交叉编译板内 WebRTC 网关（JetKVM 同款 pion 路线）。
# 编译器在 rk-vm 上：Go 1.23.4 解在 ~/go-toolchain/go，模块缓存 ~/gopath，构建缓存 ~/gocache。
# 工程与 go.mod/go.sum 在 VM 的 ~/k11c-gw（依赖只 pion/webrtc v4，已缓存好，断网也能编）。
# 产物是静态 ARM64 单文件（CGO_ENABLED=0），板上不装任何东西。
set -e
VM=rk@192.168.234.141
D=~/k11c-gw

scp -q main.go util.go "$VM:$D/"
ssh "$VM" "export PATH=\$HOME/go-toolchain/go/bin:\$PATH GOPATH=\$HOME/gopath GOCACHE=\$HOME/gocache;
           cd $D && gofmt -w *.go && go vet ./... &&
           GOOS=linux GOARCH=arm64 CGO_ENABLED=0 go build -ldflags='-s -w' -o k11c-gw . && ls -l k11c-gw"
scp -q "$VM:$D/k11c-gw" ./k11c-gw
echo "产物 ./k11c-gw（不进 git；部署目标 /opt/k11c-kvm/k11c-gw）"
