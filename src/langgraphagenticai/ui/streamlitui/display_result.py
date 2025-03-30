import streamlit as st
from langchain_core.messages import HumanMessage, AIMessage
import logging
import json

logger = logging.getLogger(__name__)

class DisplayResultStreamlit:
    def __init__(self, graph, with_message_history, config, usecase):
        self.graph = graph
        self.with_message_history = with_message_history
        self.config = config
        self.usecase = usecase
        # Initialize session state defaults
        self._initialize_session_state()
        self.session_history = self._get_session_history()

    def _initialize_session_state(self):
        """Initialize all session state variables."""
        defaults = {
            "waiting_for_feedback": False,
            "blog_requirements_collected": False,
            "content_displayed": False,
            "graph_state": None,
            "current_session_id": None
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
        # Reset display flags if session ID changes
        if st.session_state.current_session_id != session_id:
            st.session_state.content_displayed = False
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
        if self.usecase == "Blog Generation":
            self._handle_blog_generation()
        else:
            self._handle_chatbot_input()

    def _handle_blog_generation(self):
        # Check if we're waiting for feedback
        if not st.session_state.waiting_for_feedback and st.session_state.graph_state:
            graph_state = st.session_state.graph_state
            if graph_state.next and graph_state.next[0] == "feedback_collector":
                logger.info("\nSetting waiting_for_feedback based on graph state\n")
                st.session_state.waiting_for_feedback = True

        if st.session_state.waiting_for_feedback:
            self._process_feedback()
        elif not st.session_state.blog_requirements_collected:
            self._collect_blog_requirements()
        else:
            self._process_graph_stream()

    def _collect_blog_requirements(self):
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
                if not all([topic, objective, target_audience, tone_style]):
                    st.error("Please fill in all required fields.")
                    return
                user_message = f"Topic: {topic}\nObjective: {objective}\nTarget Audience: {target_audience}\nTone & Style: {tone_style}\nWord Count: {word_count}\nStructure: {structure}"
                self.session_history.add_user_message(user_message)
                with st.chat_message("user"):
                    st.markdown(user_message)
                # Reset display flags for new blog generation
                st.session_state.content_displayed = False
                st.session_state.blog_requirements_collected = True
                self._process_graph_stream(HumanMessage(content=user_message))

    def _process_feedback(self):
        latest_state = st.session_state.graph_state.values if st.session_state.graph_state else {}
        logger.info(f"Latest state in _process_feedback: {latest_state}")
        
        # Look for blog content in the right places
        blog_content = latest_state.get("final_report", "")
        
        # Display the content if it hasn't been displayed yet
        if blog_content and not st.session_state.content_displayed:
            with st.chat_message("assistant"):
                st.markdown("### Generated Blog Content")
                st.markdown(self._format_blog_content(blog_content))
                st.session_state.content_displayed = True
                logger.info("Blog content displayed from _process_feedback")

        # Check if we're at the feedback collection node
        current_node = st.session_state.graph_state.next[0] if st.session_state.graph_state.next else None
        logger.info(f"Current node in _process_feedback: {current_node}")
        
        if current_node == "feedback_collector":
            # Only show feedback UI if we haven't already shown it
            if not st.session_state.get("feedback_ui_shown", False):
                st.write("### Review the generated content:")
                col1, col2 = st.columns(2)
                
                with col1:
                    if st.button("Approve", key="content_approve"):
                        feedback = {
                            "approved": True,
                            "comments": "Content approved."
                        }
                        self._submit_feedback(feedback)
                        
                with col2:
                    with st.expander("Request Revisions"):
                        comments = st.text_area("Provide revision comments:", 
                                            placeholder="Please explain what changes you would like to see.")
                        if st.button("Submit Revisions"):
                            if not comments:
                                st.error("Please provide revision comments.")
                            else:
                                feedback = {
                                    "approved": False,
                                    "comments": comments
                                }
                                self._submit_feedback(feedback)
                
                st.session_state.feedback_ui_shown = True

    def _submit_feedback(self, feedback):
        """Submit feedback to the graph and continue processing."""
        try:
            # Convert feedback to the expected format
            feedback_json = json.dumps(feedback)
            st.session_state.waiting_for_feedback = False
            st.session_state.content_displayed = False
            st.session_state.feedback_ui_shown = False  # Reset this flag
            
            # Continue processing with the feedback
            self._process_graph_stream(HumanMessage(content=feedback_json))
            logger.info(f"Feedback submitted: {feedback}")
        except Exception as e:
            logger.error(f"Error submitting feedback: {e}")
            st.error(f"Error submitting feedback: {e}")

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
                for event in (self.graph.stream(input_data, self.config) if input_data else self.graph.stream(None, self.config)):
                    logger.info(f"\nGraph event: {event}\n")
                    
                    # Check for blog content in each event
                    for node, state in event.items():
                        # Print the full state for debugging
                        logger.info(f"\nState from {node}: {state}\n")
                        
                        if "final_report" in state:
                            # Store the final report in session state for access in _process_feedback
                            if not st.session_state.get("blog_content"):
                                st.session_state.blog_content = state["final_report"]
                                logger.info(f"Stored blog content in session state: {state['final_report'][:30]}...")
                        
                        if "messages" in state and state["messages"]:
                            with st.chat_message("assistant"):
                                content = state["messages"][-1].content
                                st.markdown(content)
                            self.session_history.add_ai_message(content)
                    
                    graph_state = self.graph.get_state(self.config)
                    logger.info(f"\nGraph state next: {graph_state.next}\n")
                    
                    if graph_state.next and graph_state.next[0] == "feedback_collector":
                        st.session_state.waiting_for_feedback = True
                        st.session_state.graph_state = graph_state
                        logger.info("\nPaused for feedback collection\n")
                        st.rerun()  # Force UI update to ensure feedback buttons appear
                        break
            except Exception as e:
                logger.error(f"\nError in graph streaming: {e}\n")
                st.error(f"\nError processing workflow: {e}\n")

    def _display_result(self, response):
        logger.info(f"\nDisplay result response: {response}\n")
        
        if self.usecase == "Blog Generation":
            messages = response.get("messages", [])
            blog_content = response.get("final_report", "")
            
            # If we have messages but no blog content, just show the message
            if messages and not blog_content:
                content = messages[-1].content
                st.markdown(content)
                
            # No need to display blog content here - it will be handled by _process_feedback
            # This prevents duplicate displays



        elif self.usecase == "Basic Chatbot":
            # Kept exactly as in original code
            st.markdown(response.get("messages", [{}])[-1].content)

        elif self.usecase == "Chatbot with Tool":
            # Kept exactly as in original code
            content = response.get("messages", [{}])[-1].content
            tool_output = response.get("tool_output", "")
            if tool_output:
                st.markdown("**Tool Output:**")
                st.code(tool_output, language="text")
            st.markdown(content)

    def _format_blog_content(self, content):
        """Format blog content for better display in Streamlit."""
        if not content:
            return ""
            
        sections = content.strip().split("\n\n")
        formatted = "\n\n".join(
            f"\n\n{s.strip()}" if s.startswith("#") else s.strip()
            for s in sections if s.strip()
        )
        return formatted.replace("\n###", "\n\n###").replace("\n##", "\n\n##").replace("\n#", "\n\n#")