#!/bin/bash
set -e

# ==========================================
# 统信UOS PySide6 一键环境配置脚本
# 功能：自动安装Miniconda + 创建pyside6_env + 安装最新版 PySide6 + 项目依赖
# 项目依赖：openpyxl, reportlab, pyinstaller, pandas, requests, numpy
# ==========================================

# -------------------------- 1. 颜色输出函数 --------------------------
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

print_info() { echo -e "${GREEN}[INFO]${NC} $1"; }
print_warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
print_error() { echo -e "${RED}[ERROR]${NC} $1"; }

# -------------------------- 2. 获取脚本所在目录 --------------------------
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
NODE_DIR="$SCRIPT_DIR/node"

# -------------------------- 3. 检测系统架构 --------------------------
print_info "正在检测系统架构..."
ARCH=$(uname -m)
print_info "当前架构: $ARCH"

if [[ "$ARCH" == "x86_64" ]]; then
    MINICONDA_URL="https://repo.anaconda.com/miniconda/Miniconda3-latest-Linux-x86_64.sh"
    NODE_VERSION="node-v20.10.0-linux-x64"
elif [[ "$ARCH" == "aarch64" ]]; then
    MINICONDA_URL="https://repo.anaconda.com/miniconda/Miniconda3-latest-Linux-aarch64.sh"
    NODE_VERSION="node-v20.10.0-linux-arm64"
else
    print_error "不支持的架构: $ARCH（仅支持 x86_64 和 aarch64）"
    exit 1
fi

# -------------------------- 4. 安装Miniconda --------------------------
MINICONDA_PATH="$HOME/miniconda3"
if [ -d "$MINICONDA_PATH" ]; then
    print_warn "Miniconda 已安装在 $MINICONDA_PATH，跳过安装"
else
    print_info "正在下载 Miniconda..."
    cd /tmp
    wget -q "$MINICONDA_URL" -O Miniconda3-latest.sh

    print_info "正在安装 Miniconda（自动模式）..."
    bash Miniconda3-latest.sh -b -p "$MINICONDA_PATH"

    print_info "正在初始化 Conda..."
    "$MINICONDA_PATH/bin/conda" init bash
    source "$HOME/.bashrc"
fi

# -------------------------- 5. 加载Conda环境 --------------------------
print_info "正在加载 Conda 环境..."
source "$MINICONDA_PATH/etc/profile.d/conda.sh"

# -------------------------- 6. 创建虚拟环境 --------------------------
ENV_NAME="pyside6_env"
PYTHON_VERSION="3.12"

if conda env list | grep -q "^$ENV_NAME "; then
    print_warn "虚拟环境 $ENV_NAME 已存在，跳过创建"
else
    print_info "正在创建虚拟环境 $ENV_NAME (Python $PYTHON_VERSION)..."
    conda create -n "$ENV_NAME" python="$PYTHON_VERSION" -y
fi

# -------------------------- 7. 激活虚拟环境并安装核心包 --------------------------
print_info "正在激活虚拟环境..."
conda activate "$ENV_NAME"

print_info "正在安装最新版 PySide6..."
conda install -c conda-forge pyside6 -y

# -------------------------- 8. 安装项目依赖（用 pip 安装，版本更灵活） --------------------------
print_info "正在安装项目依赖（openpyxl, reportlab, pyinstaller, pandas, requests, numpy）..."
pip install --upgrade pip -i https://pypi.tuna.tsinghua.edu.cn/simple
pip install \
    "openpyxl>=3.1" \
    "reportlab>=4.0" \
    "pyinstaller>=6.0" \
    "pandas>=2.0" \
    "requests>=2.31" \
    "numpy>=1.24" \
    -i https://pypi.tuna.tsinghua.edu.cn/simple

# -------------------------- 9. 配置Node.js环境（PDF解析必需） --------------------------
print_info "正在配置 Node.js 环境..."
mkdir -p "$NODE_DIR"

if [ -d "$NODE_DIR/${NODE_VERSION}/bin" ]; then
    print_warn "Node.js ${NODE_VERSION} 已存在，跳过下载"
else
    print_info "正在下载 Node.js v20.10.0 (${NODE_VERSION})..."

    TARBALL="${NODE_VERSION}.tar.xz"
    wget -q "https://nodejs.org/dist/v20.10.0/${TARBALL}" -O "/tmp/${TARBALL}"

    if [ $? -ne 0 ]; then
        print_error "Node.js 下载失败，请检查网络连接"
        print_error "或手动下载: https://nodejs.org/dist/v20.10.0/${TARBALL}"
        exit 1
    fi

    print_info "正在解压 Node.js..."
    tar -xf "/tmp/${TARBALL}" -C "$NODE_DIR"
    rm -f "/tmp/${TARBALL}"
fi

print_info "正在安装 mineru-open-api..."
cd "$NODE_DIR/${NODE_VERSION}"
./bin/npm install mineru-open-api

if [ $? -ne 0 ]; then
    print_error "mineru-open-api 安装失败，请检查网络连接"
    exit 1
fi

# -------------------------- 10. 验证所有安装 --------------------------
print_info "正在验证环境..."
python -c "
from PySide6.QtWidgets import QApplication
import PySide6
import openpyxl
import reportlab
import PyInstaller
import pandas
import requests
import numpy

print('✅ 所有依赖验证成功！')
print(f'  - PySide6: {PySide6.__version__}')
print(f'  - openpyxl: {openpyxl.__version__}')
print(f'  - reportlab: {reportlab.__version__}')
print(f'  - PyInstaller: {PyInstaller.__version__}')
print(f'  - pandas: {pandas.__version__}')
print(f'  - requests: {requests.__version__}')
print(f'  - numpy: {numpy.__version__}')
"

# 检查Node.js
if [ -f "$NODE_DIR/${NODE_VERSION}/bin/node" ]; then
    print_info "✅ Node.js: $NODE_DIR/${NODE_VERSION}/bin/node"
    "$NODE_DIR/${NODE_VERSION}/bin/node" --version
fi

# -------------------------- 11. 完成提示 --------------------------
echo ""
print_info "============================================="
print_info "  🎉 环境配置全部完成！"
print_info "============================================="
print_info "  - Miniconda 路径: $MINICONDA_PATH"
print_info "  - 虚拟环境名: $ENV_NAME"
print_info "  - Node.js 路径: $NODE_DIR/${NODE_VERSION}"
print_info ""
print_info "  下次使用前请先运行: conda activate $ENV_NAME"
print_info "============================================="
