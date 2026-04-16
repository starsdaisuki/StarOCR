# CLAUDE.md - StarOCR 项目指南

## 项目概览

StarOCR 是一个单文件 CLI 工具，使用 Mistral OCR API 将 PDF（含扫描件）转换为 Markdown。
整个项目只有一个核心文件 `ocr.py`，通过 [PEP 723](https://peps.python.org/pep-0723/) inline script metadata 声明依赖，由 `uv run` 自动管理虚拟环境，无需手动安装任何包。

## 技术栈

- **运行时**: Python >= 3.10，通过 `uv run` 执行（用户无需 pip install）
- **OCR 引擎**: Mistral OCR API (`mistral-ocr-latest` 模型)
- **PDF 处理**: PyMuPDF (`fitz`) —— 仅在大文件分段时使用
- **客户端库**: `mistralai` v1.x（**必须 <2，见下方已知问题**）

## 项目结构

```
StarOCR/
├── ocr.py          # 唯一的源码文件，包含全部逻辑
├── README.md       # 用户文档（部署、使用、费用）
└── CLAUDE.md       # 本文件
```

## 运行方式

用户通过 `~/.zshrc` 中的 alias 调用：
```bash
alias ocr='uv run ~/StarTools/StarOCR/ocr.py'
```

两种模式：
- **交互模式** (`ocr`)：引导用户选择文件夹、PDF 文件、输出路径
- **命令行模式** (`ocr file.pdf [-o output.md] [--chunk N]`)：直接处理

## 核心流程

1. 上传 PDF 到 Mistral Files API (`client.files.upload`, purpose="ocr")
2. 获取签名 URL (`client.files.get_signed_url`)
3. 调用 OCR (`client.ocr.process`, model="mistral-ocr-latest")
4. 拼接各页 Markdown 输出

大文件 (>=50MB) 会通过 PyMuPDF 自动拆分为多段（默认每段 100 页），逐段上传处理后合并。

## 环境变量

- `MISTRAL_API_KEY` —— 必须设置，否则脚本会打印提示并退出

## 已知问题与经验

### mistralai v2 不兼容（2026-04 发现）

`mistralai` 2.x 将 `Mistral` 类从包顶层 (`mistralai.Mistral`) 移到了 `mistralai.client.Mistral`，导致 `from mistralai import Mistral` 报 ImportError。

**解决方案**: 在 inline metadata 中将依赖固定为 `"mistralai>=1.0,<2"`。如果未来需要升级到 v2，需要将导入改为 `from mistralai.client import Mistral` 并验证 Files API 和 OCR API 的调用方式是否有变化。

### uv 缓存问题

当依赖版本约束变更后，uv 可能仍使用缓存的旧版本环境。如遇依赖不符预期，运行：
```bash
uv cache clean mistralai
```

## 编码规范

- 单文件项目，不要拆分模块
- 用户界面用中文，代码注释用中文
- emoji 用于 CLI 输出的视觉提示（📁 🔢 📝 🚀 ✅ ❌ 等）
- 依赖通过 PEP 723 inline metadata 声明，不使用 requirements.txt 或 pyproject.toml

## 修改注意事项

- 修改依赖版本后记得测试 `uv run ocr.py --help` 确认环境正常
- Mistral API 有 50MB 上传限制，大文件分段逻辑不可删除
- 交互模式的输入解析支持 `1 3 5`、`1-3`、`all` 格式，改动时注意向后兼容
