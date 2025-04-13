import streamlit as st
from langchain_core.messages import HumanMessage, AIMessage
import logging
import json
from datetime import datetime
import base64
from src.langgraphagenticai.ui.streamlitui.display_result_blog import DisplayBlogResult

import logging
import functools
import time


logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(), # Logs to console
        # logging.FileHandler("app.log") # Optional: Logs to a file
    ]
)

logger = logging.getLogger(__name__)

def log_entry_exit(func):
    """
    A decorator that logs the entry and exit of a function.
    It also logs the execution time.
    """
    @functools.wraps(func) # Preserves function metadata (like __name__, __doc__)
    def wrapper(*args, **kwargs):
        func_name = func.__name__
        logger.info(f"\n{'='*20}\n:Entering: {func_name}\n{'='*20}\n")
        start_time = time.perf_counter() # More precise than time.time()
        try:
            result = func(*args, **kwargs)
            end_time = time.perf_counter()
            execution_time = end_time - start_time
            logger.info(f"\n{'='*20}\n:Exiting: {func_name} (Execution Time: {execution_time:.4f} seconds)\n{'='*20}\n")
            return result
        except Exception as e:
            end_time = time.perf_counter()
            execution_time = end_time - start_time
            logger.error(f"{'='*20}:Error Exception in {func_name}: {e} (Execution Time: {execution_time:.4f} seconds)", exc_info=True)
            # Re-raise the exception after logging
            raise
    return wrapper

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

        blog_defaults = {
            "initial_input_message": None, # To store the initial blog requirements
            "waiting_for_feedback": False,
            "blog_requirements_collected": False,
            "content_displayed": False,
            "graph_state": None,
            "feedback": "",
            "blog_content": None,
            "blog_generation_complete": False,
            "feedback_submitted": False,  # Track if feedback was submitted
            "processing_complete": False,  # Track if processing is complete
            "feedback_result": None,
            "generated_draft": None,
            "synthesizer_output_processed": False
        }
        for key, value in blog_defaults.items():
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
    @log_entry_exit
    def display_chat_history(self):
        """Display the chat history from the session."""
        for message in self.session_history.messages:
            role = "user" if isinstance(message, HumanMessage) else "assistant"
            with st.chat_message(role):
                st.markdown(message.content, unsafe_allow_html=True)

    @log_entry_exit
    def process_user_input(self):
        """Process user input and display results based on the use case."""
        # st.write("DEBUG: Session State at start of process_user_input:", st.session_state) # Uncomment for Debugging

        if self.usecase == "Blog Generation":
            blog_display = DisplayBlogResult(self.graph, self.config)

            # Stage 1: Collect Requirements
            if st.session_state.current_stage == "requirements":
                if not st.session_state.blog_requirements_collected:
                    input_message = blog_display.collect_blog_requirements()
                    # logger.info(f"DEBUG: Requirements collected: {input_message}") # Uncomment for Debugging
                    if input_message:
                        st.session_state.blog_requirements_collected = True
                        st.session_state.initial_input_message = input_message # Store the initial input
                        st.session_state.current_stage = "processing"
                        st.rerun()

            # Stage 2: Initial Processing
            elif st.session_state.current_stage == "processing":
                logger.info("Entering processing stage.")
                initial_input = st.session_state.get('initial_input_message')
                if initial_input:
                    input_data = {"messages": [initial_input]}
                    logger.info(f"DEBUG: Calling process_graph_events with initial input: {input_data}") # Uncomment for Debugging
                    blog_display.process_graph_events(input_data)
                else:
                    logger.error("Processing stage reached but initial input message is missing.")
                    st.error("Error: Initial requirements not found. Please start over.")
                    st.session_state.current_stage = "requirements" # Reset to start
                    st.rerun()

            # Stage 3: Handle Feedback
            elif st.session_state.current_stage == "feedback":
                logger.info(f"Entering feedback stage. Submitted: {st.session_state.get('feedback_submitted', False)}")
                # Display draft if available
                if st.session_state.get("generated_draft"):
                     if not st.session_state.get("feedback_ui_displayed", False):
                        st.session_state["feedback_ui_displayed"] = True # Mark UI as displayed
                     feedback_result = blog_display.process_feedback() # Display feedback form and get result on submit
                else:
                     st.warning("Waiting for draft to be generated before collecting feedback.")
                     # Potentially add a spinner or status indicator here

                # Check if feedback was submitted via button clicks in process_feedback
                if st.session_state.get("feedback_submitted"):
                    logger.info("Feedback form submitted.")
                    feedback_result = st.session_state.get('feedback_result')
                    st.session_state["feedback_submitted"] = False # Reset flag immediately
                    st.session_state["feedback_ui_displayed"] = False # Reset UI display flag

                    if feedback_result:
                        if feedback_result.approved:
                            logger.info("Feedback: Approved")
                            st.session_state["blog_content"] = st.session_state.get("generated_draft")
                            st.session_state["generated_draft"] = None # Clear draft
                            st.session_state.current_stage = "complete"
                            st.session_state['feedback_result'] = None # Clear result
                            st.rerun()
                        else:
                            # Revision requested
                            logger.info(f"Feedback: Revision requested - comments: {feedback_result.comments}")
                            st.session_state["feedback"] = feedback_result.comments
                            st.session_state.current_stage = "processing_feedback"
                            st.session_state['feedback_result'] = None # Clear result
                            st.session_state["generated_draft"] = None # Clear draft
                            st.session_state["completed_sections"]=None # Clear completed sections
                            logger.info(f"{'='*20}\n:session state after revision request:\n {st.session_state}{'='*20}")
                            st.rerun()
                    else:
                         logger.warning("Feedback submitted but no result found in session state.")


            # Stage 4: Process Feedback (Resume Graph)
            elif st.session_state.current_stage == "processing_feedback":
                logger.info("Entering processing_feedback stage.")
                feedback_comment = st.session_state.get("feedback")
                if feedback_comment is not None: # Check if feedback exists
                    # Create the feedback message
                    feedback_message = HumanMessage(content=json.dumps({
                        "approved": False,
                        "comments": feedback_comment
                    }))
                    # Prepare input data for resuming the graph
                    # We only need to pass the new message. LangGraph uses the config
                    # (session_id/thread_id) and its checkpointer to load the state.
                    input_data = {"messages": [feedback_message]}
                    logger.info(f"Resuming graph with feedback message: {feedback_message.content}")
                    st.session_state["feedback"] = "" # Clear feedback after using it

                    # Call the unified process_graph_events to resume
                    blog_display.process_graph_events(input_data=input_data)
                else:
                     logger.error("Processing feedback stage reached but feedback comments are missing.")
                     st.error("Error: Feedback comments not found. Please provide feedback again.")
                     st.session_state.current_stage = "feedback" # Go back to feedback stage
                     st.rerun()

            # Stage 5: Completion
            elif st.session_state.current_stage == "complete":
                logger.info("Entering complete stage.")
                st.success("✅ Blog generation complete!")
                if st.session_state.get("blog_content"):
                    st.markdown("### Final Blog Content:")
                    st.markdown(st.session_state["blog_content"])
                    blog_display._download_blog_content(st.session_state["blog_content"]) # Add download button
                else:
                    st.warning("Final blog content is not available.")

        # Handle other use cases (non-blog)
        else:
            self._handle_chatbot_input()
    @log_entry_exit
    def _download_blog_content(self, blog_content):
        # (Keep this method as it was)
        if blog_content:
            import base64 # Ensure import
            b64 = base64.b64encode(blog_content.encode()).decode()
            # Use a timestamp or unique ID in filename if needed
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"blog_content_{timestamp}.md" # Use .md extension for markdown
            href = f'<a href="data:text/markdown;base64,{b64}" download="{filename}">⬇️ Download Blog Content (Markdown)</a>'
            st.markdown(href, unsafe_allow_html=True)

    @log_entry_exit
    def _handle_chatbot_input(self):
        # (Keep this method as it was)
        user_message = st.chat_input("Enter your message:")
        if user_message:
            # Use the RunnableWithMessageHistory directly if available
            if hasattr(self, 'with_message_history') and self.with_message_history:
                 with st.chat_message("user"):
                      st.markdown(user_message, unsafe_allow_html=True)
                 with st.chat_message("assistant"):
                      with st.spinner("Processing..."):
                           response = self.with_message_history.invoke(
                                {"messages": [HumanMessage(content=user_message)]},
                                self.config # Pass the config containing session/thread ID
                           )
                           # Extract the last message assuming it's the AI response
                           ai_message = response.get("messages", [])[-1]
                           if ai_message:
                                st.markdown(ai_message.content)
                           else:
                                st.markdown("Sorry, I couldn't process that.")
            else:
                 # Fallback or handle error if RunnableWithMessageHistory isn't set up
                 st.error("Chat history handling not configured correctly.")


    @log_entry_exit
    def _process_graph_stream(self, input_message=None):
         # This specific method might be less relevant if using RunnableWithMessageHistory
         # Keep it for potential fallback or direct graph streaming if needed
         with st.spinner("Processing..."):
            try:
                input_data = {"messages": [input_message]} if input_message else None
                for event in self.graph.stream(input_data, self.config):
                    logger.info(f"Graph event: {event}")
                    for node, state in event.items():
                        if "messages" in state and state["messages"]:
                            # Assuming the last message is the one to display
                            last_message = state["messages"][-1]
                            # Check if it's an AI message before adding to history/displaying
                            if isinstance(last_message, AIMessage):
                                 with st.chat_message("assistant"):
                                      st.markdown(last_message.content)
                                # Add to history (if managing history manually - less likely now)
                                # self.session_history.add_ai_message(last_message.content)
            except Exception as e:
                logger.error(f"Error in graph streaming: {e}")
                st.error(f"Error processing workflow: {e}")
