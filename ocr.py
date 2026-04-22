# /// script
# requires-python = ">=3.10"
# dependencies = [
#     "mistralai>=1.0,<2",
#     "pymupdf",
# ]
# ///

"""
StarOCR - 扫描件转 Markdown 工具 ⭐
使用 Mistral OCR API 将 PDF / 图片 / 文档转为 Markdown

支持格式:
    PDF:  .pdf
    图片: .png .jpg .jpeg .webp .avif .gif .bmp .tiff
    文档: .docx .pptx

两种用法:
    uv run ocr.py                        → 交互模式，一步步引导你
    uv run ocr.py 文件.pdf               → 直接跑，输出同目录同名 .md
    uv run ocr.py 图片.png -o 输出.md    → 直接跑，指定输出路径

搭配 alias 更方便（加到 ~/.zshrc）:
    alias ocr='uv run ~/StarTools/StarOCR/ocr.py'
    然后只需: ocr 文件.pdf  或  ocr 图片.png

环境变量:
    MISTRAL_API_KEY - Mistral API 密钥（必须设置）
"""

import sys
import os
import argparse
import base64
import tempfile
from pathlib import Path


# ──────────────────── 文件类型定义 ────────────────────

PDF_EXTS = {".pdf"}
IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".webp", ".avif", ".gif", ".bmp", ".tiff", ".tif"}
DOC_EXTS = {".docx", ".pptx"}
ALL_EXTS = PDF_EXTS | IMAGE_EXTS | DOC_EXTS

MIME_TYPES = {
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".webp": "image/webp",
    ".avif": "image/avif",
    ".gif": "image/gif",
    ".bmp": "image/bmp",
    ".tiff": "image/tiff",
    ".tif": "image/tiff",
}

TYPE_ICON = {
    ".pdf": "📄",
    ".docx": "📝",
    ".pptx": "📊",
}
# 图片统一用 🖼
for _ext in IMAGE_EXTS:
    TYPE_ICON[_ext] = "🖼️"


def get_file_kind(path: str) -> str:
    """返回 'pdf' / 'image' / 'doc' / 'unknown'"""
    ext = Path(path).suffix.lower()
    if ext in PDF_EXTS:
        return "pdf"
    if ext in IMAGE_EXTS:
        return "image"
    if ext in DOC_EXTS:
        return "doc"
    return "unknown"


# ──────────────────── 工具函数 ────────────────────

def get_client():
    """初始化 Mistral 客户端，没有 API Key 就提示怎么设置"""
    from mistralai import Mistral

    api_key = os.environ.get("MISTRAL_API_KEY")
    if not api_key:
        print("❌ 未设置 MISTRAL_API_KEY 环境变量")
        print()
        print("   三步搞定:")
        print("   1. 去 https://console.mistral.ai 创建 API Key")
        print("   2. 在 ~/.zshrc 末尾加一行:")
        print("      export MISTRAL_API_KEY='你的密钥'")
        print("   3. 运行 source ~/.zshrc 然后重新执行本脚本")
        sys.exit(1)
    return Mistral(api_key=api_key)


def find_inputs(directory: str) -> list[str]:
    """找出目录下所有支持的输入文件（扩展名大小写不敏感）"""
    try:
        entries = os.listdir(directory)
    except OSError:
        return []
    result = []
    for name in entries:
        path = os.path.join(directory, name)
        if os.path.isfile(path) and Path(name).suffix.lower() in ALL_EXTS:
            result.append(path)
    return sorted(result)


# ──────────────────── OCR 核心逻辑 ────────────────────

def ocr_image(client, path: str) -> str:
    """图片 OCR：base64 编码后用 image_url 直接识别（不走上传流程）"""
    ext = Path(path).suffix.lower()
    mime = MIME_TYPES.get(ext, "image/png")

    print(f"  📤 编码图片: {Path(path).name}")
    with open(path, "rb") as f:
        data = base64.b64encode(f.read()).decode("ascii")

    print(f"  🔍 OCR 识别中...")
    result = client.ocr.process(
        model="mistral-ocr-latest",
        document={"type": "image_url", "image_url": f"data:{mime};base64,{data}"},
    )

    return "\n\n".join(page.markdown for page in result.pages)


