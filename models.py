from pydantic import BaseModel, Field

class GenSQLQuery(BaseModel):
    sql_query: str = Field(description="Generated SQL query")
    query_results_columns: list = Field(description="Table columns corresponding to the query results")
    response_introduction: str = Field(description="Introduction to the answer of the initial user question.")
    
