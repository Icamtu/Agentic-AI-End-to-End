import streamlit as st
from src.langgraphagenticai.ui.streamlitui.loadui import LoadStreamlitUI
from src.langgraphagenticai.LLMS.groqllm import GroqLLM
from src.langgraphagenticai.LLMS.geminillm import GoogleLLM
from src.langgraphagenticai.LLMS.chatgptllm import OpenaiLLM
from src.langgraphagenticai.graph.graph_builder import GraphBuilder
from src.langgraphagenticai.ui.streamlitui.display_result import DisplayResultStreamlit

def load_langgraph_agenticai_app():
    """
    Loads and runs the LangGraph AgenticAI application with Streamlit UI.
    This function initializes the UI, handles user input, configures the LLM model,
    sets up the graph based on the selected use case, and displays the output while 
    implementing exception handling for robustness.
    """
    # Load UI (sidebar configuration)
    ui = LoadStreamlitUI()
    user_controls = ui.load_streamlit_ui()

    if not user_controls:
        st.error("Error: Failed to load user controls from the UI.")
        return

    if not user_controls.get("selected_llm"):
        st.error("Please select an LLM in the sidebar.")
        return


    st.markdown("### Input")
    user_message = st.chat_input("Enter your message:")

    if user_message:
        try:
            # Configure LLM based on selected_llm
            if user_controls["selected_llm"] == "Groq":
                llm_config = GroqLLM(user_controls_input=user_controls)
            elif user_controls["selected_llm"] == "Google":
                llm_config = GoogleLLM(user_controls_input=user_controls)
            elif user_controls["selected_llm"] == "OpenAI":
                llm_config = OpenaiLLM(user_controls_input=user_controls)
            else:
                st.error("Error: Unsupported LLM selected.")
                return

            model = llm_config.get_llm_model()
            if not model:
                st.error("Error: LLM model could not be initialized. Check your API key.")
                return

            # Get the selected use case
            usecase = user_controls.get("selected_usecase")
            if not usecase:
                st.error("Error: No use case selected.")
                return

            # Set up the graph
            graph_builder = GraphBuilder(model)
            try:
                graph = graph_builder.setup_graph(usecase)
                # Display the result using DisplayResultStreamlit
                DisplayResultStreamlit(usecase, graph, user_message).display_result_on_ui()
                # Reset IsFetchButtonClicked if it was set (though not used in this UI yet)
                st.session_state.IsFetchButtonClicked = False
            except Exception as e:
                st.error(f"Error: Graph setup failed - {e}")
                return

        except Exception as e:
            st.error(f"Error occurred: {e}")

if __name__ == "__main__":
    load_langgraph_agenticai_app()