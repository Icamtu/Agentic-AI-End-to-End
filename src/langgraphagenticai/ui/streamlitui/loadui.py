# Needed libraries: pip install streamlit graphviz requests python-dotenv
import streamlit as st
from datetime import date
import graphviz
import json
import requests # Needed for HTTP requests to QuickChart
import os
from dotenv import load_dotenv
import logging # Import logging if you want to use the logger from Config

# Assuming Config class is correctly defined in this file or imported
# If it's defined elsewhere, ensure the path is correct for your project structure
try:
    # This assumes your Config class is in the specified path
    from src.langgraphagenticai.ui.uiconfigfile import Config
    logger = logging.getLogger(__name__) # Setup logger if using Config's logger style
    logger.info("Successfully imported Config class.")
except ImportError as e:
    st.error(f"Failed to import Config class: {e}. Please ensure 'src/langgraphagenticai/ui/uiconfigfile.py' exists and defines the Config class.")
    # Provide a dummy class to prevent immediate crash, but highlight the error
    class Config:
        def get_page_title(self): return "Error: Config Missing"
        def get_llm_options(self): return []
        def get_usecase_options(self): return []
        def get_groq_model_options(self): return []
        def get_google_model_options(self): return []
        def get_openai_model_options(self): return []
    logger = logging.getLogger(__name__)
    logger.error("Using dummy Config class due to import error.")


