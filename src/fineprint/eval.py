from pydantic import BaseModel, Field

class CitedPolicyClause(BaseModel):
    uin: str = Field(description="UIN exactly as shown in the document label")
    clause_id: str | None = Field(description="Clause id exactly as shown in the document label, e.g. 6.1.10. Null if the label has none")

class LLMAnswer(BaseModel):
    answer: str
    citation: list[CitedPolicyClause] = Field(description="Every document the answer relies on. Empty when documents_answer_query is false")
    documents_answer_query: bool = Field(description="True only if the documents contain the answer. False when they don't mention it")


