#!/bin/bash

echo "========================================"
echo "Node.js for Linux/UOS 配置脚本"
echo "========================================"
echo ""

# 获取脚本所在目录
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# 检查Linux版Node.js是否已存在
if [ -d "node-v20.10.0-linux-x64/bin" ]; then
    echo "Linux版Node.js已存在，跳过下载"
else
    echo "正在下载 Node.js v20.10.0 for Linux x64..."

    wget -q https://nodejs.org/dist/v20.10.0/node-v20.10.0-linux-x64.tar.xz

    if [ $? -ne 0 ]; then
        echo "下载失败，请手动下载:"
        echo "https://nodejs.org/dist/v20.10.0/node-v20.10.0-linux-x64.tar.xz"
        exit 1
    fi

    echo "下载完成，正在解压..."
    tar -xf node-v20.10.0-linux-x64.tar.xz

    rm node-v20.10.0-linux-x64.tar.xz
fi

echo ""
echo "正在安装 mineru-open-api..."

cd node-v20.10.0-linux-x64
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
