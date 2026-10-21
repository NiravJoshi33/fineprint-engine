# from docling.document_converter import DocumentConverter

# converter = DocumentConverter()
# result = converter.convert(source="raw/niva_reassure2.pdf")

# with open("data/niva_reassure2.md", "w") as md_file:
#     md_file.write(result.document.export_to_markdown())

import pymupdf4llm
from pathlib import Path
import os



def get_or_create_markdown(raw_file: str, markdown_file: str) -> str:
    md_file_path = Path(markdown_file)
    if md_file_path.exists():
        with open(file=markdown_file) as md_file:
            print("returned from cache")
            return md_file.read()

    else:
        md_txt = pymupdf4llm.to_markdown(raw_file)
        print("converted")

        Path(markdown_file).write_bytes(md_txt.encode("utf-8"))

        return md_txt

