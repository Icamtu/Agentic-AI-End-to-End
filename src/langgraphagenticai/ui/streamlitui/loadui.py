# loadui.py
import streamlit as st
import os
from datetime import date
import graphviz
from langchain_core.messages import AIMessage, HumanMessage
from src.langgraphagenticai.ui.uiconfigfile import Config
from src.langgraphagenticai.graph.graph_builder import GraphBuilder  # Fixed import path

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
            dot.edges([("START", "chatbot"), ("chatbot", "tools"), ("tools", "chatbot")])
            dot.edge("chatbot", "chatbot", label="conditional", style="dashed")
        elif usecase == "Blog Generation":
            dot.node("START", "START")
            dot.node("orchestrator", "Orchestrator")
            dot.node("llm_call", "LLM Call (Workers)")
            dot.node("synthesizer", "Synthesizer")
            dot.node("hallucination_checker", "Hallucination Checker")  # Added new node
            dot.node("END", "END")
            dot.edges([
                ("START", "orchestrator"),
                ("llm_call", "synthesizer"),
                ("synthesizer", "hallucination_checker"),
                ("hallucination_checker", "END")
            ])
            dot.edge("orchestrator", "llm_call", label="parallel", style="dashed")
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
                "Select LLM", llm_options, help="Choose the language model to use."
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