def ocr_via_upload(client, path: str) -> str:
    """PDF / DOCX / PPTX OCR：上传 → 签名 URL → 识别"""
    name = Path(path).name
    print(f"  📤 上传: {name}")

    with open(path, "rb") as f:
        uploaded = client.files.upload(
            file={"file_name": name, "content": f.read()},
            purpose="ocr",
        )

    print(f"  🔗 获取签名 URL...")
    signed = client.files.get_signed_url(file_id=uploaded.id, expiry=1)

    print(f"  🔍 OCR 识别中...")
    result = client.ocr.process(
        model="mistral-ocr-latest",
        document={"type": "document_url", "document_url": signed.url},
    )

    return "\n\n".join(page.markdown for page in result.pages)


def ocr_large_pdf(client, pdf_path: str, chunk_size: int = 100) -> str:
    """处理大 PDF（>= 50MB），自动拆分后逐段处理（仅 PDF 支持拆分）"""
    import fitz  # pymupdf

    doc = fitz.open(pdf_path)
    total_pages = len(doc)
    total_chunks = (total_pages + chunk_size - 1) // chunk_size
    print(f"  📖 共 {total_pages} 页，拆成 {total_chunks} 段（每段 {chunk_size} 页）")

    all_md = []

    for start in range(0, total_pages, chunk_size):
        end = min(start + chunk_size, total_pages)
        chunk_num = start // chunk_size + 1

        print(f"\n  ── 第 {chunk_num}/{total_chunks} 段（第 {start+1}-{end} 页）──")

        chunk_doc = fitz.open()
        chunk_doc.insert_pdf(doc, from_page=start, to_page=end - 1)

        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
            chunk_path = tmp.name
            chunk_doc.save(chunk_path)
        chunk_doc.close()

        try:
            md = ocr_via_upload(client, chunk_path)
            all_md.append(md)
        finally:
            os.unlink(chunk_path)

    doc.close()
    return "\n\n".join(all_md)


# ──────────────────── 单个文件处理流程 ────────────────────

def process_one(client, path: str, output_path: str, chunk_size: int = 100):
    """处理一个文件的完整流程（按后缀分发到对应 OCR 路径）"""
    ext = Path(path).suffix.lower()
    kind = get_file_kind(path)
    size_mb = os.path.getsize(path) / (1024 * 1024)
    icon = TYPE_ICON.get(ext, "📄")
    print(f"\n{icon} {Path(path).name}（{size_mb:.1f} MB）")

    if kind == "pdf":
        if size_mb >= 50:
            print(f"  ⚠️ 超过 50MB，启用分段模式")
            markdown = ocr_large_pdf(client, path, chunk_size=chunk_size)
        else:
            markdown = ocr_via_upload(client, path)
    elif kind == "image":
        if size_mb >= 40:
            print(f"  ⚠️ 图片较大，base64 编码后可能超过 API 限制")
        markdown = ocr_image(client, path)
    elif kind == "doc":
        if size_mb >= 50:
            print(f"  ⚠️ 文档超过 50MB，且无法分段，可能失败")
        markdown = ocr_via_upload(client, path)
    else:
        print(f"  ❌ 不支持的格式: {ext}")
        return

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(markdown)

    lines = markdown.count("\n") + 1
    size_kb = len(markdown.encode("utf-8")) / 1024
    print(f"  ✅ 完成! {lines} 行, {size_kb:.0f} KB → {output_path}")


# ──────────────────── 交互模式 ────────────────────

