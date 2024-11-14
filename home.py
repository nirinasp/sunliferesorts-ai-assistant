import pyodbc

import streamlit as st

from langchain_core.prompts import ChatPromptTemplate
from langchain_core.prompts import MessagesPlaceholder
from langchain_core.output_parsers import JsonOutputParser
from langchain.schema.runnable import RunnableLambda, RunnablePassthrough
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

gen_sql_query_parser = JsonOutputParser(pydantic_object=GenSQLQuery)

def retrieve_data(gen_sql_query: dict):
    try:
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
    except:
        return []
    

def prepare_response_data(query_result: dict):
    try:
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
                f"<b style='color: #4CAF50; font-size: 16px;'>Feedback #{index + 1}</b>" + \
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
            return f"<p style='font-size: 16px; color: #d9534f;'>Unfortunately, we were unable to find any results that match your request.</p>"

        # Final response construction
        return f"<b style='font-size: 18px; color: #000;'>{response_introduction}</b><br><br>{format_retrieved_data(sql_query_result, query_results_columns)}"
    except:
        return f"<p style='font-size: 16px; color: #d9534f;'>Unfortunately, we were unable to find any results that match your request.</p>"




def create_chain():
    llm = ChatOpenAI(temperature=0.2)

    system_prompt_str = """
    As a Business Intelligence Analyst Expert for Sun Life Resorts Hotel, your role is to analyze user inputs and generate optimized SQL queries about the hotel's feedback stored inside the hotel_complaints_with_scores table.
    Constraints for Generated SQL Queries:
    - Ensure SQL Server compatibility.
    - Query data from the hotel_complaints_with_scores table.
    - Include only columns relevant [100% matching accuracy] to the user request in SQL SELECT clause and conditions.
    - Include specific columns in the SELECT clause if directly referenced by the user.
    - Include the client info (Name, Rm No) and the date and time of the feedback in the SQL SELECT clause as much as possible if it makes sense  
    - Limit results to the top 20 records if the response is a list.*
    - Ensure that the query is valid SQL Server syntax.
    - Ensure query optimization and efficiency.
    - Maintain the same column order as specified by the user.
    - If the user input does not refer any valid column, return a query that return an empty result.
    - Columns in hotel_complaints_with_scores Table: 
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
    """

    retriever_prompt = ChatPromptTemplate.from_messages([
        ("system", system_prompt_str),
        ("human", "{input}"),
        ("human", "Based on the user input, generate an SQL query that strictly adheres to the specified requirements. Return the response in the format: {generated_sql_query_format}."),
    ])

    return retriever_prompt |  llm | JsonOutputParser(pydantic_object=GenSQLQuery) | { 'gen_sql_query': RunnablePassthrough(), 'sql_query_result': retrieve_data } | prepare_response_data


def render_chat_history():
    # Display chat messages
    for message in st.session_state.chat_history:
        with st.chat_message(message["role"]):
            st.markdown(message['content'], unsafe_allow_html=True)


chain = create_chain()

if "chat_history" not in st.session_state.keys():
    st.session_state.chat_history = [{"role": "assistant", "content": "How can I help you ?"}]

    render_chat_history()

if user_input := st.chat_input("Write your question here"):
    st.session_state.chat_history.append({"role": "user", "content": user_input})

    render_chat_history()

    if st.session_state.chat_history[-1]['role'] != 'assistant':
        with st.chat_message('assistant'):
            with st.spinner("Please wait ..."):
                response = chain.invoke({
                    "input": user_input,
                    "generated_sql_query_format": gen_sql_query_parser.get_format_instructions() 
                })   

                st.markdown(response, unsafe_allow_html=True)

                st.session_state.chat_history.append(
                    {
                    "role": "assistant",
                    "content": response
                    }
                )
