import streamlit as st
from langchain_core.messages import HumanMessage
import logging
import markdown  # Added here to ensure it's available for HTML conversion
import json
from pydantic import BaseModel, Field

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),  # Logs to the console
        logging.FileHandler("app.log")  # Logs to a file
    ]
)
logger = logging.getLogger(__name__)

class ReviewFeedback(BaseModel):
    approved: bool = Field(description="Approval status: True for approved, False for rejected")
    comments: str = Field(description="Reviewer comments")

class DisplayBlogResult:
    def __init__(self, graph, config):
        self.graph = graph
        self.config = config
        self.session_history = []
        self._initialize_session_state()

    def _initialize_session_state(self):
        """Initialize session state variables."""
        defaults = {
            "current_stage": "requirements",  # Track the current stage
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
        for key, value in defaults.items():
            if key not in st.session_state:
                st.session_state[key] = value

    def collect_blog_requirements(self):
        """Collect blog requirements from the user."""
        st.markdown("## Stage 1: Blog Requirements")
        with st.expander("Stage 1: Blog Requirements", expanded=False):
            st.info("ℹ️ Fill in the details below to generate your blog post")

            with st.form("blog_requirements_form"):
                topic = st.text_input("Topic", value="The Future of AI in Healthcare", placeholder="e.g., The Future of AI in Healthcare")

                objective_options = ["Informative", "Persuasive", "Storytelling", "Other"]
                objective = st.radio("Objective", objective_options)
                custom_objective = None
                if objective == "Other":
                    custom_objective = st.text_input("Specify Objective")

                audience_options = ["Beginners", "Experts", "General Audience", "Other"]
                target_audience = st.radio("Target Audience", audience_options)
                custom_audience = None
                if target_audience == "Other":
                    custom_audience = st.text_input("Specify Target Audience")

                tone_options = ["Formal", "Casual", "Technical", "Engaging", "Other"]
                tone_style = st.radio("Tone & Style", tone_options)
                custom_tone = None
                if tone_style == "Other":
                    custom_tone = st.text_input("Specify Tone & Style")

                word_count = st.number_input("Word Count", min_value=100, max_value=5000, value=100, step=100)
                structure = st.text_area("Structure", placeholder="e.g., Introduction, Key Points, Conclusion")

                submit_button = st.form_submit_button("Next")

                if submit_button:
                    # Handle custom inputs
                    if objective == "Other" and custom_objective:
                        objective = custom_objective
                    if target_audience == "Other" and custom_audience:
                        target_audience = custom_audience
                    if tone_style == "Other" and custom_tone:
                        tone_style = custom_tone

                    if not all([topic, objective, target_audience, tone_style]):
                        st.error("Please fill in all required fields.")
                        return None

                    # Create message and add to history
                    message = HumanMessage(content=f"Topic: {topic}\nObjective: {objective}\n"
                                                    f"Target Audience: {target_audience}\nTone & Style: {tone_style}\n"
                                                    f"Word Count: {word_count}\nStructure: {structure}\n"
                                                    f"feedback: {st.session_state.get('feedback')}")
                    self.session_history.append(message)
                    st.session_state.blog_requirements_collected = True
                    logger.info(f"\n\n--------------:Blog requirements collected:------------------\n{message.content}--------------------\n\n")
                    # Show summary
                    st.success("✅ Blog requirements submitted successfully!")
                    st.markdown("### Requirements Summary")
                    requirements_summary = {
                        "Topic": topic,
                        "Objective": objective,
                        "Target Audience": target_audience,
                        "Tone & Style": tone_style,
                        "Word Count": f"{word_count} words",
                        "Structure": structure or "Default"
                    }
                    print(message)
                    for key, value in requirements_summary.items():
                        st.write(f"**{key}:** {value}")

                    return message
        return None

    def _handle_approved_click(self):
        print("\n\n----approved button ON_CLICK call back executed----\n\n")
        logger.info("----approved button ON_CLICK call back executed----")
        st.session_state['feedback_result'] = ReviewFeedback(approved=True, comments=st.session_state.get('feedback'))
        st.session_state["feedback_submitted"] = True 
        print(f"\n\n----------exiting _handle_approved_click function{st.session_state['feedback_result']}---------------\n\n")

    def _handle_revised_click(self):
    
        print("\n\n----Revised button ON_CLICK call back executed----\n\n")
        logger.info("----Revised button ON_CLICK call back executed----")
        st.session_state['feedback_result'] = ReviewFeedback(approved=False, comments=st.session_state.get('feedback'))
        st.session_state["feedback_submitted"]=True
        print(f"\n\n----------feedback_submitted: {st.session_state['feedback_submitted']} & Exiting _handle_revised_click function with {st.session_state['feedback_result']}---------------\n\n")
   

    def process_graph_events(self, input_message=None):
        try:
            input_data = {"messages": [input_message]} if input_message else None
            progress_bar = st.progress(0)
            checkpoint_found = False
            
            for i, event in enumerate(self.graph.stream(input_data, self.config)):
                logger.info(f"Graph event received: #{i+1}")
                logger.info(f"Graph event keys: {list(event.keys())}")
                
                # Update progress indicator
                progress_value = min(i * 0.1, 0.9)
                progress_bar.progress(progress_value)
                
                # Log checkpoint details
                if "__checkpoint__" in event:
                    checkpoint_state = event["__checkpoint__"]
                    checkpoint_found = True
                    logger.info(f"CHECKPOINT DETECTED - Type: {type(checkpoint_state)}")
                    if isinstance(checkpoint_state, dict):
                        logger.info(f"Checkpoint keys: {list(checkpoint_state.keys())}")
                    st.session_state.graph_state = checkpoint_state
                    logger.info("Checkpoint saved to session state")
                elif any(key for key in event.keys() if key == "synthesizer"):
                    logger.warning("Synthesizer event received, checking for checkpoint")
                    if not checkpoint_found:
                        logger.critical("Synthesizer completed but no checkpoint was generated!")
                        # Create manual checkpoint as fallback
                        logger.warning("No checkpoint detected - creating manual checkpoint")
                        manual_checkpoint = {
                            "last_node": "synthesizer",
                            "initial_draft": state.get("initial_draft", ""),
                            "sections": state.get("sections", []),
                            "topic": state.get("topic", "")
                        }
                        st.session_state.graph_state = manual_checkpoint
                        checkpoint_found = True
                        logger.info("Manual checkpoint created")
                
                # Process event data
                for node, state in event.items():
                    if node == "__interrupt__":
                        logger.info("Interrupt event received - transitioning to feedback stage")
                        st.session_state.waiting_for_feedback = True
                        st.session_state.current_stage = "feedback"
                        st.rerun()
                        return
                    if node == "synthesizer" and "initial_draft" in state:
                        logger.info("Draft generated by synthesizer, displaying content")
                        st.session_state.generated_draft = state["initial_draft"]
                        st.session_state.content_displayed = True
            
            progress_bar.progress(1.0)
            if not checkpoint_found:
                logger.warning("No checkpoint was created during graph processing!")
        except Exception as e:
            logger.exception(f"Error in graph streaming: {e}")
            st.error(f"⚠️ Error processing workflow: {e}")

    def process_graph_events_with_checkpoint(self, input_data):
        try:
            logger.info(f"Starting graph resume with checkpoint. Input keys: {list(input_data.keys())}")
            if "__checkpoint__" in input_data:
                logger.info(f"Checkpoint keys: {list(input_data['__checkpoint__'].keys())}")
            progress_bar = st.progress(0)
            for i, event in enumerate(self.graph.stream(input_data, self.config)):
                logger.info(f"Graph event received (resuming): #{i+1}")
                logger.info(f"Processing node: {list(event.keys())[0]}")
                node = list(event.keys())[0]
                state = event[node]
                if node == "synthesizer" and "initial_draft" in state:
                    logger.info(f"Synthesizer draft: {state['initial_draft']}")
                progress_bar.progress(min(i * 0.1 + 0.1, 1.0))
                if "__interrupt__" in event:
                    logger.info("Interrupt detected during resume")
                    st.session_state.graph_state = event.get("__checkpoint__", input_data["__checkpoint__"])
                    return "interrupted"
                if "file_generator" in event:
                    logger.info(f"Final draft: {state.get('initial_draft', 'No draft generated')}")
                    return "completed"
            return "completed"
        except Exception as e:
            logger.exception(f"Error resuming graph with checkpoint: {e}")
            st.error(f"⚠️ Error resuming workflow: {e}")
            return "error"
            

    def process_feedback(self):
        """Process user feedback on the generated blog draft."""
        print("\n\n----blog_display process_feedback function entered----\n\n")
        logger.info("---blog_display process_feedback function entered ----\n\n")
        
        st.markdown("## Stage 3: Feedback")
        if st.session_state.get("generated_draft"):
            st.markdown("### Drafted Blog Content:")
            st.markdown(st.session_state["generated_draft"])
            
        with st.expander("Stage 3: Feedback", expanded=True):
            feedback_text = st.text_input(
                "Revision comments:",
                placeholder="Please explain what changes you would like to see.",
                key="revision_comments_area",
                value=st.session_state.get("revision_comments_area", "Add some reference to it ")
            )
            st.session_state["feedback"] = feedback_text  # Update session state for graph processing

            col1, col2 = st.columns(2)
            with col1:
                st.button("✅ Approve Content", on_click=self._handle_approved_click, key="blog_feedback_approve_button")
            with col2:
                st.button("Submit Revision Request", on_click=self._handle_revised_click, key="blog_feedback_revise_button")
        
        return st.session_state.get('feedback_result')