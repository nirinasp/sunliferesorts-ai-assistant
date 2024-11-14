import pyodbc

import streamlit as st

from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import JsonOutputParser
from langchain_core.runnables import RunnableBranch, RunnableLambda, RunnablePassthrough
from langchain_openai import ChatOpenAI

from models import GenSQLQuery

st.set_page_config(
    page_title="Sun Life Resorts AI Assistant",
    page_icon="👋",
)

st.write("# Welcome to Sun Life Resorts AI Assistant! 👋")


@st.cache_resource
def init_db_connection():
    return pyodbc.connect(st.secrets["ODBC_CONNECTION_STRING"])


db_connection = init_db_connection()
db_table = st.secrets["DB_TABLE"]
db_table_columns_description = """
Date: Date of the feedback (nvarchar: e.g., "01\08\2024").
Time_: Time of the feedback (nvarchar: e.g., "09:41:00").
Rm_No: client room number (nvarchar).
Name: client name who complained or made the request (nvarchar e.g., "LI").
Category_of_Guest: Guest type (nvarchar: e.g., "regular guest," "VIP"), if specified.
Booked_Via_: Booking source (nvarchar)"
Nationality: Guest’s nationality, noted by country codes (e.g., "AE" for United Arab Emirates).
Meal_Plan: Meal plan type (nvarchar e.g., "HB" for Half Board).
Message_from_Guest: Complain or demand provided by the guest (nvarchar).
Complaint_or_Request: Type of feedback—either "Complaint" or "Request."
Category_of_Complaint_Request: General category of the complaint/request (nvarchar: e.g., "Restaurant_Service", "Noise_Disturbances", "Room_Maintenance", "Room_Experience", "Security", "Food_Safety", "Minibar_facilities").
Sub_Category_of_Complaint_Request: Specific complaint/request topic (nvarchar: e.g., "Reservation Issues", "General Noise", "Leakage Issues", "Not satisfied with view", "Shower issues", "Room not as per booking", "Mattress Issues", "Items lost outside BU", "Allergies", "Minibar not refilled").
Remarks: Additional remarks or notes (nvarchar e.g., "IN STAY SURVEY").
Recorded_by: Name of the staff member who recorded the feedback (nvarchar: e.g., "SELVINA").
Communicated_to: Department or individual to whom the feedback was communicated (nvarchar e.g., "Food and Beverage").
Owner: Responsible person or department, if applicable (nvarchar).
Action_Taken: Description of any actions taken by the hotel staff to fulfill the client demand (nvarchar).
Action_Taken_By: Person or department who took the action (nvarchar).
Date_: Completion date , if feedback was resolved (nvarchar).
Time_Completed: Time of completion, if feedback was resolved (nvarchar).
Follow_up_Feedback_: Follow-up response from the guest, if applicable (nvarchar).
Courtesy_call__Yes_No_: Whether a courtesy call was made (nvarchar: Yes/No).
Status__Open_Closed_: Current status of the feedback (nvarchar: Open/Closed).
Remarks_: Additional remarks or notes (nvarchar: rarely used).
_Cost_of_service_recovery_: Any cost incurred for service recovery (nvarchar).
Complaint_score: Score given to the complaint, ranging from 1 to 5 (tinyint).
Material: (nvarchar)
"""

llm = ChatOpenAI(
    model='gpt-4',
    temperature=0
)

unsupported_query_message = f"<p style='font-size: 16px; color: #d9534f;'>Unfortunately, we were unable to find any results that match your request.</p>"
malicious_query_message = f"<p style='font-size: 16px; color: #d9534f;'>Your query has been flagged as potentially harmful and has been blocked.</p>"
nonsense_query_message = f"<p style='font-size: 16px; color: #d9534f;'>Sorry, I don't understand your request.</p>"


gen_sql_query_parser = JsonOutputParser(pydantic_object=GenSQLQuery)

def retrieve_data(gen_sql_query: dict):
    print("generated sql query: ", gen_sql_query)

    columns = gen_sql_query['query_results_columns']

    with db_connection:
        db_cursor = db_connection.cursor()

        db_cursor.execute(gen_sql_query['sql_query'])

        query_results = db_cursor.fetchall()

        results = []

        if len(columns) > 1:
            results = [dict(zip(columns, record)) for record in query_results]
        elif len(columns) == 1:
            results = [record[0] for record in query_results]

    return  results
   
    

def prepare_response_from_retrieved_data(query_result: dict):
    
    response_introduction = query_result['gen_sql_query']['response_introduction']

    sql_query_result = query_result['sql_query_result']
    query_results_columns = query_result['gen_sql_query']['query_results_columns']

    def format_retrieved_data(sql_query_result, query_results_columns):
        # If the result is a list of strings, treat it as a simple list
        if len(query_results_columns) == 1 and isinstance(sql_query_result, list):
            return f"<b style='font-size: 16px; color: #000; margin-bottom: 5px;'>List of unique {query_results_columns[0].replace('_', ' ').title()}</b>" + \
                "<ul style='list-style-type: disc; padding-left: 20px; margin-top: 0;'>" + \
                ''.join([f"<li style='margin: 5px 0; color: #333;'>{item}</li>" for item in sql_query_result]) + \
                "</ul>"

        # Otherwise format as a structured feedback entry
        formatted_entries = [
            f"<div style='border: 1px solid #eee; border-radius: 10px; padding: 15px; margin-bottom: 20px; background-color: #f9f9f9;'>" + \
            "<ul style='list-style-type: none; padding-left: 0;'>" + \
            ''.join([
                f"<li style='margin: 8px 0; font-size: 14px;'><span style='color: #3e4e8e; font-weight: bold;'>{key.replace('_', ' ').title()}:</span> <span style='color: #333;'>{value}</span></li>"
                for key, value in result_item.items()
                if value is not None and value != 'N/A'  # Exclude N/A values
            ]) + \
            "</ul></div>"
            for index, result_item in enumerate(sql_query_result)
        ]
        return ''.join(formatted_entries)

    # If there are no results, just return the no results message
    if not sql_query_result:
        return unsupported_query_message

    # Final response construction
    return f"<b style='font-size: 18px; color: #000;'>{response_introduction}</b><br><br>{format_retrieved_data(sql_query_result, query_results_columns)}"
    

