from fineprint.convert import get_or_create_markdown

def split_on_headings(md_text: str) -> list[str]:
    lines = md_text.splitlines()

    chunks = []
    new_chunk = ""
    for line in lines:
        if not line.startswith("#"):
            new_chunk = new_chunk +( "\n" if new_chunk != "" else "") + line
        else:
            if new_chunk != "":
                chunks.append(new_chunk)
            
            new_chunk = line

    if new_chunk != "":
        chunks.append(new_chunk)

    return chunks
   



