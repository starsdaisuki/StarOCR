# CLAUDE.md - StarOCR 项目指南

## 项目概览

StarOCR 是一个单文件 CLI 工具，使用 Mistral OCR API 将 **PDF / 图片 / DOCX / PPTX** 转换为 Markdown。
整个项目只有一个核心文件 `ocr.py`，通过 [PEP 723](https://peps.python.org/pep-0723/) inline script metadata 声明依赖，由 `uv run` 自动管理虚拟环境，无需手动安装任何包。

## 技术栈

- **运行时**: Python >= 3.10，通过 `uv run` 执行（用户无需 pip install）
- **OCR 引擎**: Mistral OCR API (`mistral-ocr-latest` 模型)
- **PDF 处理**: PyMuPDF (`fitz`) —— 仅在大 PDF 分段时使用
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
- **交互模式** (`ocr`)：引导用户选择文件夹、文件、输出路径
- **命令行模式** (`ocr file.xxx [-o output.md] [--chunk N]`)：直接处理

## 支持的格式与分发策略

| 类型 | 扩展名 | API 路径 | 分段处理 |
|------|--------|---------|---------|
| PDF | `.pdf` | 上传 → 签名 URL → `document_url` | 是（>=50MB 自动拆） |
| 图片 | `.png` `.jpg` `.jpeg` `.webp` `.avif` `.gif` `.bmp` `.tiff` `.tif` | base64 data URL → `image_url` | 否 |
| 文档 | `.docx` `.pptx` | 上传 → 签名 URL → `document_url` | 否（无法拆分） |

**核心分发逻辑**：`process_one()` 根据后缀调用 `get_file_kind()`，再分发到 `ocr_via_upload()`（PDF/DOCX/PPTX 共用）或 `ocr_image()`（图片专用）。PDF 如果 >=50MB 会走 `ocr_large_pdf()` 拆分路径。

## 核心流程

### 上传路径（PDF / DOCX / PPTX）

1. 上传到 Mistral Files API (`client.files.upload`, purpose="ocr")
2. 获取签名 URL (`client.files.get_signed_url`)
3. 调用 OCR (`client.ocr.process`, model="mistral-ocr-latest")
4. 拼接各页 Markdown 输出

### 图片路径（PNG/JPG 等）

1. 读文件 → base64 编码
2. 构造 `data:image/png;base64,...` URL
3. 直接调 `client.ocr.process` 用 `image_url` 类型，无需上传步骤
4. 速度更快、请求更少

### 大 PDF 分段

`ocr_large_pdf()` 用 PyMuPDF 把 PDF 拆成多个 chunk_size 页的临时文件，逐个走上传路径，最后合并 Markdown。**DOCX/PPTX 无法分段**，若超过 50MB 只能给用户警告。

## 环境变量

- `MISTRAL_API_KEY` —— 必须设置，否则脚本会打印提示并退出

## 已知问题与经验

### mistralai v2 不兼容（2026-04 发现）

`mistralai` 2.x 将 `Mistral` 类从包顶层 (`mistralai.Mistral`) 移到了 `mistralai.client.Mistral`，导致 `from mistralai import Mistral` 报 ImportError。

**解决方案**: 在 inline metadata 中将依赖固定为 `"mistralai>=1.0,<2"`。如果未来升级到 v2，需要：
1. 把导入改为 `from mistralai.client import Mistral`
2. 重新验证 Files API 和 OCR API 的调用方式
3. 测试 `image_url` / `document_url` 两种调用路径

### uv 缓存问题

当依赖版本约束变更后，uv 可能仍使用缓存的旧版本环境。如遇依赖不符预期，运行：
```bash
uv cache clean mistralai
```

### 图片 base64 大小限制

图片走 base64 data URL，编码后体积约为原文件的 1.33 倍。若原图 ≥40MB，脚本会打印警告——因为编码后可能触发 Mistral API 请求体大小限制。实际测试 <10MB 的图片都没问题。

### DOCX / PPTX 无法分段

PyMuPDF 只能处理 PDF。对于超大的 DOCX/PPTX（>50MB），只能给出警告，上传可能失败。如果未来要支持，可以考虑用 `python-docx` / `python-pptx` 拆分，但不建议——这些文件很少超过 50MB，YAGNI。

## 交互模式的选择语法

用户在"要转哪些？"一步可以输入：

- 空 / `all` —— 全部
- `1 3 5` —— 挑特定序号
- `1-3` —— 范围
- `pdf` / `image`（或 `img` / `图片`）/ `doc`（或 `文档`）—— 按类型筛选

类型别名由 `kind_map` dict 映射到内部 `kind` 字符串（`pdf` / `image` / `doc`）。改动时注意向后兼容。

## 编码规范

- 单文件项目，不要拆分模块
- 用户界面用中文，代码注释用中文
- emoji 用于 CLI 输出的视觉提示：
  - 📁 文件夹 · 📋 列表 · 🔢 输入 · 📝 输出 · 🚀 开始 · ✅ 成功 · ❌ 失败 · ⚠️ 警告
  - 📄 PDF · 🖼️ 图片 · 📝 DOCX · 📊 PPTX
- 依赖通过 PEP 723 inline metadata 声明，不使用 requirements.txt 或 pyproject.toml

## 修改注意事项

- 修改依赖版本后记得测试 `uv run ocr.py --help` 确认环境正常
- Mistral API 有 50MB 上传限制，大 PDF 分段逻辑不可删除
- 新增支持的扩展名时记得同步更新：
  1. `IMAGE_EXTS` / `DOC_EXTS` / `PDF_EXTS` 集合
  2. `MIME_TYPES` dict（图片才需要）
  3. `TYPE_ICON` dict
  4. README 里的"支持格式"列表
- 交互模式的选择语法（数字/范围/类型别名）改动时注意向后兼容
- 所有 OCR 调用都用 `mistral-ocr-latest`，不要写死版本号
