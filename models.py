from pydantic import BaseModel, Field

class GenSQLQuery(BaseModel):
    sql_query: str = Field(..., description="Generated SQL query")    
    user_query_risk_level: str = Field(..., description="User query risk level")
    query_results_columns: list = Field(description="Table columns (list of str) corresponding to the query results, eg: ['Date', 'Name', 'Category_of_Guest', 'Message_from_Guest']")
    response_introduction: str = Field(..., description="More formal introduction to the final result of the query to the user. Eg: 'Here are the results of your...:' (The number of results must not be mentioned unless ot is explicitly asked in the user input)")
    
