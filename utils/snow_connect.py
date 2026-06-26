import snowflake
from snowflake.sqlalchemy import URL
from sqlalchemy import create_engine
from utils.snowchat_ui import message_func,append_message
from sqlalchemy.exc import OperationalError,ProgrammingError
import re
import pandas as pd
import numpy as np
import streamlit as st

def Snowflake_Connection():
    # Establishing the connection


    engine = create_engine(URL(
        account = '',
        user = '',
        password = '',
        database = '',
        schema = '',
        warehouse = ''
    ))

    return engine


def get_sql(text):
    sql_match = re.search(r"```sql\n([\s\S]*?)\n```", text) #, re.DOTALL
    return sql_match.group(1).strip() if sql_match else None


def handle_sql_exception(query, conn, e, retries=2):

    #Avoid circular import 
    from main import model as model_response 
    

    # context = main.context
    # print("Error handel", context)
    context = st.session_state['context'][-1]

    append_message("Uh oh, I made an error, let me try to fix it..","assistant")
    error_message = (context + 
        "\n You gave me a wrong SQL. FIX The SQL query :  \n```sql\n"
        + query
        + "\n```\n Error message: \n "
        + str(e)
    )
    print("Error Message",error_message)
    new_query = model_response(error_message,"FIX The Snowflake SQL query by re-writing it completely. Highlight SQL code using ```sql <SQL> ```.",llm_only=False)
    new_sql = get_sql(new_query)
    append_message(new_sql)
    if new_sql and retries > 0:
        return execute_sql(new_sql, retries - 1)
    else:
        append_message("I'm sorry, I couldn't fix the error. Please try again.","assistant")
        return None

@st.cache_data(show_spinner=False)
def execute_sql(query, _retries=2):
    if re.match(r"^\s*(drop|alter|truncate|delete|insert|update|merge)\s", query, re.I):
        append_message("Sorry, I can't execute queries that can modify the database.","assistant")
        return None
    try:
        df = pd.read_sql(query,Snowflake_Connection())
    #except snowflake.connector.errors.ProgrammingError as e:
    except ProgrammingError or OperationalError as e:
        return handle_sql_exception(query, Snowflake_Connection(), e, _retries)
    return df