def prepare_response_from_retrieved_data_branch():
    return RunnableBranch(
        (
          lambda query_result: isinstance(query_result, dict) and 'response_introduction' in query_result['gen_sql_query'] and 'query_results_columns' in query_result['gen_sql_query'] and 'sql_query_result' in query_result,
          RunnableLambda(prepare_response_from_retrieved_data)
        ),
        lambda query_result: unsupported_query_message
    )


def generate_sql_query_chain():
    system_prompt_str = """
    As a Business Intelligence Analyst Expert for Sun Life Resorts Hotel, your role is to generate optimized SQL queries from the user input using the Relational database table {db_table}, which logs the hotel's guests complaints and requests.
    While reading the user query, assess it's risk level as one of the following:
    - Safe: Relevant, appropriate, and risk-free.
    - Suspicious: Unusual or probing with unclear intent.
    - Malicious: Contains potentially harmful content or exploits.
    - Nonsense: Incoherent or random with no logical structure.
    - Uncontextual: Coherent but irrelevant to the system's purpose.
    - Ambiguous: Vague or unclear in intent.
    - Other: Does not fit any of the above categories.
    Constraints for Generated SQL Queries:
    - It must represent only a data retrieval or aggregation.
    - Ensure SQL Server compatibility.
    - Query only the {db_table} table.
    - Include only columns relevant [100% matching accuracy] to the user request in SQL SELECT clause and conditions.
    - Include specific columns in the SELECT clause if directly referenced by the user.
    - Include the client info (Name, Rm No) and the date and time of the feedback in the SQL SELECT clause as much as possible if it makes sense  
    - Limit results to the top 50 records if the query asks for a list of entities.*
    - Limit results to the top  1 record if the query asks for a single entity or a maximum, minimum or average value.*
    - Ensure that the sql query is valid SQL Server syntax.
    - ensure that all date and time fields query aware follow the ISO format or match the expected SQL Server format.
    - Ensure query optimization and efficiency.
    - Maintain the same column order as specified by the user.
    - If the user input does not comply with any of the requirements above, return an empty sql query.
    - Columns in {db_table} Table: 
    {table_columns}
    """

    retriever_prompt = ChatPromptTemplate.from_messages([
        ("system", system_prompt_str),
        ("human", "{input}"),
        ("human", "Using the user input and the sql query generation constraints, return the generated query in the format: {generated_sql_query_format}."),
    ])

    return retriever_prompt |  llm | JsonOutputParser(pydantic_object=GenSQLQuery)


def render_chat_history():
    # Display chat messages
    for message in st.session_state.chat_history:
        with st.chat_message(message["role"]):
            st.markdown(message['content'], unsafe_allow_html=True)

chain = generate_sql_query_chain() | RunnableBranch(
    (
        lambda gen_sql_query: 'Safe' in gen_sql_query['user_query_risk_level'] and gen_sql_query['sql_query'] != '',
        RunnableLambda(lambda gen_sql_query: { 'gen_sql_query': gen_sql_query, 'sql_query_result': retrieve_data(gen_sql_query) }) | prepare_response_from_retrieved_data_branch()
    ),
    (
        lambda gen_sql_query: 'Suspicious' in gen_sql_query['user_query_risk_level'] or 'Malicious' in gen_sql_query['user_query_risk_level'],
        lambda gen_sql_query: malicious_query_message
    ),
    (
        lambda gen_sql_query: 'Nonsense' in gen_sql_query['user_query_risk_level'],
        lambda gen_sql_query: nonsense_query_message
    ),
    lambda gen_sql_query: unsupported_query_message
)

if "chat_history" not in st.session_state.keys():
    st.session_state.chat_history = [{"role": "assistant", "content": "How can I help you ?"}]

    render_chat_history()

if user_input := st.chat_input("Write your question here"):
    st.session_state.chat_history.append({"role": "user", "content": user_input})

    render_chat_history()

    if st.session_state.chat_history[-1]['role'] != 'assistant':
        with st.chat_message('assistant'):
            with st.spinner("Please wait ..."):
                try:
                    response = chain.invoke({
                        "input": user_input,
                        "db_table": db_table,
                        "table_columns": db_table_columns_description,
                        "generated_sql_query_format": gen_sql_query_parser.get_format_instructions() 
                    })
                except Exception as e:
                    response = f"<p style='font-size: 16px; color: #d9534f;'>An error occurred while processing the query</p>"
                    print("An error occurred while processing the query: ", e)

                st.markdown(response, unsafe_allow_html=True)

                st.session_state.chat_history.append(
                    {
                    "role": "assistant",
                    "content": response
                    }
                )
