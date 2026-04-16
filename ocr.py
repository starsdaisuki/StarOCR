# /// script
# requires-python = ">=3.10"
# dependencies = [
#     "mistralai>=1.0,<2",
#     "pymupdf",
# ]
# ///

"""
StarOCR - PDF 转 Markdown 工具 ⭐
使用 Mistral OCR API 将扫描版 PDF 转为 Markdown

两种用法:
    uv run ocr.py                        → 交互模式，一步步引导你
    uv run ocr.py 文件.pdf               → 直接跑，输出同目录同名 .md
    uv run ocr.py 文件.pdf -o 输出.md    → 直接跑，指定输出路径

搭配 alias 更方便（加到 ~/.zshrc）:
    alias ocr='uv run ~/StarTools/ocr.py'
    然后只需: ocr 文件.pdf

环境变量:
    MISTRAL_API_KEY - Mistral API 密钥（必须设置）
"""

import sys
import os
import argparse
import tempfile
import glob
from pathlib import Path


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


def find_pdfs(directory: str) -> list[str]:
    """找出目录下所有 PDF 文件"""
    pattern = os.path.join(directory, "*.pdf")
    return sorted(glob.glob(pattern))


# ──────────────────── OCR 核心逻辑 ────────────────────

def ocr_single_pdf(client, pdf_path: str) -> str:
    """处理单个 PDF 文件（< 50MB），返回 Markdown 文本"""
    name = Path(pdf_path).name
    print(f"  📤 上传: {name}")

    with open(pdf_path, "rb") as f:
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

    md_parts = [page.markdown for page in result.pages]
    return "\n\n".join(md_parts)


def ocr_large_pdf(client, pdf_path: str, chunk_size: int = 100) -> str:
    """处理大 PDF（>= 50MB），自动拆分后逐段处理"""
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

        # 拆出这一段
        chunk_doc = fitz.open()
        chunk_doc.insert_pdf(doc, from_page=start, to_page=end - 1)

        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
            chunk_path = tmp.name
            chunk_doc.save(chunk_path)
        chunk_doc.close()

        try:
            md = ocr_single_pdf(client, chunk_path)
            all_md.append(md)
        finally:
            os.unlink(chunk_path)

    doc.close()
    return "\n\n".join(all_md)


# ──────────────────── 单个文件处理流程 ────────────────────

def process_one(client, pdf_path: str, output_path: str, chunk_size: int = 100):
    """处理一个 PDF 文件的完整流程"""
    file_size_mb = os.path.getsize(pdf_path) / (1024 * 1024)
    print(f"\n📄 {Path(pdf_path).name}（{file_size_mb:.1f} MB）")

    if file_size_mb >= 50:
        print(f"  ⚠️ 超过 50MB，启用分段模式")
        markdown = ocr_large_pdf(client, pdf_path, chunk_size=chunk_size)
    else:
        markdown = ocr_single_pdf(client, pdf_path)

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

    # 第一步：问 PDF 在哪
    print()
    print("📁 PDF 文件在哪个文件夹？")
    print(f"   直接回车 = 当前目录（{os.getcwd()}）")
    folder = input("   路径: ").strip()

    if not folder:
        folder = os.getcwd()
    folder = os.path.expanduser(folder)  # 展开 ~ 符号

    if not os.path.isdir(folder):
        # 也许用户直接输了单个文件路径
        if os.path.isfile(folder) and folder.lower().endswith(".pdf"):
            return interactive_single_file(folder)
        print(f"❌ 目录不存在: {folder}")
        sys.exit(1)

    # 找 PDF
    pdfs = find_pdfs(folder)
    if not pdfs:
        print(f"❌ {folder} 下没有 PDF 文件")
        sys.exit(1)

    # 列出找到的 PDF
    print(f"\n📋 找到 {len(pdfs)} 个 PDF:")
    for i, p in enumerate(pdfs, 1):
        size_mb = os.path.getsize(p) / (1024 * 1024)
        print(f"   {i}. {Path(p).name}（{size_mb:.1f} MB）")

    # 第二步：选文件
    print()
    print("🔢 要转哪些？（直接回车 = 全部）")
    print("   示例: 1 3 5  或  1-3  或  all")
    choice = input("   选择: ").strip().lower()

    if not choice or choice == "all":
        selected = pdfs
    else:
        selected = parse_selection(choice, pdfs)
        if not selected:
            print("❌ 无效选择")
            sys.exit(1)

    # 第三步：输出位置
    print()
    print("📝 Markdown 输出到哪？")
    print(f"   直接回车 = 和 PDF 同目录")
    out_dir = input("   路径: ").strip()

    if not out_dir:
        out_dir = None  # 后面会用 PDF 所在目录
    else:
        out_dir = os.path.expanduser(out_dir)
        os.makedirs(out_dir, exist_ok=True)

    # 开跑
    print()
    print(f"🚀 开始处理 {len(selected)} 个文件...")
    client = get_client()

    for pdf_path in selected:
        if out_dir:
            output_path = os.path.join(out_dir, Path(pdf_path).stem + ".md")
        else:
            output_path = str(Path(pdf_path).with_suffix(".md"))
        process_one(client, pdf_path, output_path)

    print(f"\n🎉 全部完成！共处理 {len(selected)} 个文件")


def interactive_single_file(pdf_path: str):
    """用户在交互模式直接输了一个文件路径"""
    print(f"\n📄 选中: {Path(pdf_path).name}")

    print()
    print("📝 Markdown 输出到哪？")
    default_out = str(Path(pdf_path).with_suffix(".md"))
    print(f"   直接回车 = {default_out}")
    out = input("   路径: ").strip()

    output_path = out if out else default_out

    print()
    client = get_client()
    process_one(client, pdf_path, output_path)
    print(f"\n🎉 完成!")


def parse_selection(choice: str, pdfs: list[str]) -> list[str]:
    """解析用户的选择输入，支持 '1 3 5' 和 '1-3' 格式"""
    selected = []
    parts = choice.replace(",", " ").split()

    for part in parts:
        if "-" in part:
            try:
                start, end = part.split("-", 1)
                for i in range(int(start), int(end) + 1):
                    if 1 <= i <= len(pdfs):
                        selected.append(pdfs[i - 1])
            except ValueError:
                continue
        else:
            try:
                idx = int(part)
                if 1 <= idx <= len(pdfs):
                    selected.append(pdfs[idx - 1])
            except ValueError:
                continue

    return selected


# ──────────────────── 入口 ────────────────────

def main():
    # 没有任何参数 → 交互模式
    if len(sys.argv) == 1:
        interactive_mode()
        return

    # 有参数 → 命令行模式（和以前一样）
    parser = argparse.ArgumentParser(
        description="⭐ StarOCR - PDF 转 Markdown（Mistral OCR）",
    )
    parser.add_argument("pdf", help="PDF 文件路径")
    parser.add_argument("-o", "--output", help="输出路径（默认: 同名 .md）")
    parser.add_argument("--chunk", type=int, default=100, help="大文件每段页数（默认: 100）")
    args = parser.parse_args()

    pdf_path = args.pdf
    if not os.path.exists(pdf_path):
        print(f"❌ 文件不存在: {pdf_path}")
        sys.exit(1)

    output_path = args.output or str(Path(pdf_path).with_suffix(".md"))

    client = get_client()
    process_one(client, pdf_path, output_path, chunk_size=args.chunk)


if __name__ == "__main__":
    main()
