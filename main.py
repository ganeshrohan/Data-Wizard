import warnings
import asyncio
from datetime import datetime
import os
import shutil
import re

import streamlit as st
from streamlit import _bottom
import pandas as pd
from pandasai import SmartDatalake
from pandasai.responses.streamlit_response import StreamlitResponse


from utils.snowchat_ui import message_func, append_message
from utils.snow_connect import get_sql, execute_sql
from graph_rag.search.rag_local import search, llm_model
from graph_rag.search.templet import mermaid_system_propmpt, system_context_codeQ
from custom_lineage import render_mermaid

from pygwalker.api.streamlit import init_streamlit_comm

warnings.filterwarnings("ignore")

def main():
    """
    Main function to run the Streamlit application.
    """
    init_streamlit_comm()  # For PyGwalker rendering

    st.title(":rainbow[Data Wizard]:sparkles:")
    st.caption("Talk your way through Enterprise data")

    # --- Sidebar Setup ---
    with st.sidebar:
        st.session_state.setdefault('user', "Developer")
        st.session_state['user'] = st.radio(
            "Select User Type:",
            options=["Business User", "Developer"],
            index=["Business User", "Developer"].index(st.session_state['user']),
            horizontal=True,
        )

        st.session_state.setdefault('Model', "Llama")
        st.session_state['Model'] = st.radio(
            "Select Model:",
            options=["Gemini", "Llama", "Deepseek"],
            index=["Gemini", "Llama", "Deepseek"].index(st.session_state['Model']),
            horizontal=True,
        )
        
        st.page_link("pages/illuminate.py", label="illuminate")

        if st.button("Reset Chat"):
            for key in st.session_state.keys():
                del st.session_state[key]
            st.rerun()

    # --- Initialize Chat ---
    if "messages" not in st.session_state:
        st.session_state["messages"] = [{"role": "assistant", "content": "Hey there, I'm Data Wizard! ❄️🔍 How can I assist you?"}]
    
    if "smart_df" not in st.session_state:
        st.session_state["smart_df"] = None

    # --- Display Chat History ---
    for i, msg in enumerate(st.session_state.get('messages', [])):
        message_func(msg.get('content'), msg.get('role'))
        if msg.get('role') == 'assistant' and get_sql(msg.get('content')):
            st.button(
                "Generate Code Lineage", 
                key=f"code_lineage_{i}", 
                on_click=code_lineage_response,
                args=(get_sql(msg.get('content')),)
            )

    # --- Handle User Input ---
    if prompt := st.chat_input("Ask me about your data...", key="chat_input"):
        append_message(prompt, "user")
        
        # Check for file upload
        uploaded_file = st.session_state.get('chat_input_file') 
        if uploaded_file:
            st.session_state["smart_df"] = True
            df = pd.read_csv(uploaded_file)
            append_message(df, "data")
        
        # If a dataframe is already in context (from upload or previous query)
        elif st.session_state.get("smart_df"):
            latest_df = None
            for message in reversed(st.session_state['messages']):
                if message.get('role') == 'data' and isinstance(message.get('content'), pd.DataFrame):
                    latest_df = message['content']
                    break
            if latest_df is not None:
                pandas_ai(latest_df, prompt)
        
        # Default RAG and SQL generation flow
        else:
            with st.spinner("Assistant is thinking..."):
                try:
                    rag_response = asyncio.run(search(prompt, model()))
                    response = rag_response.response
                    st.session_state["context"] = response
                    append_message(str(response))

                    if sql_query := get_sql(response):
                        df = execute_sql(sql_query)
                        if df is not None:
                            append_message(df, "data")
                except Exception as e:
                    st.error(f"An error occurred: {e}")
        st.rerun()

## Under development
def pandas_ai(df: pd.DataFrame, prompt: str):
    """
    Handles interaction with PandasAI SmartDatalake.
    """
    # Standardized path for saving charts. Ensure this directory exists.
    pass

## Under development
def model(is_pandas_ai: bool = False):
    """
    Selects and initializes the LLM based on user selection in the UI.
    API keys should be handled within the imported 'llm_model' function,
    preferably using environment variables.
    """
    pass

## Under development
def extract_mermaid_code(text: str) -> str | None:
    """
    Extracts the first Mermaid code block from the given text.
    """
    pass

## Under development
def code_lineage_response(code: str):
    """
    Generates and displays a Mermaid diagram for SQL code lineage.
    Retries with a fix prompt if the initial diagram fails to render.
    """
    pass

if __name__ == "__main__":
    main()