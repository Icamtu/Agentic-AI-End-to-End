import streamlit as st
import os
from datetime import date
import graphviz
from langchain_core.messages import AIMessage, HumanMessage
from src.langgraphagenticai.ui.uiconfigfile import Config
from src.langgraphagenticai.graph.graph_builder import GraphBuilder  

class LoadStreamlitUI:
    def __init__(self):
        self.config = Config()
        self.user_controls = {}

    def initialize_session(self):
        """Initialize session state with default values."""
        return {
            "current_step": "requirements",
            "requirements": "",
            "user_stories": "",
            "po_feedback": "",
            "generated_code": "",
            "review_feedback": "",
            "decision": None
        }

    def create_graph_diagram(self, usecase):
        """Create a graph diagram for the selected use case using GraphBuilder."""
        dot = graphviz.Digraph(comment=f"{usecase} Graph", format="png")

        # Define graph structure based on use case
        if usecase == "Basic Chatbot":
            dot.node("START", "START")
            dot.node("chatbot", "Chatbot")
            dot.node("END", "END")
            dot.edges([("START", "chatbot"), ("chatbot", "END")])
        elif usecase == "Chatbot with Tool":
            dot.node("START", "START")
            dot.node("chatbot", "Chatbot")
            dot.node("tools", "Tools")
            dot.node("END", "END")
            dot.edges([("START", "chatbot"), ("chatbot", "END")])
            dot.edge("chatbot", "tools", label="conditional", style="dashed")
            dot.edge("tools", "chatbot",  style="dashed")

        elif usecase == "Blog Generation":
                dot.node("S", "START")
                dot.node("A", "User Input",shape="rectangle")
                dot.node("B", "Outline Generator-LLM",shape="rectangle")
                dot.node("C", "Outline Review-Human",shape="rectangle")
                dot.node("D", "Draft Generator-LLM",shape="rectangle")
                dot.node("E", "Draft Review-Human",shape="rectangle")
                dot.node("I", "Web Search/Scraping",shape="rectangle")
                dot.node("F", "Revision Generator-LLM",shape="rectangle")
                dot.node("G", "END")

                # Edges (Flow between nodes)
                dot.edge("S", "A")
                dot.edge("A", "B")
                dot.edge("B", "C", label="Generated Outline")
                dot.edge("C", "D")
                dot.edge("C", "B", label="Edited Outline")  # Human feedback loop for Outline
                dot.edge("D", "E")
                dot.edge("D", "I", label="Needs Facts")  # If draft needs more facts, search
                dot.edge("I", "D", label="Relevant Info")  # Enrich draft with factual data
                dot.edge("E", "G")  # If approved, go to END
                dot.edge("E", "F", label="Feedback")
                dot.edge("F", "E", label="Refined Draft")  # Loopback for feedback updates

        elif usecase == "Coding Peer Review":
            dot.node("START", "START")
            dot.node("reviewer", "Reviewer")
            dot.node("END", "END")
            dot.edges([("START", "reviewer"), ("reviewer", "END")])

        return dot

    def load_streamlit_ui(self):
        """Load and configure the Streamlit UI with user controls and graph diagram."""
        page_title = self.config.get_page_title()
        logo = self.config.get_logo() if hasattr(self.config, "get_logo") else "🧠"  # Default to 🧠, customizable via Config
        st.set_page_config(page_title=f"{logo} {page_title}", layout="wide")
        st.header(f"{logo} {page_title}")

        # Initialize session state variables
        if "timeframe" not in st.session_state:
            st.session_state.timeframe = ""
        if "IsFetchButtonClicked" not in st.session_state:
            st.session_state.IsFetchButtonClicked = False
        if "IsSDLC" not in st.session_state:
            st.session_state.IsSDLC = False
        if "state" not in st.session_state:
            st.session_state.state = self.initialize_session()

        with st.sidebar:
            st.subheader("Configuration")

            llm_options = self.config.get_llm_options()
            usecase_options = self.config.get_usecase_options()

            self.user_controls["selected_llm"] = st.selectbox(
                "Select LLM", llm_options, help="Choose the language model provider to use."
            )

            if self.user_controls["selected_llm"] == "Groq":
                model_options = self.config.get_groq_model_options()
                self.user_controls["selected_groq_model"] = st.selectbox(
                    "Select Model", model_options, help="Choose a specific Groq model."
                )
                self.user_controls["GROQ_API_KEY"] = st.text_input(
                    "GROQ API Key",
                    type="password",
                    value=st.session_state.get("GROQ_API_KEY", ""),
                    help="Enter your Groq API key (see https://console.groq.com/keys)."
                )
                st.session_state["GROQ_API_KEY"] = self.user_controls["GROQ_API_KEY"]
                if not self.user_controls["GROQ_API_KEY"]:
                    st.warning("⚠️ Please enter your GROQ API key to proceed.")
            elif self.user_controls["selected_llm"] == "Google":
                model_options = self.config.get_google_model_options()
                self.user_controls["selected_google_genai_model"] = st.selectbox(
                    "Select Model", model_options, help="Choose a specific Google GenAI model."
                )
                self.user_controls["GOOGLE_API_KEY"] = st.text_input(
                    "Google API Key",
                    type="password",
                    value=st.session_state.get("GOOGLE_API_KEY", ""),
                    help="Enter your Google API key (see https://console.cloud.google.com/apis/credentials)."
                )
                st.session_state["GOOGLE_API_KEY"] = self.user_controls["GOOGLE_API_KEY"]
                if not self.user_controls["GOOGLE_API_KEY"]:
                    st.warning("⚠️ Please enter your Google API key to proceed.")
            
            elif self.user_controls["selected_llm"] == "OpenAI":
                model_options = self.config.get_openai_model_options()
                self.user_controls["selected_openai_model"] = st.selectbox(
                    "Select Model", model_options, help="Choose a specific OpenAI model."
                )
                self.user_controls["OPENAI_API_KEY"] = st.text_input(
                    "OpenAI API Key",
                    type="password",
                    value=st.session_state.get("OPENAI_API_KEY", ""),
                    help="Enter your OpenAI API key (see https://platform.openai.com/account/api-keys)."
                )
                st.session_state["OPENAI_API_KEY"] = self.user_controls["OPENAI_API_KEY"]
                if not self.user_controls["OPENAI_API_KEY"]:
                    st.warning("⚠️ Please enter your OpenAI API key to proceed.")



            self.user_controls["selected_usecase"] = st.selectbox(
                "Select Use Case", usecase_options, help="Choose the application use case."
            )

            if self.user_controls["selected_usecase"] in ["Chatbot with Tool", "Blog Generation"]:
                self.user_controls["TAVILY_API_KEY"] = st.text_input(
                    "Tavily API Key",
                    type="password",
                    value=st.session_state.get("TAVILY_API_KEY", ""),
                    help="Enter your Tavily API key (see https://app.tavily.com/home)."
                )
                os.environ["TAVILY_API_KEY"] = self.user_controls["TAVILY_API_KEY"]
                st.session_state["TAVILY_API_KEY"] = self.user_controls["TAVILY_API_KEY"]
                if not self.user_controls["TAVILY_API_KEY"]:
                    st.warning("⚠️ Please enter your Tavily API key to proceed.")

            # Reset button
            if st.button("Reset Session", help="Clear all inputs and reset the session."):
                for key in st.session_state.keys():
                    del st.session_state[key]
                st.session_state.state = self.initialize_session()
                st.success("Session reset successfully!")

            st.subheader("Graph Structure")
            selected_usecase = self.user_controls["selected_usecase"]
            try:
                graph_diagram = self.create_graph_diagram(selected_usecase)
                st.graphviz_chart(graph_diagram, use_container_width=True)
            except Exception as e:
                st.error(f"Failed to render graph: {e}")

        return self.user_controls