# src/langgraphagenticai/main.py
import streamlit as st
import uuid
import logging
import os
from langchain_core.messages import HumanMessage, AIMessage
from langchain_community.chat_message_histories import ChatMessageHistory
from langchain_core.chat_history import BaseChatMessageHistory
from langchain_core.runnables.history import RunnableWithMessageHistory
from src.langgraphagenticai.ui.streamlitui.loadui import LoadStreamlitUI
from src.langgraphagenticai.ui.streamlitui.display_result import DisplayResultStreamlit
from src.langgraphagenticai.LLMS.groqllm import GroqLLM
from src.langgraphagenticai.LLMS.geminillm import GoogleLLM
from src.langgraphagenticai.LLMS.chatgptllm import OpenaiLLM
from src.langgraphagenticai.graph.graph_builder import GraphBuilder

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

store = {}

def get_session_history(session_id: str) -> BaseChatMessageHistory:
    if session_id not in store:
        store[session_id] = ChatMessageHistory()
    return store[session_id]

def load_langgraph_agenticai_app():
    ui = LoadStreamlitUI()
    user_controls = ui.load_streamlit_ui()
    display_result = DisplayResultStreamlit()

    if not user_controls:
        st.error("Error: Failed to load user controls from the UI.")
        return

    selected_llm = user_controls.get("selected_llm")
    if not selected_llm:
        st.info("Please select an LLM in the sidebar to proceed.")
        return

    tavily_api_key = user_controls.get("TAVILY_API_KEY", st.session_state.get("TAVILY_API_KEY", os.getenv("TAVILY_API_KEY", "")))
    if not tavily_api_key and user_controls.get("selected_usecase") in ["Blog Generation", "Chatbot with Tool"]:
        st.warning("Tavily API key not found. Web search will be skipped.")
    else:
        st.session_state["TAVILY_API_KEY"] = tavily_api_key
        os.environ["TAVILY_API_KEY"] = tavily_api_key

    if selected_llm == "Groq" and not user_controls.get("GROQ_API_KEY"):
        st.warning("Please enter your Groq API key in the sidebar.")
        return
    elif selected_llm == "Google" and not user_controls.get("GOOGLE_API_KEY"):
        st.warning("Please enter your Google API key in the sidebar.")
        return
    elif selected_llm == "OpenAI" and not user_controls.get("OPENAI_API_KEY"):
        st.warning("Please enter your OpenAI API key in the sidebar.")
        return

    if "session_id" not in st.session_state:
        st.session_state.session_id = str(uuid.uuid4())
    if "thread_id" not in st.session_state:
        st.session_state.thread_id = str(uuid.uuid4())
    if "graph_state" not in st.session_state:
        st.session_state.graph_state = None
    if "waiting_for_feedback" not in st.session_state:
        st.session_state.waiting_for_feedback = False
    if "blog_requirements_collected" not in st.session_state:
        st.session_state.blog_requirements_collected = False
    if "current_usecase" not in st.session_state:
        st.session_state.current_usecase = None
    if "outline_feedback" not in st.session_state:
        st.session_state.outline_feedback = None
    if "draft_feedback" not in st.session_state:
        st.session_state.draft_feedback = None
    if "draft_displayed" not in st.session_state:
        st.session_state.draft_displayed = False
    if "outline_displayed" not in st.session_state:
        st.session_state.outline_displayed = False

    config = {"configurable": {"session_id": st.session_state.session_id, "thread_id": st.session_state.thread_id, "recursion_limit": 50}}
    logger.info(f"Session ID: {st.session_state.session_id}, Thread ID: {st.session_state.thread_id}")

    st.markdown("### Chat")
    session_history = get_session_history(st.session_state.session_id)
    for message in session_history.messages:
        role = "user" if isinstance(message, HumanMessage) else "assistant"
        with st.chat_message(role):
            st.markdown(message.content, unsafe_allow_html=True)

    usecase = user_controls.get("selected_usecase")
    if not usecase:
        st.error("Error: No use case selected.")
        return

    if st.session_state.current_usecase != usecase:
        logger.info(f"Use case changed to: {usecase}. Resetting session state.")
        st.session_state.waiting_for_feedback = False
        st.session_state.blog_requirements_collected = False
        st.session_state.current_usecase = usecase
        st.session_state.draft_displayed = False
        st.session_state.outline_displayed = False
        session_history.clear()
        if "graph" in st.session_state:
            del st.session_state.graph
        if "with_message_history" in st.session_state:
            del st.session_state.with_message_history

    try:
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

        if "graph" not in st.session_state:
            graph_builder = GraphBuilder(model)
            graph = graph_builder.setup_graph(usecase)
            with_message_history = RunnableWithMessageHistory(
                graph,
                get_session_history,
                input_messages_key="messages",
                history_messages_key="messages"
            )
            st.session_state.graph = graph
            st.session_state.with_message_history = with_message_history
        if not st.session_state.graph:
            raise ValueError("Graph initialization failed")

    except Exception as e:
        logger.error(f"Error initializing graph: {e}")
        st.error(f"Failed to initialize graph: {e}. Please check your configuration and try again.")
        return

    if usecase == "Blog Generation":
        if st.session_state.waiting_for_feedback:
            if st.session_state.graph_state:
                latest_state = st.session_state.graph_state.values
                
                # Display draft content only if not already displayed
                if "completed_sections" in latest_state and not st.session_state.get("draft_displayed"):
                    with st.chat_message("assistant"):
                        draft_content = "\n\n".join(latest_state["completed_sections"])
                        st.markdown("### Generated Draft")
                        st.markdown(draft_content)
                        st.session_state.draft_displayed = True
                        display_result.display_result(latest_state, usecase)

            # Determine which review stage we're in
            current_node = st.session_state.graph_state.next[0] if st.session_state.graph_state.next else None
            if current_node == "outline_review":
                st.write("Review the outline:")
                col1, col2 = st.columns(2)
                with col1:
                    if st.button("Looks good", key="outline_approve"):
                        st.session_state.outline_feedback = "approved"
                        st.session_state.waiting_for_feedback = False
                        st.session_state.outline_displayed = False  # Reset for next stage
                        logger.info("Outline approved via button")
                with col2:
                    if st.button("Add more details", key="outline_reject"):
                        st.session_state.outline_feedback = "add_more_details"
                        st.session_state.waiting_for_feedback = False
                        logger.info("Outline rejected via button, requesting more details")
            elif current_node == "draft_review":
                st.write("Review the draft:")
                col1, col2 = st.columns(2)
                with col1:
                    if st.button("Looks good", key="draft_approve"):
                        st.session_state.draft_feedback = "approved"
                        st.session_state.waiting_for_feedback = False
                        st.session_state.draft_displayed = False  # Reset display flag
                        logger.info("Draft approved via button")
                with col2:
                    if st.button("Add more details", key="draft_reject"):
                        st.session_state.draft_feedback = "add_more_details"
                        st.session_state.waiting_for_feedback = False
                        st.session_state.draft_displayed = False  # Reset display flag
                        logger.info("Draft rejected via button, requesting more details")

            # Process feedback if provided
            if not st.session_state.waiting_for_feedback:
                graph = st.session_state.get("graph")
                if not graph:
                    logger.error("Graph not initialized in session state")
                    st.error("Error: Workflow graph not initialized.")
                    return
                with st.spinner("Processing feedback..."):
                    for event in graph.stream(None, config=config):
                        logger.info(f"Graph event: {event}")
                        for node, state in event.items():
                            # Update state handling for outline display
                            if "messages" in state and state["messages"]:
                                with st.chat_message("assistant"):
                                    if "sections" in state:
                                        # Force outline display when sections are available
                                        display_result.display_result({
                                            "sections": state["sections"],
                                            "messages": state["messages"]
                                        }, usecase)
                                    else:
                                        display_result.display_result(state, usecase)
                                session_history.add_ai_message(state["messages"][-1].content)
                        graph_state = graph.get_state(config)
                        logger.info(f"Graph state after event: {graph_state}")
                        if graph_state.next and graph_state.next[0] in ["outline_review", "draft_review"]:
                            st.session_state.waiting_for_feedback = True
                            st.session_state.graph_state = graph_state
                            logger.info(f"Graph paused at: {graph_state.next}")
                            break
                        elif not graph_state.next:
                            logger.info("Blog generation completed")
                            st.session_state.blog_requirements_collected = False
                            with st.chat_message("assistant"):
                                st.markdown("✅ Blog generation completed!")
                            if st.button("New Blog Generation", key="new_blog_button"):
                                logger.info("Starting new blog generation")
                                session_history.clear()
                                st.session_state.graph_state = None
                                st.session_state.waiting_for_feedback = False
                                st.session_state.outline_feedback = None
                                st.session_state.draft_feedback = None
                                st.rerun()
                            break

        elif not st.session_state.blog_requirements_collected:
            st.markdown("### Blog Requirements")
            with st.form("blog_requirements_form"):
                topic = st.text_input("Topic", placeholder="e.g., The Future of AI in Healthcare")
                objective = st.radio("Objective", ["Informative", "Persuasive", "Storytelling", "Other"])
                if objective == "Other":
                    objective = st.text_input("Specify Objective", placeholder="Enter custom objective")
                target_audience = st.radio("Target Audience", ["Beginners", "Experts", "General Audience", "Other"])
                if target_audience == "Other":
                    target_audience = st.text_input("Specify Target Audience", placeholder="Enter custom audience")
                tone_style = st.radio("Tone & Style", ["Formal", "Casual", "Technical", "Engaging", "Other"])
                if tone_style == "Other":
                    tone_style = st.text_input("Specify Tone & Style", placeholder="Enter custom tone and style")
                word_count = st.number_input("Word Count", min_value=100, max_value=5000, value=1000, step=100)
                structure = st.text_area("Structure", placeholder="e.g., Introduction, Key Points, Conclusion")
                submit_button = st.form_submit_button("Submit Blog Requirements")

            if submit_button:
                if not topic or not objective or not target_audience or not tone_style or not structure:
                    st.error("Please fill in all required fields.")
                    return
                
                # Format user input as a single line
                user_message = f"Topic: {topic} Objective: {objective} Target Audience: {target_audience} Tone & Style: {tone_style} Word Count: {word_count} Structure: {structure}"
                
                logger.info(f"Blog requirements submitted: {user_message}")
                session_history.add_user_message(user_message)
                with st.chat_message("user"):
                    st.markdown(user_message)
                st.session_state.blog_requirements_collected = True

                with st.spinner("Generating outline..."):
                    input_data = {"messages": [HumanMessage(content=user_message)]}
                    graph = st.session_state.graph
                    if not graph:
                        logger.error("Graph not initialized before streaming initial input")
                        st.error("Error: Workflow graph not initialized.")
                        return
                    for event in graph.stream(input_data, config=config):
                        logger.info(f"Graph event: {event}")
                        for node, state in event.items():
                            if "messages" in state and state["messages"]:
                                with st.chat_message("assistant"):
                                    display_result.display_result(state, usecase)
                                session_history.add_ai_message(state["messages"][-1].content)
                        graph_state = graph.get_state(config)
                        if graph_state.next and graph_state.next[0] in ["outline_review", "draft_review"]:
                            st.session_state.waiting_for_feedback = True
                            st.session_state.graph_state = graph_state
                            break
                    st.rerun()

        # Initialize session state for draft display tracking
        if "draft_displayed" not in st.session_state:
            st.session_state.draft_displayed = False

    else:
        user_message = st.chat_input("Enter your message:")
        if user_message:
            try:
                logger.info(f"User message: {user_message}")
                session_history.add_user_message(user_message)
                with st.chat_message("user"):
                    st.markdown(user_message, unsafe_allow_html=True)

                with st.spinner("Processing..."):
                    input_data = {"messages": [HumanMessage(content=user_message)]}
                    logger.info(f"Streaming graph with input: {input_data}")
                    for event in st.session_state.with_message_history.stream(input_data, config=config):
                        logger.info(f"Graph event: {event}")
                        for node, state in event.items():
                            if "messages" in state and state["messages"]:
                                with st.chat_message("assistant"):
                                    display_result.display_result(state, usecase)
                                session_history.add_ai_message(state["messages"][-1].content)
                        graph_state = st.session_state.graph.get_state(config)
                        logger.info(f"Graph state after event: {graph_state}")
                        if not graph_state.next:
                            logger.info("Graph completed execution")
                            break
            except Exception as e:
                logger.error(f"Error occurred: {e}")
                st.error(f"Error occurred: {e}")

if __name__ == "__main__":
    load_langgraph_agenticai_app()