# --- Main Streamlit UI Class ---
class LoadStreamlitUI:
    def __init__(self):
        """Initialize the Streamlit UI class."""
        self.config = Config() 
        self.user_controls = {}
        load_dotenv() # Load environment variables

    def initialize_session(self):
        """Initialize session state with default values."""
        # (This function remains the same - initializes session state)
        base_state = {
            "current_step": "requirements", 
            "requirements": "", 
            "user_stories": "",
            "po_feedback": "", 
            "generated_code": "", 
            "review_feedback": "",
            "decision": None, 
            "timeframe": "", 
            "IsFetchButtonClicked": False,
            "IsSDLC": False,
            "GROQ_API_KEY": os.getenv("GROQ_API_KEY", ""),
            "GOOGLE_API_KEY": os.getenv("GOOGLE_API_KEY", ""),
            "OPENAI_API_KEY": os.getenv("OPENAI_API_KEY", ""),
            "TAVILY_API_KEY": os.getenv("TAVILY_API_KEY", "")
        }
        if 'state' not in st.session_state:
             st.session_state.state = base_state
        else:
             st.session_state.state.update({k: v for k, v in base_state.items() if k not in st.session_state.state})
        for key, value in base_state.items():
            if key not in st.session_state:
                st.session_state[key] = value
        return st.session_state.state

    def create_graph_diagram(self, usecase):
        """
        Create a graph diagram definition for the selected use case
        and return the DOT language string.
        (This function remains the same - generates DOT source)
        """
        dot = graphviz.Digraph(comment=f"{usecase} Graph")
        dot.attr(rankdir="TB")
        # --- Graph Definitions ---
        if usecase == "Basic Chatbot":
            dot.node("START", "START"); dot.node("chatbot", "Chatbot"); dot.node("END", "END")
            dot.edge("START", "chatbot"); dot.edge("chatbot", "END")
        elif usecase == "Chatbot with Tool":
            dot.node("START", "START"); dot.node("chatbot", "Chatbot"); dot.node("tools", "Tools"); dot.node("END", "END")
            dot.edge("START", "chatbot"); dot.edge("chatbot", "tools", label="tools_condition", style="dashed", constraint="false")
            dot.edge("tools", "chatbot", label="return"); dot.edge("chatbot", "END", label="no tools", style="dashed", constraint="false")
        elif usecase == "Blog Generation":
            dot.node("START", "START"); dot.node("user_input", "User Input"); dot.node("orchestrator", "Orchestrator")
            dot.node("llm_call", "LLM Call"); dot.node("synthesizer", "Synthesizer"); dot.node("feedback_collector", "Feedback Collector", shape="diamond")
            dot.node("file_generator", "File Generator"); dot.node("END", "END")
            dot.edge("START", "user_input"); dot.edge("user_input", "orchestrator"); dot.edge("orchestrator", "llm_call", label="assign_workers", style="dashed")
            dot.edge("llm_call", "synthesizer"); dot.edge("synthesizer", "feedback_collector")
            dot.edge("feedback_collector", "orchestrator", label="revise", style="dashed", color="orange")
            dot.edge("feedback_collector", "file_generator", label="accept", style="dashed", color="green")
            dot.edge("file_generator", "END")
        elif usecase == "SDLC":
            planning_color = '#f9d5e5'
            design_color = '#eeeeee'
            development_color = '#d4f1f9'
            testing_color = '#e1f7d5'
            deployment_color = '#ffeecc'
            decision_color = '#f0f0f0'
            # Start node
            dot.node('start', 'Start', shape='oval', style='filled', fillcolor='white')
            # Planning Phase
            with dot.subgraph(name='cluster_planning') as planning:
                planning.attr(label='Planning', style='filled', fillcolor=planning_color, color='black')
                planning.node('requirements', 'Gather Requirements', fillcolor=planning_color)
                planning.node('userStories', 'Generate User Stories', fillcolor=planning_color)
                planning.node('poReview', 'Product Owner Review', shape='diamond', fillcolor=decision_color)
                planning.node('planning_phase', 'Release Planning', fillcolor=planning_color) # Renamed to avoid conflict with subgraph name
            # Design Phase
            with dot.subgraph(name='cluster_design') as design:
                design.attr(label='Design', style='filled', fillcolor=design_color, color='black')
                design.node('designDocs', 'Create Design Documents', fillcolor=design_color)
                design.node('designReview', 'Design Review', shape='diamond', fillcolor=decision_color)
                design.node('designRevision', 'Revise Design', fillcolor=design_color)
                design.node('architecture', 'Finalize Architecture', fillcolor=design_color)
            # Development Phase
            with dot.subgraph(name='cluster_development') as development:
                development.attr(label='Development', style='filled', fillcolor=development_color, color='black')
                development.node('generateCode', 'Code Development', fillcolor=development_color) # Fixed node ID casing
                development.node('codeReview', 'Code Review', shape='diamond', fillcolor=decision_color)
                development.node('codeFix', 'Fix Code Issues', fillcolor=development_color)
                development.node('securityScan', 'Security Review', fillcolor=development_color)
                development.node('securityFix', 'Address Security Issues', fillcolor=development_color)
            # Testing Phase
            with dot.subgraph(name='cluster_testing') as testing:
                testing.attr(label='Testing', style='filled', fillcolor=testing_color, color='black')
                testing.node('testCases', 'Write Test Cases', fillcolor=testing_color)
                testing.node('unitTests', 'Unit Testing', fillcolor=testing_color)
                testing.node('integrationTests', 'Integration Testing', fillcolor=testing_color)
                testing.node('qaReview', 'QA Review', shape='diamond', fillcolor=decision_color)
                testing.node('bugFix', 'Fix Bugs', fillcolor=testing_color)
                testing.node('userAcceptance', 'User Acceptance Testing', fillcolor=testing_color)
            # Deployment Phase
            with dot.subgraph(name='cluster_deployment') as deployment:
                deployment.attr(label='Deployment', style='filled', fillcolor=deployment_color, color='black')
                deployment.node('preRelease', 'Pre-Release Checklist', fillcolor=deployment_color)
                deployment.node('deployment_phase', 'Deployment to Production', fillcolor=deployment_color) # Renamed to avoid conflict
                deployment.node('postDeploy', 'Post-Deployment Verification', fillcolor=deployment_color)
                deployment.node('maintenance', 'Maintenance & Monitoring', fillcolor=deployment_color)
            # Edges - main flow
            dot.edge('start', 'requirements')
            dot.edge('requirements', 'userStories')
            dot.edge('userStories', 'poReview')
            dot.edge('poReview', 'planning_phase', label='Approve')
            dot.edge('poReview', 'userStories', label='Reject')
            dot.edge('planning_phase', 'designDocs')
            dot.edge('designDocs', 'designReview')
            dot.edge('designReview', 'architecture', label='Approve')
            dot.edge('designReview', 'designRevision', label='Reject')
            dot.edge('designRevision', 'designReview')
            dot.edge('architecture', 'generateCode') # Fixed node ID casing
            dot.edge('generateCode', 'codeReview') # Fixed node ID casing
            dot.edge('codeReview', 'securityScan', label='Approve')
            dot.edge('codeReview', 'codeFix', label='Reject')
            dot.edge('codeFix', 'codeReview')
            dot.edge('securityScan', 'securityFix')
            dot.edge('securityFix', 'testCases')
            dot.edge('testCases', 'unitTests')
            dot.edge('unitTests', 'integrationTests')
            dot.edge('integrationTests', 'qaReview')
            dot.edge('qaReview', 'userAcceptance', label='Approve')
            dot.edge('qaReview', 'bugFix', label='Reject')
            dot.edge('bugFix', 'qaReview')
            dot.edge('userAcceptance', 'preRelease',level='Approve')
            dot.edge('userAcceptance', 'testCases',level='Reject')
            dot.edge('preRelease', 'deployment_phase')
            dot.edge('deployment_phase', 'postDeploy')
            dot.edge('postDeploy', 'maintenance')
            dot.edge('maintenance', 'start') # Example cycle back to start

        else:
            dot.node("START", "START"); dot.node("unknown", f"Unknown Use Case:\n{usecase}"); dot.node("END", "END")
            dot.edges([("START", "unknown"), ("unknown", "END")])
        return dot.source

    def render_dot_with_quickchart(self, dot_string: str, format: str = 'svg'):
        """
        Sends the DOT string to QuickChart.io API and returns the image content.
        (This function remains the same - uses QuickChart)
        """
        quickchart_url = "https://quickchart.io/graphviz"
        payload = {'graph': dot_string, 'format': format}
        headers = {'Content-Type': 'application/json'}
        try:
            response = requests.post(quickchart_url, headers=headers, json=payload, timeout=30)
            if response.status_code == 200:
                return response.text if format == 'svg' else response.content
            else:
                st.error(f"QuickChart API request failed (Status {response.status_code}):")
                try: error_detail = response.json(); st.error(f"API Error: {error_detail.get('error', response.text)}")
                except json.JSONDecodeError: st.error(f"Response: {response.text[:500]}...")
                return None
        except requests.exceptions.Timeout: st.error("Network timeout connecting to QuickChart."); return None
        except requests.exceptions.RequestException as e: st.error(f"Network error connecting to QuickChart: {e}"); return None
        except Exception as e: st.error(f"An unexpected error occurred during QuickChart rendering: {e}"); return None

    def load_streamlit_ui(self):
        """Load and configure the Streamlit UI with user controls and graph diagram."""
        
        page_title = self.config.get_page_title()

        
        try:
            # Try to get logo from Config class
            logo = self.config.get_logo()
        except AttributeError:
            logo = "☁️" # Default cloud icon
            logger.warning("Config class does not have a 'get_logo' method. Using default logo.")
            
   
        st.set_page_config(page_title=f"{page_title}", layout="wide")
        



        if "session_initialized" not in st.session_state:
            self.initialize_session()
            st.session_state.session_initialized = True # Mark as initialized

        with st.sidebar:
            st.subheader("Configuration")
            try:
                # Use methods from the imported/instantiated Config class
                llm_options = self.config.get_llm_options()
                usecase_options = self.config.get_usecase_options()
                
                if not llm_options: llm_options = ["LLM options not found in config"]
                if not usecase_options: usecase_options = ["Use cases not found in config"]
            except Exception as e:
                st.error(f"Error reading options from config: {e}")
                llm_options = ["Error loading LLMs"]
                usecase_options = ["Error loading use cases"]


           
            self.user_controls["selected_llm"] = st.selectbox(
                "Select LLM", llm_options, help="Choose the language model provider."
            )
            
            if self.user_controls["selected_llm"] == "Groq":
                model_options = self.config.get_groq_model_options()
                self.user_controls["selected_groq_model"] = st.selectbox("Select Model", model_options)
                st.session_state.GROQ_API_KEY = st.text_input(
                    "GROQ API Key", type="password", value=st.session_state.get("GROQ_API_KEY", ""),
                    help="Enter your Groq API key."
                )
                self.user_controls["GROQ_API_KEY"] = st.session_state.GROQ_API_KEY
                if not self.user_controls["GROQ_API_KEY"]: st.warning("⚠️ Please enter your GROQ API key.")

            elif self.user_controls["selected_llm"] == "Google":
                model_options = self.config.get_google_model_options()
                self.user_controls["selected_google_genai_model"] = st.selectbox("Select Model", model_options)
                st.session_state.GOOGLE_API_KEY = st.text_input(
                    "Google API Key", type="password", value=st.session_state.get("GOOGLE_API_KEY", ""),
                    help="Enter your Google API key."
                )
                self.user_controls["GOOGLE_API_KEY"] = st.session_state.GOOGLE_API_KEY
                if not self.user_controls["GOOGLE_API_KEY"]: st.warning("⚠️ Please enter your Google API key.")

            elif self.user_controls["selected_llm"] == "OpenAI":
                model_options = self.config.get_openai_model_options()
                self.user_controls["selected_openai_model"] = st.selectbox("Select Model", model_options)
                st.session_state.OPENAI_API_KEY = st.text_input(
                    "OpenAI API Key", type="password", value=st.session_state.get("OPENAI_API_KEY", ""),
                    help="Enter your OpenAI API key."
                )
                self.user_controls["OPENAI_API_KEY"] = st.session_state.OPENAI_API_KEY
                if not self.user_controls["OPENAI_API_KEY"]: st.warning("⚠️ Please enter your OpenAI API key.")


            # --- Use Case Selection ---
            self.user_controls["selected_usecase"] = st.selectbox(
                "Select Use Case", usecase_options, help="Choose the application use case."
            )

             # --- Tool-specific API Keys (like Tavily) ---
            if self.user_controls.get("selected_usecase") in ["Chatbot with Tool", "Blog Generation"]:
                st.session_state.TAVILY_API_KEY = st.text_input(
                    "Tavily API Key", type="password", value=st.session_state.get("TAVILY_API_KEY", ""),
                    help="Enter your Tavily API key (required for tool use)."
                )
                self.user_controls["TAVILY_API_KEY"] = st.session_state.TAVILY_API_KEY
                if self.user_controls["TAVILY_API_KEY"]:
                     os.environ["TAVILY_API_KEY"] = self.user_controls["TAVILY_API_KEY"]
                else:
                     st.warning("⚠️ Please enter your Tavily API key for this use case.")

            # --- Reset Button ---
            if st.button("Reset Session", help="Clear all inputs and reset the session."):
                keys_to_delete = list(st.session_state.keys())
                for key in keys_to_delete: del st.session_state[key]
                st.success("Session reset successfully!")
                st.rerun()

            # --- Graph Display Area ---
            # (This section remains the same - calls create_graph_diagram and render_dot_with_quickchart)
            st.subheader("Graph Structure")
            selected_usecase = self.user_controls.get("selected_usecase")
            if selected_usecase:
                try:
                    graph_dot_string = self.create_graph_diagram(selected_usecase)
                    if graph_dot_string:
                        with st.spinner("Rendering graph via QuickChart API..."):
                             svg_output = self.render_dot_with_quickchart(graph_dot_string, format='svg')
                        if svg_output:
                            st.image(svg_output, use_container_width=True)
                            st.caption("Graph rendered by QuickChart.io (Static SVG)")
                        else:
                            st.warning("Could not render graph using the web service.")
                    else:
                         st.error(f"Failed to generate graph DOT string for: {selected_usecase}")
                except Exception as e:
                    st.error(f"Failed to display graph component: {e}")
                    import traceback
                    st.error(traceback.format_exc())
            else:
                st.info("Select a use case to see its graph structure.")

    

        # Get selected LLM
        selected_llm = self.user_controls.get("selected_llm")

        model = "N/A"
        if selected_llm == "Groq":
            model = self.user_controls.get('selected_groq_model')
        elif selected_llm == "Google":
            model = self.user_controls.get('selected_google_genai_model')
        elif selected_llm == "OpenAI":
            model = self.user_controls.get('selected_openai_model')
        
        st.markdown(
            f"""
            <div style="background: linear-gradient(135deg, #1e1e2e 0%, #2d2d44 100%); 
                padding: 2rem; 
                border-radius: 15px; 
                box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
                margin-bottom: 2rem;">
            <div style="display: flex; align-items: center; gap: 20px; margin-bottom: 25px;">
                <svg xmlns="http://www.w3.org/2000/svg" width="60" height="60" viewBox="0 0 24 24" 
                style="filter: drop-shadow(0 2px 4px rgba(0,0,0,0.2));">
                <path fill="#4CAF50" d="M6.099 5.88H17.9c3.364 0 6.1 2.745 6.1 6.12s-2.736 6.12-6.099 6.12H6.1C2.736 18.12 0 15.375 0 12s2.736-6.12 6.099-6.12m5.419 9.487c.148.156.367.148.561.108h.002c.09-.073-.038-.166-.16-.254c-.074-.054-.145-.105-.166-.15c.068-.083-.132-.27-.289-.417a2 2 0 0 1-.15-.151c-.11-.12-.155-.273-.2-.427a1.6 1.6 0 0 0-.11-.297c-.304-.708-.653-1.41-1.143-2.01c-.315-.398-.674-.755-1.033-1.112c-.232-.23-.463-.46-.683-.701c-.226-.234-.362-.521-.499-.81c-.114-.24-.228-.482-.396-.693c-.507-.75-2.107-.955-2.342.105c0 .033-.01.054-.039.075a1.6 1.6 0 0 0-.342.334c-.238.332-.274.895.022 1.193l.001-.02c.01-.15.02-.29.139-.399c.228.198.576.268.841.12c.32.46.422 1.015.525 1.572c.085.464.17.93.382 1.341l.014.022c.124.208.25.419.41.6c.059.09.178.187.297.284c.157.128.314.256.329.366v.146c-.001.29-.002.59.184.83c.103.208-.15.418-.352.392a1 1 0 0 1-.354-.043c-.165-.04-.329-.08-.462-.003c-.038.04-.091.042-.145.043c-.064.002-.129.004-.167.07a.3.3 0 0 1-.045.066c-.042.051-.087.107-.033.149l.015-.011c.082-.063.16-.123.27-.085c-.014.082.039.103.092.125l.027.012a.4.4 0 0 1-.008.057c-.009.046-.017.09.018.13l.046-.056c.037-.046.073-.094.139-.11c.144.192.289.112.471.012c.206-.114.459-.253.81-.056c-.135-.007-.255.01-.345.121c-.023.025-.042.054-.002.087c.207-.135.294-.086.375-.04c.06.032.115.063.212.024l.07-.037c.155-.084.314-.17.499-.14c-.139.04-.188.127-.242.223a1 1 0 0 1-.094.143c-.021.021-.03.046-.007.082c.29-.024.4-.098.548-.197c.07-.047.15-.1.261-.157c.124-.076.248-.028.368.02c.13.05.255.1.371-.013c.037-.035.083-.035.129-.036l.05-.002c-.037-.194-.24-.191-.448-.189c-.24.003-.483.005-.475-.295c.222-.152.224-.415.226-.665q-.001-.09.005-.176c.163.092.336.163.508.234c.162.066.323.133.474.215c.157.254.404.59.732.568l.026-.074l.059.014c.086.021.178.045.223-.057m6.429-2.886a1.014 1.014 0 0 0 1.729-.715a1.01 1.01 0 0 0-1.013-1.01a1 1 0 0 0-.364.068l-.58-.848l-.405.278l.583.851a1.01 1.01 0 0 0 .05 1.376m-1.818-2.744a1.014 1.014 0 0 0 1.42-.615a1.008 1.008 0 0 0-.845-1.293a1.015 1.015 0 0 0-1.095.712a1.01 1.01 0 0 0 .52 1.196m0 5.867a1.015 1.015 0 0 0 1.42-.615a1.008 1.008 0 0 0-.845-1.293a1.015 1.015 0 0 0-1.095.712a1.01 1.01 0 0 0 .52 1.196m.932-3.586v-.503h-1.55a1 1 0 0 0-.218-.412l.583-.864l-.424-.28l-.583.863a1 1 0 0 0-.333-.06c-.268 0-.525.106-.714.294a1.002 1.002 0 0 0 1.047 1.655l.583.864l.42-.281l-.579-.864c.104-.119.178-.26.217-.412z"/>
                </svg>
                <h1 style="margin: 0; 
                    background: linear-gradient(135deg, #4CAF50 0%, #81C784 100%);
                    -webkit-background-clip: text;
                    -webkit-text-fill-color: transparent;
                    font-size: 2.5rem;
                    font-weight: 700;
                    letter-spacing: 0.5px;">
                Dynamic Multi-Agent Workflows with LangGraph
                </h1>
            </div>
            <div style="display: flex; 
                    gap: 30px; 
                    margin-top: 1rem; 
                    background: rgba(255,255,255,0.05);
                    padding: 1rem;
                    border-radius: 10px;">
                <div style="display: flex; align-items: center; gap: 8px;">
                <span style="color: #888;">Use Case:</span>
                <span style="color: #4CAF50; font-weight: 600;">{selected_usecase}</span>
                </div>
                <div style="display: flex; align-items: center; gap: 8px;">
                <span style="color: #888;">LLM:</span>
                <span style="color: #4CAF50; font-weight: 600;">{selected_llm}</span>
                </div>
                <div style="display: flex; align-items: center; gap: 8px;">
                <span style="color: #888;">Model:</span>
                <span style="color: #4CAF50; font-weight: 600;">{model}</span>
                </div>
            </div>
            </div>
            """,
            unsafe_allow_html=True
        )
        

        return self.user_controls

