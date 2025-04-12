import streamlit as st
from langchain_core.messages import HumanMessage, AIMessage
import logging
import json
from datetime import datetime
import base64

# Assuming display_result_blog.py is in the same directory or accessible in your Python path
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
                logger.info(f"\n{'*'*20}Entered to main Display processing stage{'*'*20}\n")
                logger.info(f"\n{'*'*20}st.session_state[feedback] is {st.session_state["feedback"]}{'*'*20}\n")
                initial_input = st.session_state.get('initial_input_message')
                st.write("\n{'='*20}:Initial Input being passed to process_graph_events:{'='*20}\n", initial_input) # Debugging
                logger.info(f"\n{'='*20}:Initial Input being passed to process_graph_events:{'='*20}\n{ initial_input}") # Debugging
                blog_display.process_graph_events(initial_input) 

            elif st.session_state.current_stage == "feedback":
                st.write("Entering feedback stage in main loop")
                logger.info(f"Entering feedback stage in main loop: submission status {st.session_state['feedback_submitted']}")
                if not st.session_state["feedback_submitted"]:
                    logger.info(f"{"="*20}Inside not feedback_submitted If Block{"="*20}")
                    feedback_result = blog_display.process_feedback()
                    st.write("Feedback Result from process_feedback:", feedback_result) # Debugging
                else:
                    logger.info(f"\n\n{"="*20}Inside feedback_submitted else Block{"="*20}\n\n")
                    # Feedback has been submitted (either approved or needs revision)
                    feedback_result = st.session_state.get('feedback_result')
                    logger.info(f"\n\n{"="*20}feedback_result.approved: {feedback_result.approved}{"="*20}\n\n")
                    if feedback_result.approved==True:
                        logger.info(f"\n\n{"="*20}Inside feedback_submitted if approved Block{"="*20}\n\n")
                        final_draft = st.session_state.get("generated_draft")
                        st.session_state["blog_content"] = final_draft
                        st.session_state["generated_draft"] = None # Clear the draft after approval
                        st.session_state.current_stage = "complete" # Move to complete stage
                        feedback_result.approved = None # Clear the feedback result
                        # st.session_state["feedback_submitted"] = None # Reset for potential future feedback
                        st.rerun() # Trigger rerun to show completion
                    else:
                        # Revision requested - move to the processing_feedback stage
                        logger.info(f"\n\n{"="*20}Inside feedback_submitted else not approved Block{"="*20}\n\n")
                        logger.info(f"\n{'*'*20}feedback_submitted  is {feedback_result.comments}{'*'*20}\n")
                        st.session_state["feedback"] = feedback_result.comments 
                        logger.info(f"{"#"*20} Stored  feedback is: {st.session_state['feedback']}{"#"*20}\n")
                        st.session_state.current_stage = "processing_feedback" # Move to processing_feedback stage
                        st.session_state["feedback_submitted"] = None # Reset the flag
                        feedback_result.comments = None # Clear the feedback result
                        st.session_state["initial_draft"]=None
                        logger.info(f"\n{'*'*20}st.session_state[feedback] is {st.session_state["feedback"]}{'*'*20}\n")
                        st.rerun() # Trigger rerun to enter the processing_feedback stage

            # In DisplayResultStreamlit.process_user_input() for the "processing_feedback" stage
            elif st.session_state.current_stage == "processing_feedback":
                logger.info(f"\n\n{'='*20}: Entered main Display processing_feedback stage:{'='*20}\n\n")
                
                # Create a proper feedback message
                feedback_message = HumanMessage(content=json.dumps({
                    "approved": False,
                    "comments": st.session_state['feedback']
                }))
                
                # Resume the graph with the stored state and new feedback
                logger.info(f"Resuming graph with feedback: {feedback_message.content}")
                logger.info(f"\n\n{'>'*20}Session State Feedback: {st.session_state['feedback']}{'<'*20}\n\n")
                
                # Use the stored checkpoint state to resume the graph
                checkpoint_state = st.session_state.get("graph_state")
                
                if checkpoint_state:
                    try:
                        input_data = {
                            "messages": [feedback_message],
                            "__checkpoint__": checkpoint_state
                        }
                        logger.info("Resuming graph with checkpoint and feedback")
                        graph_status = blog_display.process_graph_events_with_checkpoint(input_data)
                        logger.info(f"Graph processing completed with status: {graph_status}")
                        
                        if graph_status == "completed":
                            st.session_state.current_stage = "complete"
                        elif graph_status == "interrupted":
                            st.session_state.current_stage = "feedback"
                            st.session_state["feedback_submitted"] = False
                        else:
                            logger.error(f"Graph processing ended with unexpected status: {graph_status}")
                            st.error("Error during feedback processing. Starting over from requirements.")
                            st.session_state.current_stage = "requirements"
                            st.session_state.blog_requirements_collected = False
                            st.error("Error processing your feedback. Please try again.")
                    except Exception as e:
                        logger.exception(f"Error during feedback processing: {e}")
                        st.error("Error processing feedback. Starting over from requirements.")
                        st.session_state.current_stage = "requirements"
                        st.session_state.blog_requirements_collected = False
                else:
                    logger.warning("No checkpoint found in session state. Cannot resume processing.")
                    st.warning("Unable to process feedback - starting over from requirements.")
                    st.session_state.current_stage = "requirements"
                    st.session_state.blog_requirements_collected = False
                
                # Clear feedback-related state
                st.session_state['feedback_result'] = None
                st.session_state['feedback_submitted'] = False
                st.session_state['feedback'] = ""
                st.rerun()
                
            elif st.session_state.current_stage == "complete":
                st.success("✅ Blog generation complete!")
                if st.session_state.get("blog_content"):
                    st.markdown("### Final Blog Content:")
                    st.markdown(st.session_state["blog_content"])
                    self._download_blog_content(st.session_state["blog_content"]) # Add download button

        else:
            self._handle_chatbot_input()

    def _download_blog_content(self, blog_content):
        """Creates a download button for the blog content."""
        if blog_content:
            b64 = base64.b64encode(blog_content.encode()).decode()
            href = f'<a href="data:text/plain;base64,{b64}" download="blog_content.txt">⬇️ Download Blog Content</a>'
            st.markdown(href, unsafe_allow_html=True)

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