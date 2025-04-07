import streamlit as st
from langchain_core.messages import HumanMessage, AIMessage
import logging
import json
from datetime import datetime
from .display_result_blog import DisplayBlogResult

logging.basicConfig(
    level=logging.INFO,  # Set the minimum log level to INFO
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s\n'  # Format for log messages
)

logger = logging.getLogger(__name__)

class DisplayResultStreamlit:
    def __init__(self, graph, with_message_history, config, usecase):
        self.graph = graph
        self.with_message_history = with_message_history
        self.config = config
        self.usecase = usecase
        self._initialize_session_state()
        self.session_history = self._get_session_history()

    def _initialize_session_state(self):
        """Initialize all session state variables."""
        defaults = {
            "current_session_id": None,
            "current_stage": "requirements",
        }
        for key, value in defaults.items():
            if key not in st.session_state:
                st.session_state[key] = value

    def _get_session_history(self):
        from langchain_community.chat_message_histories import ChatMessageHistory
        store = {}
        session_id = self.config["configurable"]["session_id"]
        if session_id not in store:
            store[session_id] = ChatMessageHistory()
        if st.session_state.current_session_id != session_id:
            st.session_state.current_session_id = session_id
        return store[session_id]

    def display_chat_history(self):
        """Display the chat history from the session."""
        for message in self.session_history.messages:
            role = "user" if isinstance(message, HumanMessage) else "assistant"
            with st.chat_message(role):
                st.markdown(message.content, unsafe_allow_html=True)

    def process_user_input(self):
        """Process user input and display results based on the use case."""
        st.write("Session State at start of process_user_input:", st.session_state) # Debugging

        if self.usecase == "Blog Generation":

            blog_display = DisplayBlogResult(self.graph, self.config)
            if st.session_state.current_stage == "requirements":
                if not st.session_state.blog_requirements_collected:
                    input_message = blog_display.collect_blog_requirements()
                    logger.info(f"\n\n-----------------------------: Entered main Display Collection of blog requirements:--------------------------------- {input_message}\n\n--------------------")
                    if input_message:
                        logger.info(f"\n\n-----------------------------: Entered main Display 1st If block input message:-----------------------------------------------------")
                        st.session_state.blog_requirements_collected = True
                        st.session_state.initial_input_message = input_message # Store the initial input
                        st.session_state.current_stage = "processing"  # Move to processing stage
                        st.rerun() # Trigger rerun to enter the processing stage

            elif st.session_state.current_stage == "processing":
                initial_input = st.session_state.get('initial_input_message')
                logger.info(f"\n\n-----------------------------: Entered main Display processing stage:-----------------------------------------------------\n\n")
                st.write("Initial Input being passed to process_graph_events:", initial_input) # Debugging
                blog_display.process_graph_events(initial_input) # Pass the stored input message
                logger.info(f"\n\n-----------------------------: Current stage after processing:{st.session_state.current_stage}-----------------------------------------------------\n\n")
                st.rerun()  # Trigger rerun to refresh the UI

            elif st.session_state.current_stage == "feedback":
                logger.info(f"\n\n-----------------------------: Entered main Display feedback stage:{st.session_state.current_stage}-----------------------------------------------------")
                st.write("Entering feedback stage in main loop")
                logger.info("Entering feedback stage in main loop")
                feedback_result = blog_display.process_feedback()
                st.write("Feedback Result from process_feedback:", feedback_result) # Debugging

                # Check if feedback has been submitted
                if st.session_state.get('feedback_result'):
                    if st.session_state['feedback_result'].approved:
                        st.session_state.current_stage = "complete"
                        st.rerun() # Trigger rerun to show completion
                    else:
                        st.session_state.current_stage = "processing_feedback"
                        st.rerun()
                

            elif st.session_state.current_stage == "processing_feedback":
                logger.info(f"\n\n-----------------------------: Entered main Display processing_feedback stage:{st.session_state.current_stage}-----------------------------------------------------")
                blog_display.process_graph_events(HumanMessage(content=json.dumps(st.session_state['feedback_result'].model_dump_json())))
                st.session_state.current_stage = "processing" # Go back to processing after sending feedback
                st.rerun()

            elif st.session_state.current_stage == "complete":
                logger.info(f"\n\n-----------------------------: Entered main Display complete stage:{st.session_state.current_stage}-----------------------------------------------------")
                st.success("✅ Blog generation complete!")
                if st.session_state.get("blog_content"):
                    st.markdown("### Final Blog Content:")
                    st.markdown(st.session_state["blog_content"])

        else:
            self._handle_chatbot_input()

    def _handle_chatbot_input(self):
        user_message = st.chat_input("Enter your message:")
        if user_message:
            self.session_history.add_user_message(user_message)
            with st.chat_message("user"):
                st.markdown(user_message, unsafe_allow_html=True)
            self._process_graph_stream(HumanMessage(content=user_message))

    def _process_graph_stream(self, input_message=None):
        with st.spinner("Processing..."):
            try:
                input_data = {"messages": [input_message]} if input_message else None
                for event in self.graph.stream(input_data, self.config):
                    logger.info(f"Graph event: {event}")
                    for node, state in event.items():
                        if "messages" in state and state["messages"]:
                            with st.chat_message("assistant"):
                                content = state["messages"][-1].content
                                st.markdown(content)
                            self.session_history.add_ai_message(content)
            except Exception as e:
                logger.error(f"Error in graph streaming: {e}")
                st.error(f"Error processing workflow: {e}")