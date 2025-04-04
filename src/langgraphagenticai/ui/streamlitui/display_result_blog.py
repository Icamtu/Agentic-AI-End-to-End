import streamlit as st
from langchain_core.messages import HumanMessage
import logging
import markdown  # Added here to ensure it's available for HTML conversion

logging.basicConfig(
    level=logging.INFO,  # Set the minimum log level to INFO
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'  # Format for log messages
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

    def render_ui(self):
        """Main method to control the UI flow based on the current stage."""
        st.title("Blog Post Generator")
        
        # Stage 1: Requirements Collection
        if st.session_state.current_stage == "requirements":
            message = self.collect_blog_requirements()
            st.write(message)
            if message:
                st.session_state.blog_requirements_collected = True
                st.session_state.current_stage = "processing"
                # st.rerun()
        
        # Stage 2: Process Graph (Initial)
        elif st.session_state.current_stage == "processing":
            if st.session_state.blog_requirements_collected and not st.session_state.content_displayed:
                with st.spinner("Generating your blog content..."):
                    self.process_graph_events(self._get_last_message())
                   
        
        # Stage 3: Display Content
        elif st.session_state.current_stage == "content":
            if st.session_state.blog_content:
                self.display_blog_content(st.session_state.blog_content)
                st.session_state.current_stage = "feedback"
        
        # Stage 4: Feedback
        elif st.session_state.current_stage == "feedback":
            feedback = self.process_feedback()
            if feedback:
                st.session_state.feedback = feedback
                st.session_state.feedback_submitted = True
                st.session_state.current_stage = "revision_processing"
                st.rerun()
        
        # Stage 5: Process Revisions
        elif st.session_state.current_stage == "revision_processing":
            if st.session_state.feedback_submitted and not st.session_state.processing_complete:
                with st.spinner("Processing your feedback..."):
                    self.process_graph_events(HumanMessage(content=f"Feedback: {st.session_state.feedback['comments']}"))
        
        # Final Stage: Completion
        elif st.session_state.current_stage == "complete":
            st.markdown("## Final Stage: Blog Generation Complete")
            st.success("🎉 Blog post has been generated and finalized!")
            self._display_download_options()

    def _get_last_message(self):
        """Helper to retrieve the most recent message from session history."""
        return self.session_history[-1] if self.session_history else None

    def collect_blog_requirements(self):
        """Collect blog requirements from the user."""
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
                    
                    for key, value in requirements_summary.items():
                        st.write(f"**{key}:** {value}")
                    
                    return message
            return None

    def display_blog_content(self, content):
        st.markdown("## Stage 2: Generated Blog Content")
        st.info("ℹ️ Review the generated blog content below")
        
        with st.container():
            st.markdown("### Generated Blog Content")
            formatted_content = self._format_blog_content(content)
            st.markdown(formatted_content)
            
            # Option to copy content
            if st.button("📋 Copy to Clipboard", key="copy_content"):
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

    def process_feedback(self):
        st.markdown("## Stage 3: Review & Feedback")
        st.info("ℹ️ Review the content and provide your feedback")
        
        col1, col2 = st.columns(2)
        with col1:
            if st.button("✅ Approve Content", key="approve_button"):
                st.success("Content has been approved!")
                st.session_state.processing_complete = True
                st.session_state.current_stage = "complete"
                return {"approved": True, "comments": "Content approved."}

        with col2:
            with st.expander("Request Revisions", expanded=True):
                comments = st.text_area("Revision comments:",
                                      placeholder="Please explain what changes you would like to see.",
                                      key="revision_comments")
                if st.button("Submit Revision Request", key="revision_button"):
                    if comments:
                        st.info("Revision request submitted")
                        st.write("**Requested Changes:**")
                        st.write(comments)
                        return {"approved": False, "comments": comments}
                    else:
                        st.error("Please provide revision comments.")
        
        return None

    def process_graph_events(self, input_message=None):
        try:
            st.markdown("## Processing Your Request")
            
            input_data = {"messages": [input_message]} if input_message else None
            progress_bar = st.progress(0)
            
            for i, event in enumerate(self.graph.stream(input_data, self.config)):
                logger.info(f"Graph event received: #{i+1}")
                              
                # Update progress indicator
                progress_value = min(i * 0.1, 0.9)  # Cap at 90% until complete
                progress_bar.progress(progress_value)
                
                # Process event data
                for node, state in event.items():
                    if "initial_draft" in state:
                        st.session_state.blog_content = state["initial_draft"]
                        st.session_state.content_displayed = True  # Ensure this is set
                        st.session_state.current_stage = "content" # Ensure this is set
                        progress_bar.progress(1.0)
                        st.success("✅ Blog content has been generated for review!")
                        
                    if "initial_draft" in state and state["initial_draft"]:
                        with st.expander("Stage 2: Generated Draft", expanded=False):
                            st.markdown(state["initial_draft"])
                            submit_button = st.button("Next")
                            if submit_button:
                                st.session_state.current_stage = "feedback"
                                st.session_state.content_displayed = True
                                break
                    

                # Handle graph state transitions
                graph_state = self.graph.get_state(self.config)
                if graph_state and hasattr(graph_state, 'next') and graph_state.next:
                    st.session_state.graph_state = graph_state
                    
                    if graph_state.next[0] == "feedback_collector":
                        st.session_state.waiting_for_feedback = True
                        st.session_state.current_stage = "feedback"
                        break
                        
                    elif graph_state.next[0] == "file_generator":
                        st.session_state.blog_generation_complete = True
                        st.session_state.current_stage = "complete"
                        st.session_state.processing_complete = True
                        break

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
                            a {{ color: #0066cc; }}
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
