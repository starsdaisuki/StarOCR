# ⭐ StarOCR

扫描件 / 图片 / 文档 → Markdown，基于 Mistral OCR API。

**支持格式**:
- **PDF** (`.pdf`) —— 小于 50MB 直接传，大于 50MB 自动分段
- **图片** (`.png` `.jpg` `.jpeg` `.webp` `.avif` `.gif` `.bmp` `.tiff`) —— base64 直传，不走上传流程
- **文档** (`.docx` `.pptx`) —— Mistral OCR 原生支持，无需转换

## 前置要求

- [uv](https://docs.astral.sh/uv/getting-started/installation/)（不需要 pip install 任何东西，uv 会自动处理依赖）
- Mistral API Key（[去这里创建](https://console.mistral.ai)，价格 $1/1000页）

## 部署（新设备只做一次）

### macOS / Linux

```bash
# 1. 克隆到本地
gh repo clone starsdaisuki/StarOCR ~/StarTools/StarOCR

# 2. 设置 API Key（加到 ~/.zshrc 末尾）
echo "export MISTRAL_API_KEY='你的密钥'" >> ~/.zshrc
source ~/.zshrc

# 3. 加 alias（加到 ~/.zshrc 末尾）
echo "alias ocr='uv run ~/StarTools/StarOCR/ocr.py'" >> ~/.zshrc
source ~/.zshrc
```

### Windows

```powershell
# 1. 克隆到本地
gh repo clone starsdaisuki/StarOCR $HOME\StarTools\StarOCR

# 2. 设置 API Key（永久环境变量）
[Environment]::SetEnvironmentVariable("MISTRAL_API_KEY", "你的密钥", "User")

# 3. 加快捷命令（在 PowerShell 配置文件中添加函数）
#    先确保配置文件存在
if (!(Test-Path $PROFILE)) { New-Item $PROFILE -Force }
#    写入函数
Add-Content $PROFILE 'function ocr { uv run "$HOME\StarTools\StarOCR\ocr.py" @args }'
#    重新加载
. $PROFILE
```

> **Windows 提示**: 设置环境变量后需要重启终端才能生效。

## 使用

部署完成后，macOS / Linux / Windows 用法完全一样：

```bash
# 交互模式：一步步引导你选文件
ocr

# 直接跑：输出同目录同名 .md
ocr 文件.pdf
ocr 照片.png
ocr 幻灯片.pptx
ocr 简历.docx

# 指定输出路径
ocr 文件.pdf -o 输出.md

# 超大 PDF 调整每段页数（默认 100，仅 PDF 生效）
ocr 大文件.pdf --chunk 80
```

## 交互模式演示

```
⭐ StarOCR 交互模式
────────────────────────────────────

📁 文件在哪个文件夹？（支持 PDF / 图片 / DOCX / PPTX）
   直接回车 = 当前目录（/Users/stars/Documents）
   路径:

📋 找到 5 个文件（2 PDF · 2 图片 · 1 文档）:
   1. 📄 数据挖掘.pdf（148.2 MB）
   2. 📄 机器学习.pdf（32.1 MB）
   3. 🖼️ 板书.png（3.2 MB）
   4. 🖼️ 板书2.jpg（2.8 MB）
   5. 📊 期末汇报.pptx（5.1 MB）

🔢 要转哪些？（直接回车 = 全部）
   支持: 1 3 5  /  1-3  /  all  /  按类型筛选: pdf  image  doc
   选择: image

📝 Markdown 输出到哪？
   直接回车 = 和源文件同目录
   路径:

🚀 开始处理 2 个文件...
```

**选择语法**:
- `1 3 5` —— 挑第 1、3、5 个
- `1-3` —— 第 1 到第 3
- `all` / 直接回车 —— 全部
- `pdf` / `image`（或 `图片`）/ `doc`（或 `文档`）—— 按类型筛选

## 费用参考

| 页数 | 实时价格 | Batch 价格 |
|------|---------|-----------|
| 100 页 | $0.20 | $0.10 |
| 500 页 | $1.00 | $0.50 |
| 1000 页 | $2.00 | $1.00 |
