import warnings
import asyncio
from datetime import datetime
import streamlit as st
from streamlit import _bottom
# Configure Streamlit page (production settings)
st.set_page_config(page_title="Data Wizard", page_icon=":sparkles:", layout="centered", initial_sidebar_state="expanded")

import logging

# Load environment variables and configuration
from datawizard.config import settings

import snowflake
import pandas as pd
from pandasai import SmartDatalake
# from pandasai import PandasAI
from pandasai.responses.streamlit_response import StreamlitResponse
import numpy as np
import shutil
# Langchain imports
# from langchain.llms import OpenAI
from langchain_community.llms import OpenAI
# from dotenv import load_dotenv, find_dotenv

# Set up structured logging
logger = logging.getLogger("datawizard.main")
logger.setLevel(logging.INFO)
if not logger.handlers:
    handler = logging.StreamHandler()
    formatter = logging.Formatter("%(asctime)s | %(levelname)s | %(name)s | %(message)s")
    handler.setFormatter(formatter)
    logger.addHandler(handler)
from dotenv import load_dotenv, find_dotenv

from langchain.prompts import PromptTemplate
# from langchain.agents.agent_toolkits import create_python_agent
# from langchain.tools.python.tool import PythonREPLTool 
from langchain.agents.agent_types import AgentType

from gradio_client import Client
from langchain_openai import ChatOpenAI
from langchain.chains import ConversationChain
from langchain.chains.conversation.memory import ConversationBufferWindowMemory


from utils.snowchat_ui import message_func,append_message
from utils.snow_connect import get_sql,execute_sql

from pygwalker.api.streamlit import StreamlitRenderer, init_streamlit_comm,get_streamlit_html
#from streamlit_extras.switch_page_button import switch_page

from graphrag.query.llm.oai.typing import OpenaiApiType

#from rag2 import search
from graph_rag.search.rag_local import search
from graph_rag.search.rag_local import llm_model
from graph_rag.search.templet import mermaid_system_propmpt

import re
from openai import OpenAI

from custom_lineage import render_mermaid


from graph_rag.search.templet import Data_description,system_context_codeQ
warnings.filterwarnings("ignore")

def main():
    init_streamlit_comm() # -> PyGwalker render
    chat_history = []
    st.title(":rainbow[Data Wizard]:sparkles:") 
    st.caption("Talk your way through Enterprise data")

    # Determine the user

    with st.sidebar:
        st.session_state['user'] = st.radio(
            "",
            options=["Business User","Developer"],
            index=1,
            horizontal=True,
        )
    # # Determine the user

    with st.sidebar:
        st.session_state['Model'] = st.radio(
            "",
            options=["Gemini","Llama","Deepseek"],
            index=1,
            horizontal=True,
        )
    st.page_link("pages/illuminate.py", label="illuminate")


    # Add a reset button
    if st.sidebar.button("Reset Chat"):
        for key in st.session_state.keys():
            del st.session_state[key]


    st.sidebar.markdown("Data Wizard")

    MESSAGE = [{"role":"assistant","content":"Hey there, I'm Data Wizard, your SQL-speaking sidekick! ❄️🔍 How can I assist you?"}]


    if "messages" not in st.session_state.keys():
        st.session_state["messages"] = []

    if "smart_df" not in st.session_state.keys():
        st.session_state["smart_df"] = None


    
    message_func(MESSAGE[0].get('content'), MESSAGE[0].get('role'))

    if prompt := st.chat_input("You:",accept_file=True,file_type="csv"):
        try:
            append_message(prompt.text,"user")
            if prompt.files:
                st.session_state["smart_df"] = True
                df = pd.read_csv(prompt.files[0])
                append_message(df, "data")

            if st.session_state["smart_df"] is not None:
                for message in reversed(st.session_state['messages']):
                    if message.get('role') == 'data' and isinstance(message.get('content'), pd.DataFrame):
                        df = message['content']
                pandas_ai(df,prompt.text)

            else:
                with _bottom:
                    with st.spinner("Assistant is thinking..."):
                        rag_response = asyncio.run(search(prompt.text, model()))
                    # context = Data_description.replace("{question}", prompt)
                    # context = context.replace("{contents}", rag_response.response)
                print('===========================================================')
                #print('response', rag_response)
                #print('===========================================================')
                print('response', rag_response.response)
                print('prompt_tokens',rag_response.prompt_tokens)
                print('completion_time',rag_response.completion_time)
                print('llm_calls',rag_response.llm_calls)
                print('=============================================================')
               
                response = rag_response.response
                st.session_state["context"] = response

                append_message(str(response))
                if get_sql(response):
                    df = execute_sql(get_sql(response))
                    if df is not None:
                        append_message(df, "data")

        except Exception as e:
            st.error(f"An error occurred: {e}")

    for i in range(len(st.session_state['messages'])):
        if i < len(st.session_state['messages']):
            message_func(st.session_state['messages'][i].get('content'), st.session_state['messages'][i].get('role'))
        if st.session_state['messages'][i].get('role') == 'assistant' and get_sql(st.session_state['messages'][i].get('content')):
            
            st.button("Generate Code Lineage", key=f"code_lineage_{i}", on_click=lambda code=get_sql(st.session_state['messages'][i].get('content')): code_lineage_response(code))
            st.page_link("pages/illuminate.py", label="illuminate")
        


