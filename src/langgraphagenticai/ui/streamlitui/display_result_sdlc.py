import streamlit as st
from langchain_core.messages import HumanMessage
import logging
import markdown
import json
from pydantic import BaseModel, Field
from datetime import datetime
import functools
import time
import base64
from src.langgraphagenticai.logging.logging_utils import logger, log_entry_exit
import os
from langgraph.graph import END
from langgraph.types import Command
from src.langgraphagenticai.state.state import SDLCState
from src.langgraphagenticai.ui.uiconfigfile import Config

exclude_keys = ["api_key", "OPENAI_API_KEY","GOOGLE_API_KEY","TAVILY_API_KEY","GROQ_API_KEY","state"]
safe_state = {k: v for k, v in st.session_state.items() if k not in exclude_keys}

# --- Pydantic Model for Feedback ---
class ReviewFeedback(BaseModel):
    approved: bool = Field(description="Approval status: True for approved, False for rejected")
    comments: str = Field(description="Reviewer comments", default="")

# --- Main Display Class ---
class DisplaySdlcResult:
    def __init__(self, graph, config):
        self.graph = graph
        self.config = config
        self._initialize_session_state()

    def _initialize_session_state(self):
        """Initialize session state variables if they don't exist."""
        defaults = {
            "sdlc_stage": "planning",
            "project_name": "",
            "project_description": "",
            "project_goals": "",
            "project_scope": "",
            "project_objectives": "",
            "requirements_generated": False,
            "user_stories_generated": False,
            "generated_requirements": None,
            "generated_user_stories": None,
            "feedback": None,
            "needs_resume_after_feedback": False,
            "graph_completed": False,
            "graph_running": False,
            "feedback_pending": False,
        }
        for key, value in defaults.items():
            if key not in st.session_state:
                st.session_state[key] = value

    @log_entry_exit
    def handle_sdlc_workflow(self):
        """Manages the overall SDLC workflow display and interaction in Streamlit."""
        st.title("Software Development Life Cycle (SDLC) Workflow")
        st.write(safe_state)

        # Prevent concurrent runs
        if st.session_state.get("graph_running"):
            st.warning("Workflow is already running. Please wait.")
            logger.warning("Workflow blocked due to graph_running=True")
            return

        # Handle resumption
        if st.session_state.get("needs_resume_after_feedback"):
            logger.info("Detected need to resume graph after feedback.")
            st.session_state["graph_running"] = True
            self._resume_sdlc_graph()
            st.session_state["graph_running"] = False
            return  # Avoid further processing to prevent UI conflicts

        # Display UI
        phases = ["Planning", "Design", "Development", "Testing", "Deployment"]
        icons = ["🗓️", "📐", "💻", "🧪", "🚀"]
        tabs = st.tabs([f"{icon} {phase}" for icon, phase in zip(icons, phases)])

        with tabs[0]:
            if not st.session_state.get("requirements_generated"):
                self._display_planning_phase()
            self._display_planning_artifacts()

        with tabs[1]: self._display_design_phase(); self._display_design_artifacts()
        with tabs[2]: self._display_development_phase(); self._display_development_artifacts()
        with tabs[3]: self._display_testing_phase(); self._display_testing_artifacts()
        with tabs[4]: self._display_deployment_phase(); self._display_deployment_artifacts()

        if st.session_state.get("graph_completed"):
            st.success("✅ SDLC Planning Phase Completed Successfully!")
            st.markdown("You can restart the workflow or review the artifacts.")

        st.markdown("---")
        if st.button("Restart SDLC Workflow", key="restart_button"):
            logger.info("Restart SDLC Workflow button clicked")
            self._reset_session_state()
            st.rerun()

    @log_entry_exit
    def _reset_session_state(self):
        """Resets relevant session state keys to start the workflow over."""
        keys_to_reset = list(st.session_state.keys())
        logger.info("Resetting session state.")
        for key in keys_to_reset:
            if not key.startswith("_"):
                del st.session_state[key]
        self._initialize_session_state()

    @log_entry_exit
    def _display_planning_phase(self):
        """Displays the requirement collection section."""
        st.header("Planning Phase")
        self._collect_project_requirements()

    @log_entry_exit
    def _display_planning_artifacts(self):
        """Displays generated planning artifacts and the feedback form."""
        st.subheader("Planning Artifacts")
        requirements_exist = st.session_state.get("requirements_generated")
        stories_exist = st.session_state.get("user_stories_generated")

        if "feedback" not in st.session_state or st.session_state["feedback"] is None:
            st.session_state["feedback"] = {}
            logger.info("Initialized empty feedback dictionary in session state.")

        if requirements_exist:
            with st.expander("Generated Requirements", expanded=False):
                st.markdown(st.session_state["generated_requirements"])
                if st.button("Save Requirements", key="save_requirements_planning"):
                    self._save_artifact(st.session_state["generated_requirements"], "requirements.txt")
        else:
            st.info("Requirements will be displayed here after generation.")

        if stories_exist:
            with st.expander("Generated User Stories", expanded=False):
                st.markdown(st.session_state["generated_user_stories"])
                if st.button("Save User Stories", key="save_user_stories_planning"):
                    self._save_artifact(st.session_state["generated_user_stories"], "user_stories.txt")

            if not st.session_state.get("graph_completed"):
                st.markdown("### Feedback on User Stories")
                decision_options = ("Approve", "Reject")
                selected_decision = st.radio(
                    "Review Decision:",
                    decision_options,
                    key="user_story_feedback_decision",
                    horizontal=True,
                    index=0
                )
                comments = st.text_area(
                    "Comments (Required for Rejection):",
                    placeholder="Include Subscriptions model to retain customer",
                    key="user_story_feedback_comments"
                )
                submit_disabled = st.session_state.get("feedback_pending", False) or st.session_state.get("graph_running", False)
                if st.button("Submit Review", key="submit_review_button", disabled=submit_disabled):
                    if st.session_state.get("feedback_pending"):
                        st.warning("Feedback is already being processed. Please wait.")
                        return
                    st.session_state["feedback_pending"] = True
                    if selected_decision == "Reject" and not comments.strip():
                        st.error("Comments are required when rejecting.")
                        st.session_state["feedback_pending"] = False
                    else:
                        is_approved = (selected_decision == "Approve")
                        logger.info(f"Feedback submitted: {'Approved' if is_approved else 'Rejected with comments.'}")
                        current_stage = "planning"
                        st.session_state["feedback"] = {
                            current_stage: ["accept"] if is_approved else [comments.strip()]
                        }
                        logger.info("Feedback stored: %s", st.session_state["feedback"])
                        st.session_state["needs_resume_after_feedback"] = True
                        if not is_approved:
                            st.session_state["user_stories_generated"] = False
                        st.session_state["feedback_pending"] = False
                        st.write(f"Feedback submitted: {'Approved' if is_approved else 'Rejected with comments.'}{st.session_state["feedback"]}")
                        st.write(f"Feedback processing completed. Graph needs resuming: {st.session_state['needs_resume_after_feedback']}")
                        st.write("Session state after feedback: %s", st.session_state)
                        st.rerun()
            else:
                st.success("✅ User stories approved. Planning phase completed.")
                st.markdown("The feedback form is disabled as the workflow is complete.")
        elif requirements_exist and not stories_exist:
            st.info("User stories will be displayed here after generation or if awaiting regeneration after feedback.")
        elif not requirements_exist and not stories_exist:
            st.info("No artifacts generated yet in the Planning phase.")

    @log_entry_exit
    def _resume_sdlc_graph(self):
        """Resumes the graph execution from the checkpoint after feedback."""
        logger.info("Resuming SDLC graph execution...")
        logger.info("Session state before resumption: %s", "st.session_state")
        feedback_data = st.session_state.get("feedback")
        logger.info(f"Feedback data: %s", feedback_data)

        thread_id = self.config.get("configurable", {}).get("thread_id", "N/A")
        checkpoint = None
        checkpoint_state = None

        if hasattr(self.graph, 'checkpointer'):
            checkpoint_tuple = self.graph.checkpointer.get_tuple({"configurable": {"thread_id": thread_id}})
            if checkpoint_tuple:
                checkpoint = checkpoint_tuple.checkpoint
                logger.info(f"Checkpoint retrieved: %s", "checkpoint")
                checkpoint_state = checkpoint.copy() if hasattr(checkpoint, 'copy') else dict(checkpoint)
            else:
                logger.error("No checkpoint found for thread_id: %s", thread_id)
                st.error("No valid checkpoint found. Please restart the workflow.")
                return
        else:
            logger.error("Graph checkpointer not available.")
            st.error("Graph configuration error. Please restart the workflow.")
            return

        logger.info(f"Checkpoint state before resumption: %s", checkpoint_state)

        # Reconstruct resume_state, ensuring 'feedback' is at the top level
        resume_state = {
            "session_id": checkpoint_state.get("channel_values", {}).get("session_id"),
            "current_stage": checkpoint_state.get("channel_values", {}).get("current_stage", "planning"),
            "project_name": checkpoint_state.get("channel_values", {}).get("project_name"),
            "project_description": checkpoint_state.get("channel_values", {}).get("project_description"),
            "project_goals": checkpoint_state.get("channel_values", {}).get("project_goals"),
            "project_scope": checkpoint_state.get("channel_values", {}).get("project_scope"),
            "project_objectives": checkpoint_state.get("channel_values", {}).get("project_objectives"),
            "feedback": checkpoint_state.get("channel_values", {}).get("feedback", {}),
            "feedback_decision": checkpoint_state.get("channel_values", {}).get("feedback_decision"),
            "created_at": checkpoint_state.get("channel_values", {}).get("created_at", datetime.now().isoformat()),
            "last_updated": checkpoint_state.get("channel_values", {}).get("last_updated", datetime.now().isoformat()),
            "history": checkpoint_state.get("channel_values", {}).get("history", [])
        }

        # Override with st.session_state feedback
        if feedback_data:
            resume_state["feedback"] = feedback_data

        logger.info(f"Reconstructed resume_state: %s", resume_state)

        # ✅ Parse resume_state into proper SDLCState
        resume_state_obj = SDLCState(**resume_state)

        logger.info(f"Resume state object created: %s", resume_state_obj)
        logger.info(f"Resume state object type: %s", type(resume_state_obj))

        # Initialize requirements, user_stories, and graph_completed_flag
        requirements = None
        user_stories = None
        graph_completed_flag = False
        final_state = {}  

        # Inject new state into checkpointer
        if hasattr(self.graph, "checkpointer") and self.graph.checkpointer:
            self.graph.checkpointer.put(
                config={"configurable": {"thread_id": thread_id}},
                checkpoint=resume_state_obj,
                metadata={},  # Provide metadata (can be an empty dictionary)
                new_versions={} # Provide new_versions (can be an empty dictionary)
            )
            logger.info(f"✅ Injected resume_state_obj into checkpointer with thread_id {thread_id}")


        with st.spinner("Processing feedback and continuing workflow..."):
            try:
                # Resume the graph using Command(resume=...) with the reconstructed resume_state
                for event in self.graph.stream(Command(resume=resume_state_obj), config=self.config):
                    logger.info(f"Resume Event: %s", json.dumps(event, default=str))
                    for node, state in event.items():
                        if state is None:
                            logger.info(f"Node '{node}' has null state, skipping.")
                            continue
                        if not isinstance(state, dict):
                            logger.warning(f"Node '{node}' state is not a dict: {type(state)}. Skipping state processing.")
                            continue
                        logger.info(f"Node '{node}' updated state: %s", state)
                        final_state.update(state)  # Capture the latest state
                        if "generated_requirements" in state:
                            requirements = state["generated_requirements"]
                        if "user_stories" in state:
                            user_stories = state["user_stories"]
                        if "feedback_decision" in state:
                            logger.info("Feedback decision: %s", state["feedback_decision"])
                        if node == END or node == "__end__" or state.get("next_node") == END:
                            logger.info("Graph reached END node")
                            graph_completed_flag = True
                        if node == "__interrupt__":
                            logger.info("Graph interrupted for feedback processing")
            except Exception as e:
                logger.error(f"Error during graph stream: {e}", exc_info=True)
                st.error(f"An error occurred during graph resumption: {e}")
                return

        # WORKAROUND: Explicitly update state after graph execution
        if feedback_data:
            final_state["feedback"] = feedback_data
            logger.info(f"WORKAROUND: Updated final_state with feedback: {feedback_data}")
        
        logger.info(f"Final state after resumption: {final_state}")
        logger.info(f"Final feedback value: {final_state.get('feedback')}")


        st.session_state["generated_requirements"] = requirements
        st.session_state["generated_user_stories"] = user_stories
        st.session_state["requirements_generated"] = requirements is not None
        st.session_state["user_stories_generated"] = user_stories is not None and not graph_completed_flag
        st.session_state["graph_completed"] = graph_completed_flag
        st.session_state["needs_resume_after_feedback"] = False
        logger.info("Graph resumption completed. Graph completed: %s", graph_completed_flag)
        logger.info("Session state after resumption: %s", "st.session_state")


    @log_entry_exit
    def _display_design_phase(self):
        # st.header("Design Phase")
        # st.info("Design phase details will be displayed here in future implementations.")
        pass
    @log_entry_exit
    def _display_design_artifacts(self):
        # st.subheader("Design Artifacts")
        # st.info("Design artifacts (e.g., architecture diagrams, UI mockups) will be displayed here.")
        pass

    @log_entry_exit
    def _display_development_phase(self):
        # st.header("Development Phase")
        # st.info("Development phase details will be displayed here in future implementations.")
        pass

    @log_entry_exit
    def _display_development_artifacts(self):
        # st.subheader("Development Artifacts")
        # st.info("Development artifacts (e.g., code snippets, build logs) will be displayed here.")
        pass

    @log_entry_exit
    def _display_testing_phase(self):
        # st.header("Testing Phase")
        # st.info("Testing phase details will be displayed here in future implementations.")
        pass

    @log_entry_exit
    def _display_testing_artifacts(self):
        # st.subheader("Testing Artifacts")
        # st.info("Testing artifacts (e.g., test cases, bug reports) will be displayed here.")
        pass

    @log_entry_exit
    def _display_deployment_phase(self):
        # st.header("Deployment Phase")
        # st.info("Deployment phase details will be displayed here in future implementations.")
        pass

    @log_entry_exit
    def _display_deployment_artifacts(self):
        # st.subheader("Deployment Artifacts")
        # st.info("Deployment artifacts (e.g., deployment plans, monitoring dashboards) will be displayed here.")
        pass

    @log_entry_exit
    def _collect_project_requirements(self):
        """Displays the form to collect initial project details."""
        # DefaultProjectName = "The Book Nook"
        # DefaultDescription = """Develop a user-friendly mobile application for "The Book Nook," a local bookstore in Bangalore, 
        #                         to allow customers to browse their inventory, place orders online, and learn about upcoming events."""
        # DefaultGoals = """ Increase sales and revenue for The Book Nook.
        #                     Enhance customer engagement and loyalty.
        #                     Modernize The Book Nook's presence and reach a wider audience in Bangalore. """
        # DefaultScope = """ Inclusions:
        #                         Developing a mobile application compatible with Android and iOS.
        #                         Features: Browsing book catalog with search and filtering, viewing book details (description, author, price, availability), creating user accounts, adding books to a shopping cart, secure online payment integration, order history, push notifications for new arrivals and events, information about store hours and location.
        #                         Integration with the bookstore's existing inventory management system.
        #                         Basic user support documentation.
        #                     Exclusions:
        #                         Developing a separate tablet application.
        #                         Implementing a loyalty points program (will be considered in a future phase).
        #                         Integrating with social media platforms for direct purchasing.
        #                         Providing real-time inventory updates beyond a daily sync.
        #                         Developing advanced analytics dashboards for the bookstore owner in this phase."""
        # DefaultObjectives = """Increase online sales by 15% within the first six months of the app launch (Measurable, Achievable, Relevant, Time-bound).
        #                     Achieve an average user rating of 4.5 stars or higher on both app stores within three months of launch (Measurable, Achievable, Relevant, Time-bound).
        #                     Acquire 500 new registered app users within the first month of launch (Measurable, Achievable, Relevant, Time-bound).
        #                     Successfully integrate the app with the existing inventory system with no data loss by the end of the development phase (Measurable, Achievable, Relevant, Time-bound). """
        DefaultProjectName="demo_project"
        DefaultDescription="demo_description"
        DefaultGoals="demo_goals"
        DefaultScope="demo_scope"
        DefaultObjectives="demo_objectives"


        st.subheader("Define Project Details")
        with st.form("sdlc_requirements_form"):
            project_name = st.text_input("Project Name", value=st.session_state.get("project_name", DefaultProjectName), placeholder=DefaultProjectName)
            project_description = st.text_area("Project Description", value=st.session_state.get("project_description", DefaultDescription), placeholder=DefaultDescription, height=150)
            project_goals = st.text_area("Project Goals", value=st.session_state.get("project_goals", DefaultGoals), placeholder=DefaultGoals, height=100)
            project_scope = st.text_area("Project Scope", value=st.session_state.get("project_scope", DefaultScope), placeholder=DefaultScope, height=200)
            project_objectives = st.text_area("Project Objectives", value=st.session_state.get("project_objectives", DefaultObjectives), placeholder=DefaultObjectives, height=150)

            submit = st.form_submit_button("Generate Requirements & User Stories")
            if submit and not st.session_state.get("graph_running"):
                st.session_state["project_name"] = project_name.strip() or DefaultProjectName
                st.session_state["project_description"] = project_description.strip() or DefaultDescription
                st.session_state["project_goals"] = project_goals.strip() or DefaultGoals
                st.session_state["project_scope"] = project_scope.strip() or DefaultScope
                st.session_state["project_objectives"] = project_objectives.strip() or DefaultObjectives
                st.session_state["sdlc_stage"] = "planning"
                logger.info("Initial project details submitted. Running graph for the first time.")
                st.session_state["graph_running"] = True
                self._run_sdlc_graph_initial()
                st.session_state["graph_running"] = False
                st.rerun()

    @log_entry_exit
    def _run_sdlc_graph_initial(self):
        """Runs the SDLC graph for the very first time with initial project details."""
        session_id = self.config.get("configurable", {}).get("session_id")
        if not session_id:
            logger.error("Session ID not found in config! Cannot start graph.")
            st.error("Critical error: Session ID missing. Please restart.")
            return

        input_data = {"session_id": session_id}
        requirements = None
        user_stories = None
        logger.info(f"Running SDLC graph initially with input_data: {input_data}...")

        with st.spinner("Generating initial requirements and user stories..."):
            try:
                for event in self.graph.stream(input_data, self.config):
                    logger.info(f"Initial Run Event: {event}")
                    event_key = list(event.keys())[0]
                    if event_key == "__interrupt__":
                        logger.info("Graph interrupted as expected after generating artifacts.")
                        last_node_state = event.get("__interrupt__")
                        if last_node_state:
                            requirements = last_node_state.get("generated_requirements", requirements)
                            user_stories = last_node_state.get("generated_user_stories", user_stories)
                        break
                    for node, state in event.items():
                        if state is None: continue
                        logger.info(f"Node '{node}' updated state.")
                        if "generated_requirements" in state:
                            requirements = state["generated_requirements"]
                        if "user_stories" in state:
                            user_stories = state["user_stories"]
            except Exception as e:
                logger.error(f"Error during initial graph stream: {e}", exc_info=True)
                st.error(f"An error occurred during graph execution: {e}")
                return

        st.session_state["generated_requirements"] = requirements
        st.session_state["generated_user_stories"] = user_stories
        st.session_state["requirements_generated"] = requirements is not None
        st.session_state["user_stories_generated"] = user_stories is not None
        logger.info("Initial graph run finished (interrupted). Artifacts stored in session state.")

    @log_entry_exit
    def _save_artifact(self, content: str, filename: str):
        """Provides a download link for the given artifact content."""
        try:
            b64 = base64.b64encode(content.encode()).decode()
            href = f'<a href="data:file/txt;base64,{b64}" download="{filename}">⬇️ Download {filename}</a>'
            st.markdown(href, unsafe_allow_html=True)
            logger.info(f"Generated download link for {filename}")
        except Exception as e:
            logger.error(f"Error creating download link for {filename}: {e}")
            st.error(f"Could not generate download link for {filename}.")