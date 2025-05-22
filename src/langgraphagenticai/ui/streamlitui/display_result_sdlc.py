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
from src.langgraphagenticai.state.state import SDLCStages, SDLCState
from src.langgraphagenticai.ui.uiconfigfile import Config

exclude_keys = ["api_key", "OPENAI_API_KEY", "GOOGLE_API_KEY", "TAVILY_API_KEY", "GROQ_API_KEY", "state"]
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
            "user_stories_generated_flag": False,
            "design_documents_generated_flag": False,
            "development_artifact_generated_flag": False,
            "testing_artifact_generated_flag": False,
            "deployment_artifact_generated_flag": False,
            "generated_requirements": None,
            "generated_user_stories": None,
            "generated_design_documents": None,
            "generated_development_artifact": None,
            "generated_testing_artifact": None,
            "generated_deployment_artifact": None,
            "user_stories_approved": False,
            "design_documents_approved": False,
            "development_artifact_approved": False,
            "testing_artifact_approved": False,
            "deployment_artifact_approved": False,
            "feedback": {},
            "feedback_pending": False,
            "needs_resume_after_feedback": False,
            "planning_stage_running": False,
            "design_stage_running": False,
            "development_stage_running": False,
            "testing_stage_running": False,
            "deployment_stage_running": False,
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
        running_flags = [
            st.session_state.get("planning_stage_running"),
            st.session_state.get("design_stage_running"),
            st.session_state.get("development_stage_running"),
            st.session_state.get("testing_stage_running"),
            st.session_state.get("deployment_stage_running"),
        ]
        if any(running_flags):
            st.warning("Workflow is already running. Please wait.")
            logger.warning("Workflow blocked due to active stage running.")
            return

        # Handle resumption
        if st.session_state.get("needs_resume_after_feedback"):
            logger.info("Detected need to resume graph after feedback.")
            current_stage = st.session_state.get("sdlc_stage")
            st.session_state[f"{current_stage}_stage_running"] = True
            try:
                self._resume_sdlc_graph()
            finally:
                st.session_state[f"{current_stage}_stage_running"] = False
            st.rerun()
            return

        # Display UI
        phases = ["Planning", "Design", "Development", "Testing", "Deployment"]
        icons = ["🗓️", "📐", "💻", "🧪", "🚀"]
        tabs = st.tabs([f"{icon} {phase}" for icon, phase in zip(icons, phases)])

        with tabs[0]:
            if not st.session_state.get("requirements_generated"):
                self._display_planning_phase()
            self._display_planning_artifacts()
            if st.session_state.get("user_stories_approved"):
                st.session_state["user_stories"] = st.session_state["generated_user_stories"]
                st.session_state["sdlc_stage"] = "design"
                st.session_state["feedback_decision"] = None
                st.session_state["needs_resume_after_feedback"] = False
                st.session_state["feedback_pending"] = False
                st.success("✅ SDLC Planning Phase Completed Successfully!")
                st.markdown("You can GO TO NEXT PHASE or review the artifacts.")
                if st.session_state["sdlc_stage"] == "design" and not st.session_state.get("design_documents_generated_flag"):
                    st.info("Moving to Design Phase and generating artifacts...")
                    st.session_state["design_stage_running"] = True
                    try:
                        self._run_sdlc_graph_initial("design")
                    finally:
                        st.session_state["design_stage_running"] = False
                    st.rerun()

        with tabs[1]:
            if not st.session_state.get("design_documents_generated_flag"):
                self._display_design_phase()
            self._display_design_artifacts()
            if st.session_state.get("design_documents_approved"):
                st.session_state["sdlc_stage"] = "development"
                st.session_state["feedback_decision"] = None
                st.session_state["needs_resume_after_feedback"] = False
                st.session_state["feedback_pending"] = False
                st.success("✅ SDLC Design Phase Completed Successfully!")
                st.markdown("You can GO TO NEXT PHASE or review the artifacts.")
                if st.session_state["sdlc_stage"] == "development" and not st.session_state.get("development_artifact_generated_flag"):
                    st.info("Moving to Development Phase and generating artifacts...")
                    st.session_state["development_stage_running"] = True
                    try:
                        self._run_sdlc_graph_initial("development")
                    finally:
                        st.session_state["development_stage_running"] = False
                    st.rerun()

        with tabs[2]:
            if not st.session_state.get("development_artifact_generated_flag"):
                self._display_development_phase()
            self._display_development_artifacts()
            if st.session_state.get("development_artifact_approved"):
                st.session_state["sdlc_stage"] = "testing"
                st.session_state["feedback_decision"] = None
                st.session_state["needs_resume_after_feedback"] = False
                st.session_state["feedback_pending"] = False
                st.success("✅ SDLC Development Phase Completed Successfully!")
                st.markdown("You can GO TO NEXT PHASE or review the artifacts.")
                if st.session_state["sdlc_stage"] == "testing" and not st.session_state.get("testing_artifact_generated_flag"):
                    st.info("Moving to Testing Phase and generating artifacts...")
                    st.session_state["testing_stage_running"] = True
                    try:
                        self._run_sdlc_graph_initial("testing")
                    finally:
                        st.session_state["testing_stage_running"] = False
                    st.rerun()

        with tabs[3]:
            if not st.session_state.get("testing_artifact_generated_flag"):
                self._display_testing_phase()
            self._display_testing_artifacts()
            if st.session_state.get("testing_artifact_approved"):
                st.session_state["sdlc_stage"] = "deployment"
                st.session_state["feedback_decision"] = None
                st.session_state["needs_resume_after_feedback"] = False
                st.session_state["feedback_pending"] = False
                st.success("✅ SDLC Testing Phase Completed Successfully!")
                st.markdown("You can GO TO NEXT PHASE or review the artifacts.")
                if st.session_state["sdlc_stage"] == "deployment" and not st.session_state.get("deployment_artifact_generated_flag"):
                    st.info("Moving to Deployment Phase and generating artifacts...")
                    st.session_state["deployment_stage_running"] = True
                    try:
                        self._run_sdlc_graph_initial("deployment")
                    finally:
                        st.session_state["deployment_stage_running"] = False
                    st.rerun()

        with tabs[4]:
            if not st.session_state.get("deployment_artifact_generated_flag"):
                self._display_deployment_phase()
            self._display_deployment_artifacts()
            if st.session_state.get("deployment_artifact_approved"):
                st.session_state["sdlc_stage"] = "complete"
                st.session_state["feedback_decision"] = None
                st.session_state["needs_resume_after_feedback"] = False
                st.session_state["feedback_pending"] = False
                st.success("✅ SDLC Deployment Phase Completed Successfully!")
                st.markdown("SDLC Workflow Completed!")

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
        requirements_exist = st.session_state.get("requirements_generated", False)
        stories_exist = st.session_state.get("user_stories_generated_flag", False)
        user_stories_approved = st.session_state.get("user_stories_approved", False)

        if requirements_exist:
            with st.expander("Generated Requirements", expanded=False):
                st.markdown(st.session_state["generated_requirements"])
                if st.button("Save Requirements", key="save_requirements_planning"):
                    self._save_artifact(st.session_state["generated_requirements"], "requirements.txt")
        else:
            st.info("Requirements will be displayed here after generation.")

        if stories_exist:
            expander_label = "Approved User Stories" if user_stories_approved else "Generated User Stories"
            with st.expander(expander_label, expanded=False):
                story_content = st.session_state.get("generated_user_stories", "Error: User stories flag set but no content found.")
                st.markdown(story_content)
                if story_content and st.button("Save User Stories", key="save_user_stories_planning"):
                    self._save_artifact(story_content, "user_stories.txt")

            if not user_stories_approved:
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
                submit_disabled = st.session_state.get("feedback_pending", False) or st.session_state.get("planning_stage_running", False)
                if st.button("Submit Review", key="submit_review_button_planning", disabled=submit_disabled):
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
                        if current_stage not in st.session_state["feedback"]:
                            st.session_state["feedback"][current_stage] = []
                        st.session_state["feedback"][current_stage] = ["accept" if is_approved else comments.strip()]
                        logger.info("Feedback stored: %s", st.session_state["feedback"])
                        st.session_state["needs_resume_after_feedback"] = True
                        if not is_approved:
                            st.session_state["user_stories_generated_flag"] = False
                        st.session_state["feedback_pending"] = False
                        st.write(f"Feedback submitted: {'Approved' if is_approved else 'Rejected with comments.'}")
                        st.write("Session state after feedback: %s", st.session_state)
                        st.rerun()
            else:
                st.success("✅ User stories approved. Planning phase completed.")
                st.markdown("The feedback form is disabled as the Planning Phase is complete.")
        elif requirements_exist and not stories_exist and not user_stories_approved:
            st.info("User stories will be displayed here after generation or if awaiting regeneration after feedback.")
        elif not requirements_exist and not stories_exist and not user_stories_approved:
            st.info("No artifacts generated yet in the Planning phase.")

    @log_entry_exit
    def _display_design_phase(self):
        """Displays the design phase details."""
        st.header("Design Phase")
        st.info("Design documents are being generated based on approved user stories.")

    @log_entry_exit
    def _display_design_artifacts(self):
        """Displays design artifacts and feedback form."""
        st.subheader("Design Artifacts")
        design_artifacts_exist = st.session_state.get("generated_design_documents", False)
        design_documents_approved = st.session_state.get("design_documents_approved", False)

        if design_artifacts_exist:
            expander_label = "Approved Design Documents" if design_documents_approved else "Generated Design Documents"
            with st.expander(expander_label, expanded=False):
                design_documents = st.session_state.get("generated_design_documents", "Error: Design documents not generated.")
                # Add logging to inspect the value of design_documents
                logger.info(f"Value of design_documents: {design_documents}")
                st.markdown(design_documents)
                if st.button("Save Design Documents", key="save_design_documents"):
                    self._save_artifact(design_documents, "design_documents.txt")

            if not design_documents_approved:
                st.markdown("### Feedback on Design Documents")
                decision_options = ("Approve", "Reject")
                selected_decision = st.radio(
                    "Review Decision:",
                    decision_options,
                    key="design_documents_feedback_decision",
                    horizontal=True,
                    index=0
                )
                comments = st.text_area(
                    "Comments (Required for Rejection):",
                    placeholder="Include more details on the design",
                    key="design_documents_feedback_comments"
                )
                submit_disabled = st.session_state.get("feedback_pending", False) or st.session_state.get("design_stage_running", False)
                if st.button("Submit Review", key="submit_review_button_design", disabled=submit_disabled):
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
                        current_stage = "design"
                        if current_stage not in st.session_state["feedback"]:
                            st.session_state["feedback"][current_stage] = []
                        st.session_state["feedback"][current_stage] = ["accept" if is_approved else comments.strip()]
                        logger.info("Feedback stored: %s", st.session_state["feedback"])
                        st.session_state["needs_resume_after_feedback"] = True
                        if not is_approved:
                            st.session_state["design_documents_generated_flag"] = False
                        st.session_state["feedback_pending"] = False
                        st.write(f"Feedback submitted: {'Approved' if is_approved else 'Rejected with comments.'}")
                        st.write("Session state after feedback: %s", st.session_state)
                        st.rerun()
            else:
                st.success("✅ Design documents approved. Design phase completed.")
                st.markdown("The feedback form is disabled as the Design Phase is complete.")
        else:
            st.info("Design documents will be displayed here after generation.")

    @log_entry_exit
    def _display_development_phase(self):
        """Displays the development phase details."""
        st.header("Development Phase")
        st.info("Development artifacts are being generated based on approved design documents.")

    @log_entry_exit
    def _display_development_artifacts(self):
        """Displays development artifacts and feedback form."""
        st.subheader("Development Artifacts")
        development_artifacts_exist = st.session_state.get("generated_development_artifact", False)
        development_artifact_approved = st.session_state.get("development_artifact_approved", False)

        if development_artifacts_exist:
            expander_label = "Approved Development Artifacts" if development_artifact_approved else "Generated Development Artifacts"
            with st.expander(expander_label, expanded=False):
                development_artifact = st.session_state.get("generated_development_artifact", "Error: Development artifacts not generated.")
                st.markdown(development_artifact)
                if st.button("Save Development Artifacts", key="save_development_artifacts"):
                    self._save_artifact(development_artifact, "development_artifact.txt")

            if not development_artifact_approved:
                st.markdown("### Feedback on Development Artifacts")
                decision_options = ("Approve", "Reject")
                selected_decision = st.radio(
                    "Review Decision:",
                    decision_options,
                    key="development_artifact_feedback_decision",
                    horizontal=True,
                    index=0
                )
                comments = st.text_area(
                    "Comments (Required for Rejection):",
                    placeholder="Include details on code improvements",
                    key="development_artifact_feedback_comments"
                )
                submit_disabled = st.session_state.get("feedback_pending", False) or st.session_state.get("development_stage_running", False)
                if st.button("Submit Review", key="submit_review_button_development", disabled=submit_disabled):
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
                        current_stage = "development"
                        if current_stage not in st.session_state["feedback"]:
                            st.session_state["feedback"][current_stage] = []
                        st.session_state["feedback"][current_stage] = ["accept" if is_approved else comments.strip()]
                        logger.info("Feedback stored: %s", st.session_state["feedback"])
                        st.session_state["needs_resume_after_feedback"] = True
                        if not is_approved:
                            st.session_state["development_artifact_generated_flag"] = False
                        st.session_state["feedback_pending"] = False
                        st.write(f"Feedback submitted: {'Approved' if is_approved else 'Rejected with comments.'}")
                        st.write("Session state after feedback: %s", st.session_state)
                        st.rerun()
            else:
                st.success("✅ Development artifacts approved. Development phase completed.")
                st.markdown("The feedback form is disabled as the Development Phase is complete.")
        else:
            st.info("Development artifacts will be displayed here after generation.")

    @log_entry_exit
    def _display_testing_phase(self):
        """Displays the testing phase details."""
        st.header("Testing Phase")
        st.info("Testing artifacts are being generated based on approved development artifacts.")

    @log_entry_exit
    def _display_testing_artifacts(self):
        """Displays testing artifacts and feedback form."""
        st.subheader("Testing Artifacts")
        testing_artifacts_exist = st.session_state.get("generated_testing_artifact", False)
        testing_artifact_approved = st.session_state.get("testing_artifact_approved", False)

        if testing_artifacts_exist:
            expander_label = "Approved Testing Artifacts" if testing_artifact_approved else "Generated Testing Artifacts"
            with st.expander(expander_label, expanded=False):
                testing_artifact = st.session_state.get("generated_testing_artifact", "Error: Testing artifacts not generated.")
                st.markdown(testing_artifact)
                if st.button("Save Testing Artifacts", key="save_testing_artifacts"):
                    self._save_artifact(testing_artifact, "testing_artifact.txt")

            if not testing_artifact_approved:
                st.markdown("### Feedback on Testing Artifacts")
                decision_options = ("Approve", "Reject")
                selected_decision = st.radio(
                    "Review Decision:",
                    decision_options,
                    key="testing_artifact_feedback_decision",
                    horizontal=True,
                    index=0
                )
                comments = st.text_area(
                    "Comments (Required for Rejection):",
                    placeholder="Include details on test case improvements",
                    key="testing_artifact_feedback_comments"
                )
                submit_disabled = st.session_state.get("feedback_pending", False) or st.session_state.get("testing_stage_running", False)
                if st.button("Submit Review", key="submit_review_button_testing", disabled=submit_disabled):
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
                        current_stage = "testing"
                        if current_stage not in st.session_state["feedback"]:
                            st.session_state["feedback"][current_stage] = []
                        st.session_state["feedback"][current_stage] = ["accept" if is_approved else comments.strip()]
                        logger.info("Feedback stored: %s", st.session_state["feedback"])
                        st.session_state["needs_resume_after_feedback"] = True
                        if not is_approved:
                            st.session_state["testing_artifact_generated_flag"] = False
                        st.session_state["feedback_pending"] = False
                        st.write(f"Feedback submitted: {'Approved' if is_approved else 'Rejected with comments.'}")
                        st.write("Session state after feedback: %s", st.session_state)
                        st.rerun()
            else:
                st.success("✅ Testing artifacts approved. Testing phase completed.")
                st.markdown("The feedback form is disabled as the Testing Phase is complete.")
        else:
            st.info("Testing artifacts will be displayed here after generation.")

    @log_entry_exit
    def _display_deployment_phase(self):
        """Displays the deployment phase details."""
        st.header("Deployment Phase")
        st.info("Deployment artifacts are being generated based on approved testing artifacts.")

    @log_entry_exit
    def _display_deployment_artifacts(self):
        """Displays deployment artifacts and feedback form."""
        st.subheader("Deployment Artifacts")
        deployment_artifacts_exist = st.session_state.get("generated_deployment_artifact", False)
        deployment_artifact_approved = st.session_state.get("deployment_artifact_approved", False)

        if deployment_artifacts_exist:
            expander_label = "Approved Deployment Artifacts" if deployment_artifact_approved else "Generated Deployment Artifacts"
            with st.expander(expander_label, expanded=False):
                deployment_artifact = st.session_state.get("generated_deployment_artifact", "Error: Deployment artifacts not generated.")
                st.markdown(deployment_artifact)
                if st.button("Save Deployment Artifacts", key="save_deployment_artifacts"):
                    self._save_artifact(deployment_artifact, "deployment_artifact.txt")

            if not deployment_artifact_approved:
                st.markdown("### Feedback on Deployment Artifacts")
                decision_options = ("Approve", "Reject")
                selected_decision = st.radio(
                    "Review Decision:",
                    decision_options,
                    key="deployment_artifact_feedback_decision",
                    horizontal=True,
                    index=0
                )
                comments = st.text_area(
                    "Comments (Required for Rejection):",
                    placeholder="Include details on deployment improvements",
                    key="deployment_artifact_feedback_comments"
                )
                submit_disabled = st.session_state.get("feedback_pending", False) or st.session_state.get("deployment_stage_running", False)
                if st.button("Submit Review", key="submit_review_button_deployment", disabled=submit_disabled):
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
                        current_stage = "deployment"
                        if current_stage not in st.session_state["feedback"]:
                            st.session_state["feedback"][current_stage] = []
                        st.session_state["feedback"][current_stage] = ["accept" if is_approved else comments.strip()]
                        logger.info("Feedback stored: %s", st.session_state["feedback"])
                        st.session_state["needs_resume_after_feedback"] = True
                        if not is_approved:
                            st.session_state["deployment_artifact_generated_flag"] = False
                        st.session_state["feedback_pending"] = False
                        st.write(f"Feedback submitted: {'Approved' if is_approved else 'Rejected with comments.'}")
                        st.write("Session state after feedback: %s", st.session_state)
                        st.rerun()
            else:
                st.success("✅ Deployment artifacts approved. Deployment phase completed.")
                st.markdown("The feedback form is disabled as the Deployment Phase is complete.")
        else:
            st.info("Deployment artifacts will be displayed here after generation.")

    @log_entry_exit
    def _collect_project_requirements(self):
        """Displays the form to collect initial project details."""
        # DefaultProjectName = "demo_project"
        # DefaultDescription = "demo_description"
        # DefaultGoals = "demo_goals"
        # DefaultScope = "demo_scope"
        # DefaultObjectives = "demo_objectives"
        
        DefaultProjectName = "The Book Nook"
        DefaultDescription = """Develop a user-friendly mobile application for "The Book Nook," a local bookstore in Bangalore, 
                                to allow customers to browse their inventory, place orders online, and learn about upcoming events."""
        DefaultGoals = """ Increase sales and revenue for The Book Nook.
                            Enhance customer engagement and loyalty.
                            Modernize The Book Nook's presence and reach a wider audience in Bangalore. """
        DefaultScope = """ Inclusions:
                                Developing a mobile application compatible with Android and iOS.
                                Features: Browsing book catalog with search and filtering, viewing book details (description, author, price, availability), creating user accounts, adding books to a shopping cart, secure online payment integration, order history, push notifications for new arrivals and events, information about store hours and location.
                                Integration with the bookstore's existing inventory management system.
                                Basic user support documentation.
                            Exclusions:
                                Developing a separate tablet application.
                                Implementing a loyalty points program (will be considered in a future phase).
                                Integrating with social media platforms for direct purchasing.
                                Providing real-time inventory updates beyond a daily sync.
                                Developing advanced analytics dashboards for the bookstore owner in this phase."""
        DefaultObjectives = """Increase online sales by 15% within the first six months of the app launch (Measurable, Achievable, Relevant, Time-bound).
                            Achieve an average user rating of 4.5 stars or higher on both app stores within three months of launch (Measurable, Achievable, Relevant, Time-bound).
                            Acquire 500 new registered app users within the first month of launch (Measurable, Achievable, Relevant, Time-bound).
                            Successfully integrate the app with the existing inventory system with no data loss by the end of the development phase 
                            (Measurable, Achievable, Relevant, Time-bound). """
        

        st.subheader("Define Project Details")
        with st.form("sdlc_requirements_form"):
            project_name = st.text_input("Project Name", value= DefaultProjectName, placeholder=DefaultProjectName)
            project_description = st.text_area("Project Description", value=DefaultDescription, placeholder=DefaultDescription, height=150)
            project_goals = st.text_area("Project Goals", value=DefaultGoals, placeholder=DefaultGoals, height=100)
            project_scope = st.text_area("Project Scope", value=DefaultScope, placeholder=DefaultScope, height=200)
            project_objectives = st.text_area("Project Objectives", value=DefaultObjectives, placeholder=DefaultObjectives, height=150)

            submit = st.form_submit_button("Generate Requirements & User Stories")
            if submit and not st.session_state.get("planning_stage_running"):
                st.session_state["project_name"] = project_name.strip()
                st.session_state["project_description"] = project_description.strip() 
                st.session_state["project_goals"] = project_goals.strip()
                st.session_state["project_scope"] = project_scope.strip()
                st.session_state["project_objectives"] = project_objectives.strip()
                st.session_state["sdlc_stage"] = "planning"
                logger.info("Initial project details submitted. Running graph for the first time.")
                st.session_state["planning_stage_running"] = True
                try:
                    self._run_sdlc_graph_initial("planning")
                finally:
                    st.session_state["planning_stage_running"] = False
                st.rerun()

    @log_entry_exit
    def _run_sdlc_graph_initial(self, stage: str):
        """Runs the SDLC graph for the first time with initial project details."""
        session_id = self.config.get("configurable", {}).get("session_id")
        if not session_id:
            logger.error("Session ID not found in config! Cannot start graph.")
            st.error("Critical error: Session ID missing. Please restart.")
            return

        input_data = {"session_id": session_id, "sdlc_stage": stage}
        # Add project details to input_data
        input_data["project_name"] = st.session_state.get("project_name", "")
        input_data["project_description"] = st.session_state.get("project_description", "")
        input_data["project_goals"] = st.session_state.get("project_goals", "")
        input_data["project_scope"] = st.session_state.get("project_scope", "")
        input_data["project_objectives"] = st.session_state.get("project_objectives", "")
        requirements = None
        user_stories = None
        design_documents = None
        development_artifact = None
        testing_artifact = None
        deployment_artifact = None
        logger.info(f"Running SDLC graph initially with input_data: {input_data}...")

        artifact_description = {
            "planning": "requirements and user stories",
            "design": "design documents",
            "development": "development artifact",
            "testing": "testing artifact",
            "deployment": "deployment artifact"
        }.get(stage, "artifacts")

        with st.spinner(f"Generating initial {artifact_description}..."):
            try:
                for event_dict in self.graph.stream(input_data, self.config):
                    logger.info(f"Initial Run Event: {event_dict}")
                    if "__interrupt__" in event_dict:
                        logger.info("Graph interrupted as expected after generating artifacts.")
                        break
                    for node_name, node_output_dict in event_dict.items():
                        if node_name in ["__checkpoint__", "__interrupt__"]:
                            continue
                        if node_output_dict is None:
                            continue
                        if not isinstance(node_output_dict, dict):
                            logger.warning(f"Node '{node_name}' output is not a dict: {node_output_dict}. Skipping artifact extraction.")
                            continue
                        logger.info(f"Processing output from node '{node_name}'.")
                        if "generated_requirements" in node_output_dict:
                            requirements = node_output_dict["generated_requirements"]
                        if "user_stories" in node_output_dict:
                            user_stories = node_output_dict["user_stories"]
                        if "design_documents" in node_output_dict:
                            design_documents = node_output_dict["design_documents"]
                        if "development_artifact" in node_output_dict:
                            development_artifact = node_output_dict["development_artifact"]
                        if "testing_artifact" in node_output_dict:
                            testing_artifact = node_output_dict["testing_artifact"]
                        if "deployment_artifact" in node_output_dict:
                            deployment_artifact = node_output_dict["deployment_artifact"]
            except Exception as e:
                logger.error(f"Error during initial graph stream: {e}", exc_info=True)
                st.error(f"An error occurred during graph execution: {e}")
                return

        st.session_state["generated_requirements"] = requirements
        st.session_state["generated_user_stories"] = user_stories
        st.session_state["generated_design_documents"] = design_documents
        st.session_state["generated_development_artifact"] = development_artifact
        st.session_state["generated_testing_artifact"] = testing_artifact
        st.session_state["generated_deployment_artifact"] = deployment_artifact

        st.session_state["requirements_generated"] = requirements is not None
        st.session_state["user_stories_generated_flag"] = user_stories is not None
        st.session_state["design_documents_generated_flag"] = design_documents is not None
        st.session_state["development_artifact_generated_flag"] = development_artifact is not None
        st.session_state["testing_artifact_generated_flag"] = testing_artifact is not None
        st.session_state["deployment_artifact_generated_flag"] = deployment_artifact is not None
        logger.info("Initial graph run finished (interrupted). Artifacts stored in session state.")

    @log_entry_exit
    def _resume_sdlc_graph(self):
        """Resumes the graph execution from the checkpoint after feedback."""
        logger.info("Resuming SDLC graph execution...")
        feedback_data = st.session_state.get("feedback")
        logger.info(f"Feedback data from session state: %s", feedback_data)

        if "configurable" not in self.config or "thread_id" not in self.config["configurable"]:
            logger.error("Thread ID missing in main config. Cannot resume.")
            st.error("Cannot resume workflow: Session thread ID is missing in configuration.")
            st.session_state["needs_resume_after_feedback"] = False
            return
        thread_id = self.config["configurable"]["thread_id"]

        update_payload = {}
        try:
            if feedback_data:
                update_payload['feedback'] = feedback_data
                current_stage_value = st.session_state.get("sdlc_stage")
                update_payload['current_stage'] = SDLCStages(current_stage_value)
                if isinstance(feedback_data, dict) and current_stage_value in feedback_data:
                    stage_feedback = feedback_data.get(current_stage_value, [])
                    last_feedback = stage_feedback[-1].strip().lower() if stage_feedback else ""
                    update_payload['feedback_decision'] = "accept" if last_feedback == "accept" else "reject"
                else:
                    update_payload['feedback_decision'] = "reject"
                logger.info(f"Update payload prepared: {update_payload}")
            else:
                logger.warning("Resume triggered but no feedback data found in session state.")
                update_payload['feedback_decision'] = "reject"
                update_payload['current_stage'] = SDLCStages(st.session_state.get("sdlc_stage", "planning"))
            update_payload['last_updated'] = datetime.now().isoformat()
        except Exception as e:
            logger.error(f"Error preparing update payload for thread_id {thread_id}: {e}", exc_info=True)
            st.error(f"Error preparing resume data: {e}. Please restart.")
            st.session_state["needs_resume_after_feedback"] = False
            return

        if update_payload:
            logger.info(f"Updating graph state for thread_id {thread_id} with payload: {update_payload}")
            try:
                self.graph.update_state(config=self.config, values=update_payload)
                logger.info(f"[OK] Updated graph state for thread_id {thread_id} with payload: {update_payload}")
            except Exception as e:
                logger.error(f"Error calling graph.update_state for thread_id {thread_id}: {e}", exc_info=True)
                st.error(f"Error updating workflow state: {e}. Please restart.")
                st.session_state["needs_resume_after_feedback"] = False
                return

        with st.spinner("Processing feedback and continuing workflow..."):
            try:
                final_state = {}
                logger.info("Attempting graph stream with Command(resume=True)")
                for event in self.graph.stream(Command(resume=True), config=self.config, stream_mode="values"):
                    logger.debug(f"Resume Stream Event: {event}")
                    node = event.get("log", {}).get("actions", [{}])[0].get("node")
                    state = event
                    if not isinstance(state, dict):
                        logger.warning(f"Received non-dict state in stream: {type(state)}. Skipping.")
                        continue
                    if node:
                        logger.info(f"Executing node: {node}")
                    logger.info(f"Node '{node}' generated state update.")
                    final_state.update(state)
                    if "generated_requirements" in state and state["generated_requirements"] is not None:
                        st.session_state["generated_requirements"] = state["generated_requirements"]
                        st.session_state["requirements_generated"] = True
                    if "user_stories" in state and state["user_stories"] is not None:
                        st.session_state["generated_user_stories"] = state["user_stories"]
                        st.session_state["user_stories_generated_flag"] = True
                    if "design_documents" in state and state["design_documents"] is not None:
                        st.session_state["generated_design_documents"] = state["design_documents"]
                        st.session_state["design_documents_generated_flag"] = True
                    if "development_artifact" in state and state["development_artifact"] is not None:
                        st.session_state["generated_development_artifact"] = state["development_artifact"]
                        st.session_state["development_artifact_generated_flag"] = True
                    if "testing_artifact" in state and state["testing_artifact"] is not None:
                        st.session_state["generated_testing_artifact"] = state["testing_artifact"]
                        st.session_state["testing_artifact_generated_flag"] = True
                    if "deployment_artifact" in state and state["deployment_artifact"] is not None:
                        st.session_state["generated_deployment_artifact"] = state["deployment_artifact"]
                        st.session_state["deployment_artifact_generated_flag"] = True
            except Exception as e:
                logger.error(f"Error during graph stream after resume: {e}", exc_info=True)
                st.error(f"An error occurred during workflow resumption: {e}")
                return

            final_feedback_decision = final_state.get("feedback_decision")
            logger.info(f"Final feedback decision after stream: {final_feedback_decision}")

            if final_feedback_decision == "accept":
                if st.session_state["sdlc_stage"] == "planning":
                    st.session_state["user_stories_approved"] = True
                    st.session_state["sdlc_stage"] = "design"
                    logger.info("User stories approved. Proceeding to design phase.")
                elif st.session_state["sdlc_stage"] == "design":
                    st.session_state["design_documents_approved"] = True
                    st.session_state["sdlc_stage"] = "development"
                    logger.info("Design documents approved. Proceeding to development phase.")
                elif st.session_state["sdlc_stage"] == "development":
                    st.session_state["development_artifact_approved"] = True
                    st.session_state["sdlc_stage"] = "testing"
                    logger.info("Development artifact approved. Proceeding to testing phase.")
                elif st.session_state["sdlc_stage"] == "testing":
                    st.session_state["testing_artifact_approved"] = True
                    st.session_state["sdlc_stage"] = "deployment"
                    logger.info("Testing artifact approved. Proceeding to deployment phase.")
                elif st.session_state["sdlc_stage"] == "deployment":
                    st.session_state["deployment_artifact_approved"] = True
                    st.session_state["sdlc_stage"] = "complete"
                    logger.info("Deployment artifact approved. SDLC complete.")
                else:
                    logger.error("Unknown SDLC stage: %s", st.session_state["sdlc_stage"])
                    st.error("Unknown SDLC stage. Cannot proceed.")
                    st.session_state["needs_resume_after_feedback"] = False
                    return
            else:
                logger.info(f"Graph looped back. Final feedback decision: {final_feedback_decision}")

            st.session_state["needs_resume_after_feedback"] = False
            logger.info("Graph resumption completed. Approved flags: %s", {
                "planning": st.session_state.get("user_stories_approved"),
                "design": st.session_state.get("design_documents_approved"),
                "development": st.session_state.get("development_artifact_approved"),
                "testing": st.session_state.get("testing_artifact_approved"),
                "deployment": st.session_state.get("deployment_artifact_approved")
            })
            st.rerun()

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