def pandas_ai(df,prompt):
    # Set up SmartDataframe and store it in session state for reuse
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    user_defined_path = "C:/Code/DataWizard/exports/charts/chart_copy/"+"file_" + timestamp + ".png"
    st.session_state.smart_df = SmartDatalake(
        df, config={
                     "llm": model(is_pandas_ai=True),
                     "verbose": True, 
                     "response_parser": StreamlitResponse, 
                     "custom_whitelisted_dependencies":["seaborn","wordcloud","matplotlib","re"]
                     }
        )

    if prompt:
        smart_df_res = st.session_state.smart_df.chat(prompt)
        if isinstance(smart_df_res,str):
            if smart_df_res.endswith('.png'):
                shutil.copy(smart_df_res,user_defined_path)
                append_message(user_defined_path,role='image')
            else:
                append_message(smart_df_res)
        else:
            append_message(smart_df_res,"data")
        


def converstations(llm,context,system_context=None):
    model = st.session_state['Model']

    if system_context is None:
        system_context = system_context_codeQ
    
    conversation = llm.generate(
        messages=[
            {"role": "system", "content": system_context},
            {"role": "user", "content": context}
        ],
        streaming=False
    )
    return conversation



def model(context=None,system_context=None,llm_only=True, is_pandas_ai=False):
    model = st.session_state['Model']
    if model  == 'Gemini':
            llm_model_name="google/gemma-4-31b-it:free"
    elif model == 'Llama': 
            llm_model_name="meta-llama/llama-3.3-70b-instruct:free"
    else:
        llm_model_name = "deepseek/deepseek-r1:free"

    llm_model_out = llm_model(llm_model_name, is_pandas_ai=is_pandas_ai)
    if llm_only:
        return llm_model_out
    else:
        response = converstations(llm_model_out,context,system_context)
        return response


def extract_mermaid_code(text):
    """
        Extracts the first Mermaid code block from the given text and removes characters not friendly with Mermaid syntax.

        Args:
            text (str): Input text containing Mermaid code block.

        Returns:
            str or None: Mermaid code (without the ```mermaid delimiters), or None if not found.
        """
    pattern = r"```mermaid\s+([\s\S]+?)```"
    match = re.search(pattern, text)
    if match:
        mermaid_code = match.group(1).strip()
        # Remove characters not friendly with Mermaid syntax (e.g., ())
        mermaid_code = re.sub(r"[\(\)]", "", mermaid_code)
        return mermaid_code
    return None

def code_lineage(code):
    lineage = model(llm_only=False,system_context=mermaid_system_propmpt,context=code)
    lineage = extract_mermaid_code(lineage)
    append_message(lineage, role='lineage')


def code_lineage_response(code: str) -> str:
    """
    Generates a Mermaid diagram code from the provided code snippet.
    Retries model_response with error message if rendering fails.
    """
    max_attempts = 2
    lineage = None
    error_message = None
    for attempt in range(max_attempts):
        if attempt == 0:
            combined_context = f"{mermaid_system_propmpt}\n\n{code}"
            lineage_response = model(llm_only=False, context=combined_context)
        else:
            # Add error message to context for LLM to fix the diagram
            retry_context = f"{code}\n\n# Previous Mermaid diagram failed to render with error: {error_message or 'Unknown error'}\n# Please fix the Mermaid code."
            lineage_response = model(llm_only=False, system_context=mermaid_system_propmpt, context=retry_context)
        lineage = extract_mermaid_code(lineage_response)

        try:
            append_message(render_mermaid(lineage),role='lineage') # , height=600, scrolling=False)
            return  # Success, exit the function
        except Exception as e:
            error_message = str(e)
            if attempt == max_attempts - 1:
                append_message("There was an internal issue rendering the diagram after multiple attempts.")

if __name__ =="__main__":
    main()