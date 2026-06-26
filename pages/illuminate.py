import streamlit as st
from pygwalker.api.streamlit import StreamlitRenderer
import pandas as pd
st.set_page_config(layout="wide",initial_sidebar_state="collapsed")

st.title(":rainbow[Illuminate]")


st.page_link("C:/Code/DataWizard/main.py", label="Explorer")

def illuminate():
    print("Inside illuminate")
    df = None

    for message in reversed(st.session_state['messages']):
        if message.get('role') == 'data' and isinstance(message.get('content'), pd.DataFrame):
            df = message['content']  # Assign the found DataFrame
            break
    if df is not None:

        pyg = StreamlitRenderer(df)
        pyg.explorer() #width=1000, height=600, scrolling=True

illuminate()