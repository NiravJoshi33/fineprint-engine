import json


def load_json_file(file: str) -> list[dict]:

    try:
        with open(file, "r") as json_file:
            return json.load(json_file)

    except FileNotFoundError:
        raise Exception(f"File doesn't exist, Please create one at {file}")


def load_run_file(file: str) -> list[dict]:
    try:
        with open(file, "r") as jsonl_file:
            return [json.loads(l) for l in jsonl_file]

    except FileNotFoundError:
        raise Exception(f"File doesn't exist, Please create one at {file}")


def calc_hit_rate(expected: list, to_check: list) -> tuple[int, int]:
    return sum(1 for item in expected if item in to_check), len(expected)


if __name__ == "__main__":
    answer_key = load_json_file(file="evals/answer_key.json")
    questions = load_json_file(file="evals/questions.json")

    qna_map = {}
    for q in questions:
        qna_map[q["id"]] = {
            "q": q,
            "a": next((a for a in answer_key if a.get("id") == q["id"]), None),
        }

    # print(qna_map)

    run_data = load_run_file(file="data/runs/2026-10-25_baseline.jsonl")

    a_type_flag_map = {"out_of_scope": False, "answer": True, "silent": False}

    def contains_flag_for(type: str) -> bool:
        return a_type_flag_map[type]

    all_retrieved_hit_rates = []
    all_cited_hit_rates = []
    flag_correct_rate = 0
    for item in run_data:
        q_id = item["q_id"]
        key = qna_map[q_id]["a"]
        answer_type = key["type"]
        expected_clauses = key["clauses"]

        retrieved_docs = item["retrieved_docs"]
        retrieved_clause_ids = [doc["clause_id"] for doc in retrieved_docs]
        citations = item["citations"]
        cited_clause_ids = [citation["clause_id"] for citation in citations]

        answered_docs_answer_query = item["docs_answer_query"]
        expected_docs_answer_query = contains_flag_for(key["type"])

        if answered_docs_answer_query == expected_docs_answer_query:
            flag_correct_rate += 1

        print(f"Q{q_id} {answer_type}")
        print(f"expected: {expected_clauses}")

        print(f"retrieved: {retrieved_clause_ids}")
        retrieved_hits, total = calc_hit_rate(expected_clauses, retrieved_clause_ids)
        if total != 0:
            all_retrieved_hit_rates.append(retrieved_hits / total)
        print(f"retrieved hits: {retrieved_hits} / {total}")
        print(f"cited: {cited_clause_ids}")
        cited_hits, _ = calc_hit_rate(expected_clauses, cited_clause_ids)
        if total != 0:
            all_cited_hit_rates.append(cited_hits / total)
        print(f"cited hits: {cited_hits} / {total}")
        print(
            f"doc contains flag correct: expected: {expected_docs_answer_query}, got {answered_docs_answer_query}"
        )
        print("---")

    print(
        f"average retrieved hit rate: {sum(all_retrieved_hit_rates) / len(all_retrieved_hit_rates)}"
    )
    print(
        f"average cited hit rate: {sum(all_cited_hit_rates) / len(all_cited_hit_rates)}"
    )
    print(f"correct flag rate: {flag_correct_rate} / {len(run_data)}")
