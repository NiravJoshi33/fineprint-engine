import re

from fineprint.convert import get_or_create_markdown

CLAUSE_ID_PATTERN = r"^#+ ?(\**)((\d+\.)+)\s"
BULLET_ID_PATTERN = r"^\s*- ((\d+\.){2,}\d+)\.?\s"


def find_clause_id(text: str) -> str | None:
    match = re.search(CLAUSE_ID_PATTERN, text)
    if match is not None:
        return match.group(2).strip(".")
    else:
        match = re.search(BULLET_ID_PATTERN, text)
        if match is not None:
            return match.group(1).strip(".")
        else:
            return None


def extract_headings(md_text: str) -> dict:
    headings = {}
    for line in md_text.splitlines():
        match = re.search(CLAUSE_ID_PATTERN, line)

        if match is not None:
            headings[match.groups()[1].strip(".")] = (
                line[match.end() :].strip().replace("**", "")
            )

    return headings


def build_path(clause_id: str, headings: dict):
    path_els = []
    clause_id_splits = clause_id.split(".")

    for i in range(len(clause_id_splits)):
        mid_clause_id = ".".join(clause_id_splits[: i + 1])
        if mid_clause_id in headings:
            path_els.append(mid_clause_id)

    return " > ".join(f"{el} {headings[el]}" for el in path_els)


def create_new_chunk(new_chunk_text: str, policy_id: str, headings: dict) -> dict:
    clause_id = find_clause_id(new_chunk_text)

    return {
        "chunk": new_chunk_text,
        "clause_id": clause_id,
        "policy_id": policy_id,
        "path": build_path(clause_id, headings) if clause_id is not None else "",
    }


def split_on_headings(md_text: str, policy_id: str) -> list[dict]:
    lines = md_text.splitlines()

    headings = extract_headings(md_text)

    chunks = []
    new_chunk = ""
    for line in lines:
        if not line.startswith("#") and not re.search(BULLET_ID_PATTERN, line):
            new_chunk = new_chunk + ("\n" if new_chunk != "" else "") + line
        else:
            if new_chunk != "":
                chunks.append(create_new_chunk(new_chunk, policy_id, headings))

            new_chunk = line

    if new_chunk != "":
        chunks.append(create_new_chunk(new_chunk, policy_id, headings))

    return chunks


if __name__ == "__main__":
    from fineprint.chunk import split_on_headings
    from fineprint.convert import get_or_create_markdown

    md_text = get_or_create_markdown(
        raw_file="raw/niva_reassure2.pdf", markdown_file="data/niva_reassure2.md"
    )
    chunks = split_on_headings(md_text, "NBHHLIP27054V032627")

    chunks_with_clause_id = sum(1 for chunk in chunks if chunk["clause_id"] is not None)
    print(chunks_with_clause_id)
    print(len(chunks) - chunks_with_clause_id)

    # for i in range(3):
    #     print("###chunk###")
    #     print(chunks[i])

    # headings = extract_headings(md_text)
    # path = build_path("6.1.5", headings)
    # print(path)
