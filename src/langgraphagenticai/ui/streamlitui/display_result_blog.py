import streamlit as st
from langchain_core.messages import HumanMessage
import logging
import markdown  # Added here to ensure it's available for HTML conversion
import json

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),  # Logs to the console
        logging.FileHandler("app.log")  # Logs to a file
    ]
)
logger = logging.getLogger(__name__)

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
            "processing_complete": False  # Track if processing is complete
        }
        for key, value in defaults.items():
            if key not in st.session_state:
                st.session_state[key] = value
    # def render_ui(self):
        # --- ADD THIS BLOCK NEAR THE START OF render_ui ---
        # # Check if approval was requested via callback
        # if st.session_state.get('approval_requested', True):
        #     print("--- render_ui detected approval_requested ---")
        #     del st.session_state.approval_requested # Reset flag
        #     st.session_state.current_stage = "revision_processing"
        #     st.session_state.waiting_for_feedback = False
        #     self.process_graph_events(input_message="approved") # Call the function that handles graph invocation with approval signal
        #     st.rerun() # Rerun to update UI immediately to processing stage

        # # Check if revision was requested via callback
        # elif st.session_state.get('revision_requested', False):
        #      print("--- render_ui detected revision_requested ---")
        #      del st.session_state.revision_requested # Reset flag
        #      st.session_state.current_stage = "revision_processing"
        #      st.session_state.waiting_for_feedback = False
        #      logger.info(f"\n\n------Revision requested with feedback:-------------\n--------------\n{st.session_state.feedback_text}-----------\n\n")
        #      st.session_state.feedback= st.session_state.get('feedback_text', "") # Get feedback text
        #      self.process_graph_events() # Call the function that handles graph invocation
        #      st.rerun() # Rerun to update UI immediately to processing stage
        # # --- END OF ADDED BLOCK ---


        # Existing render_ui logic follows...
        # if 'current_stage' not in st.session_state:
        #     st.session_state.current_stage = "requirements"
        #     st.session_state.blog_requirements_collected = False # Initialize flag

        # # Render based on stage (keep existing logic)
        # if st.session_state.current_stage == "requirements":
        #      # Display requirements form (call existing function)
        #      requirements_met = self.collect_blog_requirements()
        #      if requirements_met:
        #           st.session_state.blog_requirements_collected = True # Update flag
        #           st.session_state.current_stage = "generation" # Move to next stage
                #   st.rerun() # Rerun to start generation

        # elif st.session_state.current_stage == "generation":
        #     logger.info("\n-----------------\n---------------Blog generation stage entered.\n-----------------\n-------------------\n")
        #     st.info("Generating blog post...")
        #     # If requirements were just met, start the graph stream
        #     if st.session_state.blog_requirements_collected:
        #          # Assuming initial message is prepared in collect_blog_requirements
        #          # or retrieve it from session state if stored there
        #          initial_message = st.session_state.get('initial_blog_message')
        #          if initial_message:
        #               self.process_graph_events(initial_message)
        #          else:
        #               st.error("Initial requirements message not found.")
        #          # Reset flag
        #          st.session_state.blog_requirements_collected = False


        # elif st.session_state.current_stage == "feedback":
        #     # Call the modified process_feedback (which now just renders)
        #     self.process_feedback()
        #     # The actual handling of feedback submission is done
        #     # by the callbacks and the check block added at the start of render_ui

        # elif st.session_state.current_stage == "revision_processing":
        #     st.info("Processing feedback...")
        #     # This stage is entered after feedback callback sets the flag and render_ui reruns.
        #     # process_graph_events was already called by the flag check block.
        #     # We might need logic here to display streaming results during revision if process_graph_events uses stream.

        # elif st.session_state.current_stage == "completed":
        #      st.success("Blog post generation completed!")
        #      # Maybe display the final result if stored in session state
        #      if 'final_blog_content' in st.session_state:
        #           st.markdown("### Final Blog Post")
        #           st.markdown(st.session_state.final_blog_content)
        #           # Add download button if applicable (using st.session_state.file_path)
        #           if 'file_path' in st.session_state and st.session_state.file_path:
        #              try:
        #                  with open(st.session_state.file_path, "rb") as fp:
        #                      st.download_button(
        #                          label="Download Blog Post",
        #                          data=fp,
        #                          file_name=os.path.basename(st.session_state.file_path),
        #                          mime="text/markdown" # Or appropriate mime type
        #                      )
        #              except FileNotFoundError:
        #                  st.error(f"Error: Generated file not found at {st.session_state.file_path}")
        #              except Exception as e:
        #                  st.error(f"Error reading file for download: {e}")
   
    def collect_blog_requirements(self):
        """Collect blog requirements from the user."""
        st.markdown("## Stage 1: Blog Requirements")
        with st.expander("Stage 1: Blog Requirements", expanded=False):
            st.info("ℹ️ Fill in the details below to generate your blog post")
            
            with st.form("blog_requirements_form"):
                topic = st.text_input("Topic",value= "The Future of AI in Healthcare", placeholder="e.g., The Future of AI in Healthcare")
                
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
                                            f"Word Count: {word_count}\nStructure: {structure}")
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

    def display_blog_content(self, content):
        st.markdown("## Final Generated Blog Content")
        st.info("ℹ️ Review the generated blog content below")
        
        with st.container():
            st.markdown("### Generated Blog Content")
            formatted_content = self._format_blog_content(content)
            st.markdown(formatted_content)
            
            # Option to copy content
            if st.button("📋 Copy to Clipboard", key="copy_content"):
                print("----approved button clicked----")
                st.code(content, language="markdown")
                st.success("Content copied to clipboard! Use Ctrl+C to copy.")
            
            st.session_state.content_displayed = True

    def _format_blog_content(self, content):
        if not content:
            return ""
        
        # Improved formatting logic
        content = content.strip()
        
        # Handle all heading levels properly
        for i in range(5, 0, -1):
            heading_marker = '#' * i
            content = content.replace(f"\n{heading_marker} ", f"\n\n{heading_marker} ")
        
        # Ensure paragraphs have proper spacing
        paragraphs = content.split("\n\n")
        formatted_paragraphs = []
        
        for p in paragraphs:
            if p.strip():
                formatted_paragraphs.append(p.strip())
        
        return "\n\n".join(formatted_paragraphs)
    
    def _handle_approved_click(self):
        print("\n\n----approved button ON_CLICK call back executed----\n\n")
        logger.info("----approved button ON_CLICK call back executed----")
        st.session_state.approval_requested = True
        st.session_state.feedback_type = "approved"
    
    def _handle_revised_click(self,feedback_text):
        # check for comments to revise
        if feedback_text:
            print("\n\n----revised button ON_CLICK call back executed----\n\n")
            logger.info("----revised button ON_CLICK call back executed----")
            st.session_state.approval_requested = True
            st.session_state.feedback_type = "revise"
            st.session_state.feedback_text= feedback_text # store the feedback text
            print(f"Feedback text: {feedback_text}")
        else:
            # Handel case where no comments are provided
            st.warning("Please provide comments for revision.")
            if "revsion_requested" in st.session_state:
                del st.session_state.feedback_type


    def process_feedback(self):
        print("\n\n----process_feedback function entered----\n\n")
        logger.info("\n\n----process_feedback function entered (INFO)----\n\n")
        st.markdown("## Stage 3: Feedback")
        with st.expander("Stage 3: Feedback", expanded=True):
            st.info("ℹ️ Review the content and provide your feedback")
            if 'response' in st.session_state and st.session_state.response:
                st.markdown("### Generated Draft")
                st.markdown(st.session_state.response)
            else:
                st.warning("Draft content not available for review.")

            feedback_text = st.text_area("Revision comments:",value="Add some references to the content",
                                placeholder="Please explain what changes you would like to see.",
                                key="revision_comments_area")
            
            col1, col2 = st.columns(2)
            with col1:
                st.button("✅ Approve Content",on_click=self._handle_approved_click,key="blog_feedback_approve_button")
            with col2:
                st.button("Submit Revision Request",on_click=self._handle_revised_click, args=(feedback_text,),key="blog_feedback_revise_button")
        

    def process_graph_events(self, input_message=None):
        try:
            st.markdown("## Stage 2: Generated Draft")
            
            input_data = {"messages": [input_message]} if input_message else None
            progress_bar = st.progress(0)
            
            for i, event in enumerate(self.graph.stream(input_data, self.config)):
                logger.info(f"Graph event received: #{i+1}")
                               
                # Update progress indicator
                progress_value = min(i * 0.1, 0.9)  # Cap at 90% until complete
                progress_bar.progress(progress_value)
                
                # Process event data
                for node, state in event.items():
                    logger.info(f"Processing event for node: {node}, state: {state}")
                    
                      # Specifically handle interrupt events
                    if node == "__interrupt__":
                        logger.info("Interrupt event received - transitioning to feedback stage")
                        st.session_state.waiting_for_feedback = True
                        logger.info("Waiting for feedback from user.")
                        st.session_state.current_stage = "feedback"
                        logger.info("Feedback stage initiated.")
                        progress_bar.progress(1.0)
                        # return
                    
                    if isinstance(state, dict):
                                                
                        if node == "synthesizer" and "initial_draft" in state:
                            logger.info("Draft generated by synthesizer, displaying content")
                            st.session_state.blog_content = state["initial_draft"]
                            st.session_state.content_displayed = True  # Ensure this is set
                            st.session_state.current_stage = "content" # Ensure this is set
                            st.success("✅ Blog content has been generated for review!")
                            with st.expander("Stage 2: Generated Draft", expanded=True):
                                st.markdown(state["initial_draft"])
                            # st.session_state.waiting_for_feedback = True
                            # st.session_state.current_stage = "feedback"
                            progress_bar.progress(1.0)

                    # Check if the file_generator node finished to set stage to complete
                    # This might happen when processing feedback
                    if node == "file_generator":
                        logger.info("File generator node finished, setting stage to complete.")
                        st.session_state.blog_generation_complete = True
                        st.session_state.current_stage = "complete"
                        st.session_state.processing_complete = True
                        break  # Stop processing events after completion

            if not st.session_state.waiting_for_feedback and not st.session_state.processing_complete:
                st.session_state.current_stage = "content"            
            
            # Ensure progress completes
            progress_bar.progress(1.0)
            
        except Exception as e:
            st.error(f"⚠️ Error processing workflow: {e}")
            logger.exception(f"Error in graph streaming: {e}")
            # Add recovery mechanism
            st.session_state.current_stage = "requirements"
            st.warning("There was an error. Please try again.")

    def _display_download_options(self):
        """Display download options for the final blog content."""
        if st.session_state.blog_content:
            st.markdown("### Download Options")
            
            col1, col2 = st.columns(2)
            with col1:
                st.download_button(
                    label="Download as Markdown (.md)",
                    data=st.session_state.blog_content,
                    file_name="blog_post.md",
                    mime="text/markdown"
                )
            
            with col2:
                try:
                    # Convert to HTML for download (basic conversion)
                    html_content = f"""
                    <!DOCTYPE html>
                    <html>
                    <head>
                        <meta charset="UTF-8">
                        <title>Blog Post</title>
                        <style>
                            body {{ font-family: Arial, sans-serif; line-height: 1.6; margin: 0 auto; max-width: 800px; padding: 20px; }}
                            h1, h2, h3 {{ color: #333; }}
                            a {{ color: "#0066cc"; }}
                        </style>
                    </head>
                    <body>
                    {markdown.markdown(st.session_state.blog_content)}
                    </body>
                    </html>
                    """
                    
                    st.download_button(
                        label="Download as HTML (.html)",
                        data=html_content,
                        file_name="blog_post.html",
                        mime="text/html"
                    )
                except Exception as e:
                    st.warning(f"HTML conversion not available: {str(e)}")
                    logger.warning(f"HTML conversion failed: {e}")

            # Show final content
            with st.expander("View Final Content", expanded=False):
                st.markdown(self._format_blog_content(st.session_state.blog_content))
