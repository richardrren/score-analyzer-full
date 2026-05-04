# 统信UOS兼容性问题修复记录

## 问题一：ARM架构导致Node.js可执行文件格式错误

### 错误信息
```
PDF parsing error: [Errno 8] 可执行文件格式错误: '/data/home/user/score-analyzer-full/node/node-v20.10.0-linux-x64/bin/node'
```

### 问题原因
程序下载的是 x64 架构的 Node.js，但用户的统信UOS运行在 ARM64 架构上，导致可执行文件格式不兼容。

### 修复方案

**1. 修改 `node/setup_node_linux.sh`**

添加架构自动检测逻辑，根据 `uname -m` 的返回值判断系统架构：
- `aarch64` 或 `arm64` → 下载 `node-v20.10.0-linux-arm64`
- `x86_64` → 下载 `node-v20.10.0-linux-x64`

```bash
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
    exit 1
fi
```

**2. 修改 `app/pdf_parser.py`**

在 `get_local_node_path()` 函数中添加架构检测逻辑，根据 `platform.machine()` 返回值选择正确的 Node.js 目录：

```python
system = platform.system()
machine = platform.machine().lower()
if system == "Windows":
    node_dir = os.path.join(base_dir, "node", "node-v20.10.0-win-x64")
elif system == "Linux":
    if machine in ("aarch64", "arm64"):
        node_dir = os.path.join(base_dir, "node", "node-v20.10.0-linux-arm64")
    else:
        node_dir = os.path.join(base_dir, "node", "node-v20.10.0-linux-x64")
else:
    node_dir = os.path.join(base_dir, "node", "node-v20.10.0-linux-x64")
```

### 修复后操作
用户在统信UOS上需要重新运行配置脚本：
```bash
cd ~/score-analyzer-full/node
rm -rf node-v20.10.0-linux-x64  # 删除旧版本
./setup_node_linux.sh  # 自动下载正确架构版本
```

---

## 问题二：TTC字体文件导致报告生成失败

### 错误信息
```
报告生成失败：TTC file "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc": postscript outlines are not supported
报告生成失败：TTC file "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc": postscript outlines are not supported
```

### 问题原因
`reportlab` 库的 `TTFont` 无法正确处理 TTC（TrueType Collection）字体文件。TTC 是多个 TrueType 字体打包在一起的格式，reportlab 不支持这种格式的"postscript outlines"特性。

原代码尝试加载系统中的 NotoSansCJK-Regular.ttc 字体文件，但在解析时失败。

### 修复方案

修改 `app/pdf_service.py`，移除直接加载系统 TTC 字体的逻辑，改为使用 reportlab 内置的 CID 中文字体：

```python
FONT_NAME = "STSong-Light"
FONT_FALLBACKS = {
    "Windows": "STSong-Light",
    "Linux": "STSong-Light",  # 改为使用内置字体
    "Darwin": "STSong-Light",
}

def _register_font() -> None:
    try:
        pdfmetrics.getFont(FONT_NAME)
    except KeyError:
        system = platform.system()
        font_name = FONT_FALLBACKS.get(system, "STSong-Light")
        if system == "Linux":
            # 在Linux上直接使用reportlab内置的CID字体，避免TTC字体兼容性问题
            try:
                pdfmetrics.registerFont(UnicodeCIDFont(font_name))
            except Exception:
                # 如果STSong不可用，尝试其他内置字体
                for fallback_font in ["MSung-Light", "STHeiti-Light", "STKaiti-Light"]:
                    try:
                        pdfmetrics.registerFont(UnicodeCIDFont(fallback_font))
                        break
                    except Exception:
                        continue
        else:
            pdfmetrics.registerFont(UnicodeCIDFont(font_name))
```

### 修复后操作
用户在统信UOS上更新代码后重新运行即可：
```bash
cd ~/score-analyzer-full
git pull
```

---

## 技术总结

| 问题 | 根因 | 解决方案 |
|------|------|----------|
| Node.js可执行文件格式错误 | 下载了错误架构的Node.js | 自动检测系统架构，下载对应版本 |
| TTC字体文件不支持 | reportlab不支持TTC格式的postscript outlines | 使用reportlab内置CID字体代替系统字体 |

### 统信UOS开发注意事项

1. **跨架构兼容**：Linux系统不等于x86_64，ARM架构设备需要使用对应的二进制文件
2. **字体处理**：reportlab处理中文字体时，优先使用内置CID字体，避免依赖系统字体文件
3. **字体格式**：TTC、OTF等复合字体格式可能在reportlab中不被支持，需谨慎使用
