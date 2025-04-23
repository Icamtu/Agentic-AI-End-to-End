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
import os  # Import the os module


class ReviewFeedback(BaseModel):
    approved: bool = Field(description="Approval status: True for approved, False for rejected")
    comments: str = Field(description="Reviewer comments")

class DisplaySdlcResult:
    def __init__(self, graph, config):
        self.graph = graph
        self.config = config
        self._initialize_session_state()

    def _initialize_session_state(self):
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
        }
        for key, value in defaults.items():
            if key not in st.session_state:
                st.session_state[key] = value

    @log_entry_exit
    def handle_sdlc_workflow(self):
        st.title("Software Development Life Cycle (SDLC) Workflow")

        phases = ["Planning", "Design", "Development", "Testing", "Deployment"]
        icons = ["🗓️", "📐", "💻", "🧪", "🚀"]
        tabs = st.tabs([f"{icon} {phase}" for icon, phase in zip(icons, phases)])

        with tabs[0]:  # Planning Tab
            self._display_planning_phase()
            self._display_planning_artifacts()

        with tabs[1]:  # Design Tab
            self._display_design_phase()
            self._display_design_artifacts()

        with tabs[2]:  # Development Tab
            self._display_development_phase()
            self._display_development_artifacts()

        with tabs[3]:  # Testing Tab
            self._display_testing_phase()
            self._display_testing_artifacts()

        with tabs[4]:  # Deployment Tab
            self._display_deployment_phase()
            self._display_deployment_artifacts()

        st.markdown("---")
        if st.button("Restart SDLC Workflow", key="restart_button"):
            self._reset_session_state()
            st.rerun()

    @log_entry_exit
    def _reset_session_state(self):
        keys_to_reset = [
            "sdlc_stage", "project_name", "project_description", "project_goals",
            "project_scope", "project_objectives", "requirements_generated",
            "user_stories_generated", "generated_requirements", "generated_user_stories"
        ]
        for key in keys_to_reset:
            if key in st.session_state:
                del st.session_state[key]

    @log_entry_exit
    def _display_planning_phase(self):
        st.header("Planning Phase")
        self._collect_project_requirements()

    @log_entry_exit
    def _display_planning_artifacts(self):
        st.subheader("Planning Artifacts")
        if st.session_state.get("requirements_generated"):
            with st.expander("Generated Requirements"):
                st.subheader("Generated Requirements")
                st.markdown(st.session_state["generated_requirements"].content)
                if st.button("Save Requirements", key="save_requirements_planning"):  
                    self._save_artifact(st.session_state["generated_requirements"].content, "requirements.txt")
        if st.session_state.get("user_stories_generated"):
            with st.expander("Generated User Stories"):
                st.subheader("Generated User Stories")
                st.markdown(st.session_state["generated_user_stories"].content)
                if st.button("Save User Stories", key="save_user_stories_planning"):  
                    self._save_artifact(st.session_state["generated_user_stories"].content, "user_stories.txt")
            st.markdown("### feedback")
            feedback = st.radio("Is the user story approved?", ("Yes", "No"))
            if feedback == "Yes":
                st.success("User story approved.")
            else:
                st.error("User story rejected.")
                comments = st.text_area("Comments", placeholder="Enter your comments here...")
                if st.button("Submit Feedback"):
                    st.feedback = ReviewFeedback(approved=False, comments=comments)
                    st.success(f"Feedback submitted: {st.feedback}")
                    st.write(f"Comments: {st.feedback.comments}")
                    # st.rerun()

        if not st.session_state.get("requirements_generated") and not st.session_state.get("user_stories_generated"):
            st.info("No artifacts generated yet in the Planning phase.")
        elif not st.session_state.get("requirements_generated"):
            st.info("Requirements will be displayed here after generation.")
        elif not st.session_state.get("user_stories_generated"):
            st.info("User stories will be displayed here after generation.")

    @log_entry_exit
    def _display_design_phase(self):
        st.header("Design Phase")
        st.info("Design phase details will be displayed here in future implementations.")

    @log_entry_exit
    def _display_design_artifacts(self):
        st.subheader("Design Artifacts")
        st.info("Design phase details will be displayed here in future implementations.")
    @log_entry_exit
    def _display_development_phase(self):
        st.header("Development Phase")
        st.info("Design phase details will be displayed here in future implementations.")

    @log_entry_exit
    def _display_development_artifacts(self):
        st.subheader("Development Artifacts")
        st.info("Development artifacts (e.g., code snippets, architecture diagrams) will be displayed here in future implementations.")

    @log_entry_exit
    def _display_testing_phase(self):
        st.header("Testing Phase")
        st.info("Design phase details will be displayed here in future implementations.")

    @log_entry_exit
    def _display_testing_artifacts(self):
        st.subheader("Testing Artifacts")
        st.info("Testing artifacts (e.g., test cases, test reports) will be displayed here in future implementations.")

    @log_entry_exit
    def _display_deployment_phase(self):
        st.header("Deployment Phase")
        if st.session_state.get("user_stories_generated"):
            st.info("Deployment planning and execution based on finalized user stories (to be implemented).")
        else:
            st.info("User stories need to be generated before deployment planning.")
        self._display_deployment_artifacts()

    @log_entry_exit
    def _display_deployment_artifacts(self):
        st.subheader("Deployment Artifacts")
        st.info("Deployment artifacts (e.g., deployment plans, configuration files) will be displayed here in future implementations.")

    @log_entry_exit
    def _collect_project_requirements(self):
        DefaultProjectName = "The Book Nook"
        DefaultDescription = """Develop a user-friendly mobile application for "The Book Nook,"
                                    a local bookstore in Bangalore, to allow customers to browse their inventory, place orders online
                                    and learn about upcoming events.The app should have a clean, modern design and be easy to navigate.
                                    The app should also include a feature for customers to sign up for a loyalty program that rewards them with
                                    points for every purchase they make."""

        DefaultGoals = """Increase sales and revenue for The Book Nook.
                            Enhance customer engagement and loyalty.
                            Modernize The Book Nook's presence and reach a wider audience in Bangalore."""
        DefaultScope = """Inclusions:
                                        Developing a mobile application compatible with Android and iOS.
                                        Features: Browsing book catalog with search and filtering, viewing book details (description, author, price, availability), creating user accounts, adding books to a shopping cart, secure online payment integration, order history, push notifications for new arrivals and events, information about store hours and location.
                                        Integration with the bookstore's existing inventory management system.
                                        Basic user support documentation.
                                    Exclusions:
                                        Developing a separate tablet application.
                                        Implementing a loyalty points program (will be considered in a future phase).
                                        Integrating with social media platforms for direct purchasing.
                                        Providing real-time inventory updates beyond a daily sync.
                                        Developing advanced analytics dashboards for the bookstore owner in this phase.
                                    The app will include features such as:
                                        - User registration and login
                                        - Browsing the bookstore's inventory
                                        - Online ordering and payment processing
                                        - Event calendar and notifications
                                        - Loyalty program sign-up and tracking"""
        DefaultObjectives = """
                                        Increase online sales by 15% within the first six months of the app launch (Measurable, Achievable, Relevant, Time-bound).
                                        Achieve an average user rating of 4.5 stars or higher on both app stores within three months of launch (Measurable, Achievable, Relevant, Time-bound).
                                        Acquire 500 new registered app users within the first month of app launch (Measurable, Achievable, Relevant, Time-bound).
                                        Successfully integrate the app with the existing inventory system with no data loss by the end of the development phase (Measurable, Achievable, Relevant, Time-bound).
                                        Ensure the app is compatible with the latest versions of Android and iOS (Measurable, Achievable, Relevant, Time-bound).
                                        Provide user support documentation and FAQs within the app (Measurable, Achievable, Relevant, Time-bound)."""

        st.header("Collect Project Requirements")
        with st.form("sdlc_requirements_form"):
            project_name = st.text_input("Project Name",
                                         value=st.session_state.get("project_name", ""),
                                         placeholder=DefaultProjectName)

            project_description = st.text_area("Project Description",
                                             value=st.session_state.get("project_description", ""),
                                             placeholder=DefaultDescription)

            project_goals = st.text_area("Project Goals",
                                         value=st.session_state.get("project_goals", ""),
                                         placeholder=DefaultGoals)

            project_scope = st.text_area("Project Scope",
                                         value=st.session_state.get("project_scope", ""),
                                         placeholder=DefaultScope)

            project_objectives = st.text_area("Project Objectives",
                                              value=st.session_state.get("project_objectives", ""),
                                              placeholder=DefaultObjectives)
            submit = st.form_submit_button("Generate Requirements & User Stories")
            if submit:
                for key, value in {
                    "project_name": project_name.strip() or DefaultProjectName,
                    "project_description": project_description.strip() or DefaultDescription,
                    "project_goals": project_goals.strip() or DefaultGoals,
                    "project_scope": project_scope.strip() or DefaultScope,
                    "project_objectives": project_objectives.strip() or DefaultObjectives,
                    "sdlc_stage": "generate_user_stories"
                }.items():
                    st.session_state[key] = value
                logger.info("session state updated with project details: %s", st.session_state)
                self._run_sdlc_graph()
                st.rerun()

    @log_entry_exit
    def _run_sdlc_graph(self):
        # Prepare input for the graph
        input_data = {
            "session_id": self.config["configurable"]["session_id"],
            "current_stage": "planning",
            "project_name": st.session_state["project_name"],
            "project_description": st.session_state["project_description"],
            "project_goals": st.session_state["project_goals"],
            "project_scope": st.session_state["project_scope"],
            "project_objectives": st.session_state["project_objectives"],
            "messages": [HumanMessage(content=json.dumps({
                "project_name": st.session_state["project_name"],
                "project_description": st.session_state["project_description"],
                "project_goals": st.session_state["project_goals"],
                "project_scope": st.session_state["project_scope"],
                "project_objectives": st.session_state["project_objectives"],
            }))]
        }
        requirements = None
        user_stories = None
        logger.info("Running SDLC graph with input data: %s", input_data)
        # Run the graph and collect outputs
        for event in self.graph.stream(input_data, self.config):
            for node, state in event.items():
                if state is None:
                    continue
                if "generated_requirements" in state:
                    requirements = state["generated_requirements"]
                if "user_stories" in state:
                    user_stories = state["user_stories"]
        st.session_state["generated_requirements"] = requirements
        st.session_state["generated_user_stories"] = user_stories
        st.session_state["requirements_generated"] = requirements is not None
        st.session_state["user_stories_generated"] = user_stories is not None


    def _save_artifact(self, data, filename):
        """Saves the artifact data to a file, prompting the user for the download."""
        try:
            # Create a download link using streamlit
            b64 = base64.b64encode(data.encode()).decode()
            st.markdown(f'<a href="data:file/txt;base64,{b64}" download="{filename}">Download {filename}</a>', unsafe_allow_html=True)
            st.success(f"Artifact download link created. Click to download {filename}")

        except Exception as e:
            st.error(f"Error creating download link: {e}")