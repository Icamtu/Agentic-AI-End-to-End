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
from langgraph.graph import END # Import END for checking graph completion

# --- Pydantic Model for Feedback ---
class ReviewFeedback(BaseModel):
    approved: bool = Field(description="Approval status: True for approved, False for rejected")
    comments: str = Field(description="Reviewer comments", default="") # Default to empty string

# --- Main Display Class ---
class DisplaySdlcResult:
    def __init__(self, graph, config):
        self.graph = graph
        self.config = config
        self._initialize_session_state()

    def _initialize_session_state(self):
        """Initialize session state variables if they don't exist."""
        defaults = {
            "sdlc_stage": "planning", # Tracks the conceptual stage
            "project_name": "",
            "project_description": "",
            "project_goals": "",
            "project_scope": "",
            "project_objectives": "",
            "requirements_generated": False, # UI flag: Have requirements been generated at least once?
            "user_stories_generated": False, # UI flag: Have user stories been generated and are ready for review/approved?
            "generated_requirements": None, # Stores the actual artifact text
            "generated_user_stories": None, # Stores the actual artifact text
            "feedback": None, # Stores feedback dict for process_feedback node (transient)
            "needs_resume_after_feedback": False, # Flag to trigger graph resume
            "graph_completed": False, # Flag to indicate workflow completion (reached END)
            "graph_running": False, # Flag to prevent concurrent runs/UI updates during stream
        }
        for key, value in defaults.items():
            if key not in st.session_state:
                st.session_state[key] = value

    @log_entry_exit
    def handle_sdlc_workflow(self):
        """Manages the overall SDLC workflow display and interaction in Streamlit."""
        st.title("Software Development Life Cycle (SDLC) Workflow")

        phases = ["Planning", "Design", "Development", "Testing", "Deployment"]
        icons = ["🗓️", "📐", "💻", "🧪", "🚀"]
        tabs = st.tabs([f"{icon} {phase}" for icon, phase in zip(icons, phases)])

        # --- Check if we need to resume the graph ---
        needs_resume = st.session_state.get("needs_resume_after_feedback", False)
        if needs_resume and not st.session_state.get("graph_running", False):
            logger.info("Detected need to resume graph after feedback.")
            st.session_state["needs_resume_after_feedback"] = False # Reset the flag immediately
            st.session_state["graph_running"] = True # Set lock
            self._resume_sdlc_graph() # Call the function to handle resumption
            st.session_state["graph_running"] = False # Release lock
            # Rerun to update the UI based on the resumed graph's state changes
            st.rerun()
            return # Stop further processing in this run

        # --- Display content based on the current state ---
        with tabs[0]:  # Planning Tab
            # Only show collection form if requirements haven't been generated yet
            if not st.session_state.get("requirements_generated"):
                 self._display_planning_phase() # Contains _collect_project_requirements
            # Always display artifacts and feedback form if artifacts exist
            # The feedback form is only active if stories are generated
            self._display_planning_artifacts()

        # --- Placeholder Tabs ---
        with tabs[1]: self._display_design_phase(); self._display_design_artifacts()
        with tabs[2]: self._display_development_phase(); self._display_development_artifacts()
        with tabs[3]: self._display_testing_phase(); self._display_testing_artifacts()
        with tabs[4]: self._display_deployment_phase(); self._display_deployment_artifacts()

        # --- Display Completion Status ---
        if st.session_state.get("graph_completed"):
            st.success("✅ SDLC Planning Phase Completed Successfully!")

        # --- Restart Button ---
        st.markdown("---")
        if st.button("Restart SDLC Workflow", key="restart_button"):
            self._reset_session_state()
            st.rerun()

    @log_entry_exit
    def _reset_session_state(self):
        """Resets relevant session state keys to start the workflow over."""
        keys_to_reset = list(st.session_state.keys()) # Get all keys
        logger.info("Resetting session state.")
        for key in keys_to_reset:
            # Avoid deleting internal Streamlit keys or keys we might want to persist
            if not key.startswith("_"): # Basic check, adjust if needed
                 del st.session_state[key]
        # Re-initialize after clearing
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
        stories_exist = st.session_state.get("user_stories_generated") # This flag indicates readiness for review/approval

        # Display Requirements if they exist
        if requirements_exist:
            with st.expander("Generated Requirements", expanded=True):
                st.markdown(st.session_state["generated_requirements"])
                if st.button("Save Requirements", key="save_requirements_planning"):
                    self._save_artifact(st.session_state["generated_requirements"], "requirements.txt")
        else:
             st.info("Requirements will be displayed here after generation.")

        # Display User Stories and Feedback Form ONLY if stories are generated and ready for review
        if stories_exist:
            with st.expander("Generated User Stories", expanded=True):
                st.markdown(st.session_state["generated_user_stories"])
                if st.button("Save User Stories", key="save_user_stories_planning"):
                    self._save_artifact(st.session_state["generated_user_stories"], "user_stories.txt")

            # --- Feedback Section ---
            # Only show feedback if the graph isn't completed yet
            if not st.session_state.get("graph_completed"):
                st.markdown("### Feedback on User Stories")
                decision_options = ("Approve", "Reject")
                selected_decision = st.radio(
                    "Review Decision:",
                    decision_options,
                    key="user_story_feedback_decision",
                    horizontal=True,
                    index=0 # Default to Approve
                )

                comments = ""
                if selected_decision == "Reject":
                    comments = st.text_area(
                        "Comments (Required for Rejection):",
                        value="Include Subscriptions model to retain customer", # Example default
                        placeholder="Explain why the user stories need revision...",
                        key="user_story_feedback_comments"
                    )

                if st.button("Submit Review", key="submit_review_button"):
                    is_approved = (selected_decision == "Approve")
                    if not is_approved and not comments.strip():
                        st.error("Comments are required when rejecting.")
                    else:
                        feedback_obj = ReviewFeedback(approved=is_approved, comments=comments if not is_approved else "")
                        logger.info("Feedback submitted: %s", feedback_obj)
                        st.success(f"Feedback submitted: {'Approved' if is_approved else 'Rejected with comments.'}")

                        # Store feedback dict for the process_feedback node
                        st.session_state["feedback"] = feedback_obj.model_dump()
                        logger.info("Session state updated with feedback: %s", st.session_state["feedback"])

                        # --- Signal that the graph needs to resume ---
                        st.session_state["needs_resume_after_feedback"] = True

                        # If rejected, immediately hide the stories from the UI until regenerated
                        # The resume logic will handle updating the actual artifacts
                        if not is_approved:
                            st.session_state["user_stories_generated"] = False

                        logger.info("Feedback stored. Triggering rerun for graph resumption.")
                        st.rerun() # Rerun to trigger the resume logic in handle_sdlc_workflow
            else:
                st.success("User stories approved.") # Show if graph is completed

        # Indicate waiting state if requirements exist but stories don't (yet)
        elif requirements_exist and not stories_exist:
            st.info("User stories will be displayed here after generation or if awaiting regeneration after feedback.")
        # Initial state message
        elif not requirements_exist and not stories_exist:
             st.info("No artifacts generated yet in the Planning phase.")


    # --- Placeholder Display Functions for Other Phases ---
    @log_entry_exit
    def _display_design_phase(self):
        st.header("Design Phase")
        st.info("Design phase details will be displayed here in future implementations.")

    @log_entry_exit
    def _display_design_artifacts(self):
        st.subheader("Design Artifacts")
        st.info("Design artifacts (e.g., architecture diagrams, UI mockups) will be displayed here.")

    @log_entry_exit
    def _display_development_phase(self):
        st.header("Development Phase")
        st.info("Development phase details will be displayed here in future implementations.")

    @log_entry_exit
    def _display_development_artifacts(self):
        st.subheader("Development Artifacts")
        st.info("Development artifacts (e.g., code snippets, build logs) will be displayed here.")

    @log_entry_exit
    def _display_testing_phase(self):
        st.header("Testing Phase")
        st.info("Testing phase details will be displayed here in future implementations.")

    @log_entry_exit
    def _display_testing_artifacts(self):
        st.subheader("Testing Artifacts")
        st.info("Testing artifacts (e.g., test cases, bug reports) will be displayed here.")

    @log_entry_exit
    def _display_deployment_phase(self):
        st.header("Deployment Phase")
        st.info("Deployment phase details will be displayed here in future implementations.")

    @log_entry_exit
    def _display_deployment_artifacts(self):
        st.subheader("Deployment Artifacts")
        st.info("Deployment artifacts (e.g., deployment plans, monitoring dashboards) will be displayed here.")

    # --- Requirement Collection Form ---
    @log_entry_exit
    def _collect_project_requirements(self):
        """Displays the form to collect initial project details."""
        # Default values (kept for brevity)
        DefaultProjectName = "The Book Nook"
        DefaultDescription = "..." # Truncated
        DefaultGoals = "..." # Truncated
        DefaultScope = "..." # Truncated
        DefaultObjectives = "..." # Truncated

        st.subheader("Define Project Details")
        with st.form("sdlc_requirements_form"):
            project_name = st.text_input("Project Name", value=st.session_state.get("project_name", DefaultProjectName), placeholder=DefaultProjectName)
            project_description = st.text_area("Project Description", value=st.session_state.get("project_description", DefaultDescription), placeholder=DefaultDescription, height=150)
            project_goals = st.text_area("Project Goals", value=st.session_state.get("project_goals", DefaultGoals), placeholder=DefaultGoals, height=100)
            project_scope = st.text_area("Project Scope", value=st.session_state.get("project_scope", DefaultScope), placeholder=DefaultScope, height=200)
            project_objectives = st.text_area("Project Objectives", value=st.session_state.get("project_objectives", DefaultObjectives), placeholder=DefaultObjectives, height=150)

            submit = st.form_submit_button("Generate Requirements & User Stories")
            if submit and not st.session_state.get("graph_running", False):
                # Update session state with form values
                st.session_state["project_name"] = project_name.strip() or DefaultProjectName
                st.session_state["project_description"] = project_description.strip() or DefaultDescription
                st.session_state["project_goals"] = project_goals.strip() or DefaultGoals
                st.session_state["project_scope"] = project_scope.strip() or DefaultScope
                st.session_state["project_objectives"] = project_objectives.strip() or DefaultObjectives
                st.session_state["sdlc_stage"] = "planning" # Ensure stage is set

                logger.info("Initial project details submitted. Running graph for the first time.")
                st.session_state["graph_running"] = True # Set lock
                self._run_sdlc_graph_initial() # Call the initial run function
                st.session_state["graph_running"] = False # Release lock
                st.rerun() # Rerun to display the generated artifacts

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
                    event_key = list(event.keys())[0] # Get the node name or signal

                    # Explicitly check for interrupt signal
                    if event_key == "__interrupt__":
                         logger.info("Graph interrupted as expected after generating artifacts.")
                         # No 'break' needed, stream stops automatically
                         # Capture the state *just before* the interrupt
                         # Note: LangGraph checkpointer handles the actual state saving
                         # We just need the artifacts for the UI
                         last_node_state = event.get("__interrupt__") # The state *at* interrupt
                         if last_node_state:
                             requirements = last_node_state.get("generated_requirements", requirements)
                             user_stories = last_node_state.get("generated_user_stories", user_stories)
                         break # Exit loop after interrupt is handled

                    # Process node updates
                    for node, state in event.items():
                        if state is None: continue
                        logger.info(f"Node '{node}' updated state.")
                        # Capture the latest generated artifacts from the state
                        if "generated_requirements" in state:
                            requirements = state["generated_requirements"]
                        if "user_stories" in state:
                            user_stories = state["user_stories"]

            except Exception as e:
                 logger.error(f"Error during initial graph stream: {e}", exc_info=True)
                 st.error(f"An error occurred during graph execution: {e}")
                 return # Stop processing if stream fails

        # Update session state after the initial run (which was interrupted)
        st.session_state["generated_requirements"] = requirements
        st.session_state["generated_user_stories"] = user_stories
        st.session_state["requirements_generated"] = requirements is not None
        st.session_state["user_stories_generated"] = user_stories is not None # Mark stories as generated and ready for review
        logger.info("Initial graph run finished (interrupted). Artifacts stored in session state.")


    @log_entry_exit
    def _resume_sdlc_graph(self):
        """Resumes the graph execution from the checkpoint after feedback."""
        logger.info("Resuming SDLC graph execution...")
        # Input is {} instead of None, as process_feedback reads from st.session_state

        # --- Add detailed logging before the stream call ---
        logger.info(f"Attempting resume with config: {self.config}")
        try:
            # Assuming self.memory is the MemorySaver instance used in the graph
            if hasattr(self, 'graph') and hasattr(self.graph, 'checkpointer') and hasattr(self.graph.checkpointer, 'storage'):
                 thread_id = self.config.get("configurable", {}).get("thread_id", "N/A")
                 checkpoint_exists = thread_id in self.graph.checkpointer.storage
                 logger.info(f"Checkpointer storage keys: {list(self.graph.checkpointer.storage.keys())}")
                 logger.info(f"Checkpoint for current thread_id ({thread_id}) exists: {checkpoint_exists}")
                 if checkpoint_exists:
                     pass
            else:
                 logger.warning("Could not access checkpointer storage for inspection.")
        except Exception as log_err:
            logger.warning(f"Could not inspect checkpointer storage: {log_err}")
        # --- End detailed logging ---

        requirements = st.session_state.get("generated_requirements")
        user_stories = st.session_state.get("generated_user_stories")
        graph_completed_flag = False

        with st.spinner("Processing feedback and continuing workflow..."):
            try:
                # --- MODIFICATION: Pass {} instead of None ---
                for event in self.graph.stream({}, self.config): # Pass {} as input to resume
                # --- END MODIFICATION ---

                    # If this loop runs, the logs below will appear
                    logger.info(f"Resume Event: {event}")
                    event_key = list(event.keys())[0] # Get node name or signal

                    # Check if the graph reached the end after resuming
                    if event_key == END:
                         logger.info("Graph reached END after resuming.")
                         graph_completed_flag = True
                         final_state = event.get(END)
                         if final_state:
                             requirements = final_state.get("generated_requirements", requirements)
                             user_stories = final_state.get("generated_user_stories", user_stories)
                         break

                    # Process node updates during resume
                    for node, state in event.items():
                        if state is None: continue
                        logger.info(f"Node '{node}' updated state during resume.")
                        if "generated_requirements" in state:
                            requirements = state["generated_requirements"]
                            logger.info("Requirements potentially updated during resume.")
                        if "user_stories" in state:
                            user_stories = state["user_stories"]
                            logger.info("User stories potentially updated during resume.")

            except Exception as e:
                 logger.error(f"Error during graph resume stream: {e}", exc_info=True)
                 st.error(f"An error occurred during graph resumption: {e}")
                 return

        # --- Update session state after resume processing ---
        st.session_state["generated_requirements"] = requirements
        st.session_state["generated_user_stories"] = user_stories
        st.session_state["requirements_generated"] = requirements is not None
        st.session_state["user_stories_generated"] = user_stories is not None
        st.session_state["graph_completed"] = graph_completed_flag

        logger.info("Graph resumption processing finished.")


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

