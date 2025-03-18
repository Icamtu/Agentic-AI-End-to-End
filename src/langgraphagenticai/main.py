# src/langgraphagenticai/main.py
import streamlit as st
import uuid
from src.langgraphagenticai.ui.streamlitui.loadui import LoadStreamlitUI
from src.langgraphagenticai.LLMS.groqllm import GroqLLM
from src.langgraphagenticai.LLMS.geminillm import GoogleLLM
from src.langgraphagenticai.LLMS.chatgptllm import OpenaiLLM
from src.langgraphagenticai.graph.graph_builder import GraphBuilder
from src.langgraphagenticai.ui.streamlitui.display_result import DisplayResultStreamlit
from langchain_community.chat_message_histories import ChatMessageHistory
from langchain_core.chat_history import BaseChatMessageHistory
from langchain_core.runnables.history import RunnableWithMessageHistory
from langchain_core.messages import HumanMessage

# Store for session histories
store = {}

def get_session_history(session_id: str) -> BaseChatMessageHistory:
    """Retrieve or create a chat history for the given session ID."""
    if session_id not in store:
        store[session_id] = ChatMessageHistory()
    return store[session_id]

def load_langgraph_agenticai_app():
    """Loads and runs the LangGraph AgenticAI application with Streamlit UI."""
    ui = LoadStreamlitUI()
    user_controls = ui.load_streamlit_ui()

    if not user_controls:
        st.error("Error: Failed to load user controls from the UI.")
        return

    selected_llm = user_controls.get("selected_llm")
    if not selected_llm:
        st.info("Please select an LLM in the sidebar to proceed.")
        return

    # Validate API keys
    if selected_llm == "Groq" and not user_controls.get("GROQ_API_KEY"):
        st.warning("Please enter your Groq API key in the sidebar.")
        return
    elif selected_llm == "Google" and not user_controls.get("GOOGLE_API_KEY"):
        st.warning("Please enter your Google API key in the sidebar.")
        return
    elif selected_llm == "OpenAI" and not user_controls.get("OPENAI_API_KEY"):
        st.warning("Please enter your OpenAI API key in the sidebar.")
        return

    # Dynamic session ID using uuid
    if "session_id" not in st.session_state:
        st.session_state.session_id = str(uuid.uuid4())

    config = {"configurable": {"session_id": st.session_state.session_id}}

    st.markdown("### Chat")

    # Display chat history
    session_history = get_session_history(st.session_state.session_id)
    for message in session_history.messages:
        role = "user" if isinstance(message, HumanMessage) else "assistant"
        with st.chat_message(role):
            st.markdown(message.content)

    user_message = st.chat_input("Enter your message:")

    if user_message:
        try:
            session_history.add_user_message(user_message)
            with st.chat_message("user"):
                st.markdown(user_message)

            if selected_llm == "Groq":
                llm_config = GroqLLM(user_controls_input=user_controls)
            elif selected_llm == "Google":
                llm_config = GoogleLLM(user_controls_input=user_controls)
            elif selected_llm == "OpenAI":
                llm_config = OpenaiLLM(user_controls_input=user_controls)
            else:
                st.error(f"Error: Unsupported LLM selected: '{selected_llm}'")
                return

            model = llm_config.get_llm_model()
            if not model:
                st.error("Error: LLM model could not be initialized.")
                return

            usecase = user_controls.get("selected_usecase")
            if not usecase:
                st.error("Error: No use case selected.")
                return

            graph_builder = GraphBuilder(model)
            graph = graph_builder.setup_graph(usecase)

            with_message_history = RunnableWithMessageHistory(
                graph,
                get_session_history,
                input_messages_key="messages",
                history_messages_key="messages"
            )

            with st.spinner("Processing..."):
                input_data = {"messages": [HumanMessage(content=user_message)]}
                response = with_message_history.invoke(input_data, config=config)

                # Pass the full response to DisplayResultStreamlit
                display = DisplayResultStreamlit(usecase, graph, user_message, response)
                with st.chat_message("assistant"):
                    assistant_response = display.display_result_on_ui()
                session_history.add_ai_message(assistant_response)

            st.session_state.IsFetchButtonClicked = False

        except Exception as e:
            st.error(f"Error occurred: {e}")

if __name__ == "__main__":
    load_langgraph_agenticai_app()