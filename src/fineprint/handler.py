import json
import time

_init_start = time.perf_counter()
from fineprint.run_eval import get_answer_for_query  # noqa: E402  loads models, builds indexes

print(f"timing init total: {time.perf_counter() - _init_start:.1f}s", flush=True)


def handler(event: dict, context):
    try:
        body = event["body"]

        query = (json.loads(body))["query"]

        _, _, result = get_answer_for_query(query)

        return {
            "statusCode": 200,
            "body": json.dumps(
                {
                    "answer": result.parsed.answer,
                    "citation": [
                        citation.model_dump() for citation in result.parsed.citation
                    ],
                },
            ),
        }

    except Exception as e:
        print(f"Error processing query: {str(e)}")
        raise


if __name__ == "__main__":
    event = {"body": json.dumps({"query": "What is the moratorium period?"})}
    print(handler(event, None))
