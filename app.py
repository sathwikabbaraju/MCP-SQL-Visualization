import streamlit as st
import asyncio
import json
from agent import run_agent
from dashboard_agent import run_agent as run_dashboard_agent

from typing import Dict, Any

st.set_page_config(
    page_title="MCP SQL Chatbot & Dashboard",
    page_icon="🧊",
    layout="wide",
    initial_sidebar_state="expanded",
    
)

# Title and Header
st.title("🧊 MCP SQL Chatbot & Dashboard")
st.write(
    "Interact with an SQL database using natural language and visualize database trends. "
    "This app connects to an MCP SQL server to execute your queries, provide results, and generate dashboards."
)

# Sidebar
with st.sidebar:
    st.header("ℹ️ About")
    st.markdown(
        "This application allows you to interact with an SQL database using natural language and visualize data. "
        "It leverages the MCP (Modular Control Protocol) to connect to an SQL server, "
        "execute your queries, present the results, and generate interactive dashboards."
    )
    st.markdown(
        "**How to use:**\n"
        "1. Ensure the MCP SQL server is running.\n"
        "2. Ask your questions in the chat box below.\n"
        "3. The app will generate and execute the appropriate SQL query.\n"
        "4. The results will be displayed in the chat.\n"
        "5. Navigate to the 'Dashboard' tab to view database insights."
    )
    


def display_html_dashboard(html_content: str):
    """Displays the HTML dashboard in Streamlit."""
    st.components.v1.html(html_content, height=800, scrolling=True)


# --- Main App Logic ---

# Initialize session state
if "messages" not in st.session_state:
    st.session_state.messages = []
if "conversation_state" not in st.session_state:
    st.session_state.conversation_state = {}
if "dashboard_html" not in st.session_state:
    st.session_state.dashboard_html = ""

# Tabs
tab1, tab2 = st.tabs(["Chatbot", "Dashboard"])

# Chatbot Tab
with tab1:
    # Create a container for the chat messages
    chat_container = st.container()

    # Add an id to the chat container
    chat_container.markdown('<div id="chat-container"></div>', unsafe_allow_html=True)

    # Display chat history within the container
    with chat_container:
        for message in st.session_state.messages:
            with st.chat_message(message["role"]):
                st.markdown(message["content"])

    # User input
    user_query = st.chat_input("Ask a question about the database (e.g., 'List all employees')", key="chat_input")

    if user_query:
        st.session_state.messages.append({"role": "user", "content": user_query})

        # Display the user message immediately
        with chat_container:
            with st.chat_message("user"):
                st.markdown(user_query)

        with st.spinner("Fetching response from the database..."):
            try:
                resp = asyncio.run(run_agent(user_query))
            except Exception as e:
                st.error(f"An error occurred: {e}")
                resp = None

        if resp:
            # Add assistant's response to session state
            st.session_state.messages.append({"role": "assistant", "content": resp.content})

            # Display the assistant message immediately
            with chat_container:
                with st.chat_message("assistant"):
                    st.markdown(resp.content)

    

# Dashboard Tab
with tab2:
    st.header("Database Dashboard")

    if st.button("Generate Dashboard"):
        with st.spinner("Analyzing database and generating dashboard..."):
            try:
                dashboard_response = asyncio.run(run_dashboard_agent("Analyse my database and suggest a dashboard"))
                #remove  ```html if present
                __html = dashboard_response.content
                if __html.startswith("```html"):
                    __html =  __html.replace("```html", "")
                    if __html.endswith("```"):
                        __html = __html.replace("```", "")
                st.session_state.dashboard_html = __html
                display_html_dashboard(__html)

            except Exception as e:
                st.error(f"An error occurred: {e}")
                
    if st.session_state.dashboard_html:
        st.download_button(
            label="Download Dashboard HTML",
            data=st.session_state.dashboard_html,
            file_name="dashboard.html",
            mime="text/html",
        )