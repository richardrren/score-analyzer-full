#!/bin/bash

echo "========================================"
echo "Node.js for Linux/UOS 配置脚本"
echo "========================================"
echo ""

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# 检测系统架构
ARCH=$(uname -m)
echo "检测到系统架构: $ARCH"

# 根据架构选择Node.js版本
if [ "$ARCH" = "aarch64" ] || [ "$ARCH" = "arm64" ]; then
    NODE_VERSION="node-v20.10.0-linux-arm64"
    echo "将下载 ARM64 版本的 Node.js"
elif [ "$ARCH" = "x86_64" ]; then
    NODE_VERSION="node-v20.10.0-linux-x64"
    echo "将下载 x64 版本的 Node.js"
else
    echo "不支持的架构: $ARCH"
    echo "支持的架构: x86_64 (x64), aarch64 (arm64)"
    exit 1
fi

# 检查对应版本的Node.js是否已存在
if [ -d "${NODE_VERSION}/bin" ]; then
    echo "${NODE_VERSION} 已存在，跳过下载"
else
    echo "正在下载 ${NODE_VERSION}..."

    TARBALL="${NODE_VERSION}.tar.xz"
    wget -q "https://nodejs.org/dist/v20.10.0/${TARBALL}"

    if [ $? -ne 0 ]; then
        echo "下载失败，请检查网络连接"
        echo "或手动下载: https://nodejs.org/dist/v20.10.0/${TARBALL}"
        exit 1
    fi

    echo "下载完成，正在解压..."
    tar -xf "$TARBALL"
    rm -f "$TARBALL"
fi

echo ""
echo "正在安装 mineru-open-api..."

cd "$NODE_VERSION"
./bin/npm install mineru-open-api

if [ $? -ne 0 ]; then
    echo "安装失败，请检查网络连接"
    exit 1
fi

echo ""
echo "========================================"
echo "配置完成！"
echo "========================================"
echo ""
echo "现在可以返回项目根目录运行程序了："
echo "  cd .."
echo "  python3 main.py"
echo ""
