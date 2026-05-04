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

# -------------------------- 2. 检测系统架构 --------------------------
print_info "正在检测系统架构..."
ARCH=$(uname -m)
print_info "当前架构: $ARCH"

if [[ "$ARCH" == "x86_64" ]]; then
    MINICONDA_URL="https://repo.anaconda.com/miniconda/Miniconda3-latest-Linux-x86_64.sh"
elif [[ "$ARCH" == "aarch64" ]]; then
    MINICONDA_URL="https://repo.anaconda.com/miniconda/Miniconda3-latest-Linux-aarch64.sh"
else
    print_error "不支持的架构: $ARCH（仅支持 x86_64 和 aarch64）"
    exit 1
fi

# -------------------------- 3. 安装Miniconda --------------------------
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

# -------------------------- 4. 加载Conda环境 --------------------------
print_info "正在加载 Conda 环境..."
source "$MINICONDA_PATH/etc/profile.d/conda.sh"

# -------------------------- 5. 创建虚拟环境 --------------------------
ENV_NAME="pyside6_env"
PYTHON_VERSION="3.12"

if conda env list | grep -q "^$ENV_NAME "; then
    print_warn "虚拟环境 $ENV_NAME 已存在，跳过创建"
else
    print_info "正在创建虚拟环境 $ENV_NAME (Python $PYTHON_VERSION)..."
    conda create -n "$ENV_NAME" python="$PYTHON_VERSION" -y
fi

# -------------------------- 6. 激活虚拟环境并安装核心包 --------------------------
print_info "正在激活虚拟环境..."
conda activate "$ENV_NAME"

print_info "正在安装最新版 PySide6..."
conda install -c conda-forge pyside6 -y

# -------------------------- 7. 安装项目依赖（用 pip 安装，版本更灵活） --------------------------
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

# -------------------------- 8. 验证所有安装 --------------------------
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

# -------------------------- 9. 完成提示 --------------------------
echo ""
print_info "============================================="
print_info "  🎉 环境配置全部完成！"
print_info "  - Miniconda 路径: $MINICONDA_PATH"
print_info "  - 虚拟环境名: $ENV_NAME"
print_info "  - 已安装: PySide6 + 所有项目依赖"
print_info ""
print_info "  下次使用前请先运行: conda activate $ENV_NAME"
print_info "============================================="