def interactive_mode():
    """没给参数时进入的引导模式"""
    print("⭐ StarOCR 交互模式")
    print("─" * 40)

    # 第一步：问文件在哪
    print()
    print("📁 文件在哪个文件夹？（支持 PDF / 图片 / DOCX / PPTX）")
    print(f"   直接回车 = 当前目录（{os.getcwd()}）")
    folder = input("   路径: ").strip()

    if not folder:
        folder = os.getcwd()
    folder = os.path.expanduser(folder)

    if not os.path.isdir(folder):
        # 也许用户直接输了单个文件路径
        if os.path.isfile(folder) and Path(folder).suffix.lower() in ALL_EXTS:
            return interactive_single_file(folder)
        print(f"❌ 目录不存在: {folder}")
        sys.exit(1)

    # 扫描支持的文件
    files = find_inputs(folder)
    if not files:
        print(f"❌ {folder} 下没有支持的文件")
        print(f"   支持: {', '.join(sorted(ALL_EXTS))}")
        sys.exit(1)

    # 按类型统计
    counts = {"pdf": 0, "image": 0, "doc": 0}
    for f in files:
        counts[get_file_kind(f)] += 1
    summary = []
    if counts["pdf"]:
        summary.append(f"{counts['pdf']} PDF")
    if counts["image"]:
        summary.append(f"{counts['image']} 图片")
    if counts["doc"]:
        summary.append(f"{counts['doc']} 文档")

    # 列出找到的文件
    print(f"\n📋 找到 {len(files)} 个文件（{' · '.join(summary)}）:")
    for i, p in enumerate(files, 1):
        ext = Path(p).suffix.lower()
        icon = TYPE_ICON.get(ext, "📄")
        size_mb = os.path.getsize(p) / (1024 * 1024)
        print(f"   {i}. {icon} {Path(p).name}（{size_mb:.1f} MB）")

    # 第二步：选文件
    print()
    print("🔢 要转哪些？（直接回车 = 全部）")
    print("   支持: 1 3 5  /  1-3  /  all  /  按类型筛选: pdf  image  doc")
    choice = input("   选择: ").strip().lower()

    if not choice or choice == "all":
        selected = files
    elif choice in ("pdf", "image", "img", "图片", "doc", "文档"):
        # 类型别名 → 内部 kind
        kind_map = {"img": "image", "图片": "image", "文档": "doc"}
        target_kind = kind_map.get(choice, choice)
        selected = [f for f in files if get_file_kind(f) == target_kind]
        if not selected:
            print(f"❌ 没有 {choice} 类型的文件")
            sys.exit(1)
    else:
        selected = parse_selection(choice, files)
        if not selected:
            print("❌ 无效选择")
            sys.exit(1)

    # 第三步：输出位置
    print()
    print("📝 Markdown 输出到哪？")
    print(f"   直接回车 = 和源文件同目录")
    out_dir = input("   路径: ").strip()

    if not out_dir:
        out_dir = None
    else:
        out_dir = os.path.expanduser(out_dir)
        os.makedirs(out_dir, exist_ok=True)

    # 开跑
    print()
    print(f"🚀 开始处理 {len(selected)} 个文件...")
    client = get_client()

    for path in selected:
        if out_dir:
            output_path = os.path.join(out_dir, Path(path).stem + ".md")
        else:
            output_path = str(Path(path).with_suffix(".md"))
        process_one(client, path, output_path)

    print(f"\n🎉 全部完成！共处理 {len(selected)} 个文件")


def interactive_single_file(path: str):
    """用户在交互模式直接输了一个文件路径"""
    ext = Path(path).suffix.lower()
    icon = TYPE_ICON.get(ext, "📄")
    print(f"\n{icon} 选中: {Path(path).name}")

    print()
    print("📝 Markdown 输出到哪？")
    default_out = str(Path(path).with_suffix(".md"))
    print(f"   直接回车 = {default_out}")
    out = input("   路径: ").strip()

    output_path = out if out else default_out

    print()
    client = get_client()
    process_one(client, path, output_path)
    print(f"\n🎉 完成!")


def parse_selection(choice: str, items: list[str]) -> list[str]:
    """解析用户的选择输入，支持 '1 3 5' 和 '1-3' 格式"""
    selected = []
    parts = choice.replace(",", " ").split()

    for part in parts:
        if "-" in part:
            try:
                start, end = part.split("-", 1)
                for i in range(int(start), int(end) + 1):
                    if 1 <= i <= len(items):
                        selected.append(items[i - 1])
            except ValueError:
                continue
        else:
            try:
                idx = int(part)
                if 1 <= idx <= len(items):
                    selected.append(items[idx - 1])
            except ValueError:
                continue

    return selected


# ──────────────────── 入口 ────────────────────

def main():
    # 没有任何参数 → 交互模式
    if len(sys.argv) == 1:
        interactive_mode()
        return

    # 有参数 → 命令行模式
    parser = argparse.ArgumentParser(
        description="⭐ StarOCR - PDF / 图片 / 文档 转 Markdown（Mistral OCR）",
    )
    parser.add_argument(
        "file",
        help=f"源文件路径（支持: {', '.join(sorted(ALL_EXTS))}）",
    )
    parser.add_argument("-o", "--output", help="输出路径（默认: 同名 .md）")
    parser.add_argument("--chunk", type=int, default=100, help="大 PDF 每段页数（默认 100，仅 PDF 生效）")
    args = parser.parse_args()

    path = args.file
    if not os.path.exists(path):
        print(f"❌ 文件不存在: {path}")
        sys.exit(1)

    ext = Path(path).suffix.lower()
    if ext not in ALL_EXTS:
        print(f"❌ 不支持的格式: {ext}")
        print(f"   支持的格式: {', '.join(sorted(ALL_EXTS))}")
        sys.exit(1)

    output_path = args.output or str(Path(path).with_suffix(".md"))

    client = get_client()
    process_one(client, path, output_path, chunk_size=args.chunk)


if __name__ == "__main__":
    main()
