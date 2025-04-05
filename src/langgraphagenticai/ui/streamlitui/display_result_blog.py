import streamlit as st
from langchain_core.messages import HumanMessage
from langgraph.graph import MessagesState
import logging
import markdown
import json

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s\n'
)
logger = logging.getLogger(__name__)

class DisplayBlogResult:
    def __init__(self, graph, config):
        self.graph = graph
        self.config = config
        self.session_history = []
        self._initialize_session_state()

    def _initialize_session_state(self):
        defaults = {
            "current_stage": "requirements",
            "waiting_for_feedback": False,
            "blog_requirements_collected": False,
            "content_displayed": False,
            "graph_state": None,
            "feedback": "",
            "blog_content": None,
            "blog_generation_complete": False,
            "feedback_submitted": False,
            "processing_complete": False
        }
        for key, value in defaults.items():
            if key not in st.session_state:
                st.session_state[key] = value

    def render_ui(self):
        st.title("Blog Post Generator")
        st.write("Debug - Current Stage:", st.session_state.current_stage)
        
        if st.session_state.current_stage == "requirements":
            message = self.collect_blog_requirements()
            st.write(message)
            if message:
                st.session_state.blog_requirements_collected = True
                st.session_state.current_stage = "processing"
                st.rerun()
        
        elif st.session_state.current_stage == "processing":
            if st.session_state.blog_requirements_collected and not st.session_state.content_displayed:
                with st.spinner("Generating your blog content..."):
                    self.process_graph_events(self._get_last_message())
                st.rerun()
        
        elif st.session_state.current_stage == "content":
            if st.session_state.blog_content:
                self.display_blog_content(st.session_state.blog_content)
                st.session_state.current_stage = "feedback"
                st.rerun()
        
        elif st.session_state.current_stage == "feedback":
            feedback = self.process_feedback()
            if feedback:
                st.session_state.feedback = feedback
                st.session_state.feedback_submitted = True
                st.session_state.current_stage = "revision_processing"
                st.rerun()
        
        elif st.session_state.current_stage == "revision_processing":
            if st.session_state.feedback_submitted and not st.session_state.processing_complete:
                with st.spinner("Processing your feedback..."):
                    feedback_json = json.dumps(st.session_state.feedback)
                    self.process_graph_events(HumanMessage(content=feedback_json))
                st.rerun()
        
        elif st.session_state.current_stage == "complete":
            st.markdown("## Final Stage: Blog Generation Complete")
            st.success("🎉 Blog post has been generated and finalized!")
            self._display_download_options()

    def _get_last_message(self):
        return self.session_history[-1] if self.session_history else None

    def collect_blog_requirements(self):
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
                    if objective == "Other" and custom_objective:
                        objective = custom_objective
                    if target_audience == "Other" and custom_audience:
                        target_audience = custom_audience
                    if tone_style == "Other" and custom_tone:
                        tone_style = custom_tone
                    if not all([topic, objective, target_audience, tone_style]):
                        st.error("Please fill in all required fields.")
                        return None
                    message = HumanMessage(content=f"Topic: {topic}\nObjective: {objective}\n"
                                                  f"Target Audience: {target_audience}\nTone & Style: {tone_style}\n"
                                                  f"Word Count: {word_count}\nStructure: {structure}")
                    self.session_history.append(message)
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
            if st.button("📋 Copy to Clipboard", key="copy_content"):
                st.code(content, language="markdown")
                st.success("Content copied to clipboard! Use Ctrl+C to copy.")
        st.session_state.content_displayed = True

    def _format_blog_content(self, content):
        if not content:
            return ""
        content = content.strip()
        for i in range(5, 0, -1):
            heading_marker = '#' * i
            content = content.replace(f"\n{heading_marker} ", f"\n\n{heading_marker} ")
        paragraphs = content.split("\n\n")
        formatted_paragraphs = [p.strip() for p in paragraphs if p.strip()]
        return "\n\n".join(formatted_paragraphs)

    def process_feedback(self,State: MessagesState):
        st.markdown("## Stage 3: Feedback")
        with st.expander("Stage 3: Feedback", expanded=True):
            st.info("ℹ️ Review the content and provide your feedback")
            col1, col2 = st.columns(2)
            with col1:
                if st.button("✅ Approve Content", key="approve_button"):
                    State["approved"] = True
                    st.write(f"state Approved status{state['approved']}")
                    logger.info("Content approved by user.")
                    st.success("Content approval submitted. Processing...")
                    return {"approved": True, "comments": "Content approved."}
            with col2:
                comments = st.text_area("Revision comments:", value="Add some references to the content",
                                       placeholder="Please explain what changes you would like to see.",
                                       key="revision_comments")
                if st.button("Submit Revision Request", key="revision_button"):
                    if comments:
                        st.info("Revision request submitted")
                        st.write("**Requested Changes:**")
                        st.write(comments)
                        logger.info(f"\nRevision request: {comments}\n")
                        return {"approved": False, "comments": comments}
            return None

    def process_graph_events(self, input_message=None):
        try:
            st.markdown("## Stage 2: Generated Draft")
            input_data = {"messages": [input_message]} if input_message else None
            progress_bar = st.progress(0)
            for i, event in enumerate(self.graph.stream(input_data, self.config)):
                logger.info(f"Graph event received: #{i+1}{event}")
                progress_value = min(i * 0.1, 0.9)
                progress_bar.progress(progress_value)
                for node, state in event.items():
                    logger.info(f"Processing event for node: {node}, state: {state}")
                    if node == "__interrupt__":
                        logger.info("Interrupt event received - transitioning to feedback stage")
                        st.session_state.waiting_for_feedback = True
                        st.session_state.current_stage = "feedback"
                        progress_bar.progress(1.0)
                        st.info("Draft generated. Please provide feedback below.")
                        return
                    if isinstance(state, dict):
                        if node == "synthesizer" and "initial_draft" in state:
                            logger.info("Draft generated by synthesizer, displaying content")
                            st.session_state.blog_content = state["initial_draft"]
                            st.session_state.content_displayed = False  # Reset for revisions
                            st.success("✅ Blog content has been generated for review!")
                            with st.expander("Stage 2: Generated Draft", expanded=True):
                                st.markdown(state["initial_draft"])
                            st.session_state.waiting_for_feedback = True
                            st.session_state.current_stage = "feedback"
                            progress_bar.progress(1.0)

                        if node == "feedback_collector" and "draft_approved" in state:
                            logger.info(f"Feedback collector node finished, draft_approved: {state['draft_approved']}")
                            if state["draft_approved"]:
                                logger.info("Draft approved, proceeding to file generation.")
                                st.session_state.blog_content = state["final_report"]
                                st.session_state.current_stage = "complete"
                                
                            else:
                                logger.info("Draft not approved, waiting for feedback.")
                                st.session_state.current_stage = "revision_processing"

                    if node == "file_generator":
                        logger.info("File generator node finished, setting stage to complete.")
                        st.session_state.blog_generation_complete = True
                        st.session_state.current_stage = "complete"
                        st.session_state.processing_complete = True
                        break
            progress_bar.progress(1.0)
        except Exception as e:
            st.error(f"⚠️ Error processing workflow: {e}")
            logger.exception(f"Error in graph streaming: {e}")
            st.session_state.current_stage = "requirements"
            st.warning("There was an error. Please try again.")

    def _display_download_options(self):
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
            with st.expander("View Final Content", expanded=False):
                st.markdown(self._format_blog_content(st.session_state.blog_content))
