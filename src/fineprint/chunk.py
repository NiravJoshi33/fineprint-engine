from fineprint.convert import get_or_create_markdown

md_text = get_or_create_markdown(raw_file="raw/niva_reassure2.pdf", markdown_file="data/niva_reassure2.md")
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

max_len = 0
largest_chunk = ""
for chunk in chunks:
    if len(chunk) > max_len:
        largest_chunk = chunk
        max_len = len(chunk)

print(largest_chunk)
print(len(largest_chunk))


