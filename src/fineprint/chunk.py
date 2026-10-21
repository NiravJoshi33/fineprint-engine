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

if __name__ == "__main__":

    md_text = get_or_create_markdown(raw_file="raw/niva_reassure2.pdf", markdown_file="data/niva_reassure2.md")
    chunks = split_on_headings(md_text)

    max_len = 0
    largest_chunk = ""
    for chunk in chunks:
        if len(chunk) > max_len:
            largest_chunk = chunk
            max_len = len(chunk)

    print(largest_chunk)
    print(len(largest_chunk))



