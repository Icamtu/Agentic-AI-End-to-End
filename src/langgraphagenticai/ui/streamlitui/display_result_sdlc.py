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
            "user_stories_generated_flag": False,
            "generated_requirements": None,
            "generated_user_stories": None,
            "generated_design_documents": None,
            "generated_development_artifact": None,
            "generated_testing_artifact": None,
            "generated_deployment_artifact": None,
            "feedback": None,
            "needs_resume_after_feedback": False,
            "user_stories_approved": False,
            "planning_stage_running": False,
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
        if st.session_state.get("planning_stage_running"):
            st.warning("Workflow is already running. Please wait.")
            logger.warning("Workflow blocked due to planning_stage_running=True")
            return

        # Handle resumption
        if st.session_state.get("needs_resume_after_feedback"):
            logger.info("Detected need to resume graph after feedback.")
            st.session_state["planning_stage_running"] = True
            self._resume_sdlc_graph()
            st.session_state["planning_stage_running"] = False
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
                st.session_state["user_stories"]= st.session_state["generated_user_stories"]
                st.session_state["user_stories_approved"] = True
                # st.session_state["sdlc_stage"] = "design"
                st.success("✅ SDLC Planning Phase Completed Successfully!")
                st.markdown("You can restart the workflow or review the artifacts.")

        with tabs[1]:
            if not st.session_state.get("design_documents_generated"):
                self._display_design_phase()
            self._display_design_artifacts()
        with tabs[2]: self._display_development_phase(); self._display_development_artifacts()
        with tabs[3]: self._display_testing_phase(); self._display_testing_artifacts()
        with tabs[4]: self._display_deployment_phase(); self._display_deployment_artifacts()

        

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
        requirements_exist = st.session_state.get("requirements_generated",False)
        stories_exist = st.session_state.get("user_stories_generated_flag",False)
        user_stories_approved = st.session_state.get("user_stories_approved", False)

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
                            st.session_state["user_stories_generated_flag"] = False
                        st.session_state["feedback_pending"] = False
                        st.write(f"Feedback submitted: {'Approved' if is_approved else 'Rejected with comments.'}{st.session_state["feedback"]}")
                        st.write(f"Feedback processing completed. Graph needs resuming: {st.session_state['needs_resume_after_feedback']}")
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
        # st.markdown(st.session_state["design_documents"])
      
        
    @log_entry_exit
    def _display_design_artifacts(self):
        """Displays design artifacts."""
        st.subheader("Design Artifacts")
        logger.info(f"Approved user stories in session state: %s", st.session_state.get("design_documents", None))
        design_artifacts_exist = st.session_state.get("generated_design_documents",False)
        design_documents_approved = st.session_state.get("design_documents_approved", False)
        
        if design_artifacts_exist:
            expander_design_label = "Approved Design Artifacts" if design_documents_approved else "Generated User Design Artifacts"
            with st.expander(expander_design_label, expanded=False):
                design_documents = st.session_state.get("design_documents", "Error: User stories flag set but no content found.")
                st.markdown(design_documents)
                if st.button("Save Design Documents", key="save_design_documents"):
                    self._save_artifact(design_documents, "design_documents.txt")
            
            if not design_documents_approved:
                st.markdown("### Feedback on Design Artifacts")
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
                submit_disabled = st.session_state.get("feedback_pending", False) or st.session_state.get("planning_stage_running", False)
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
                            st.session_state["user_stories_generated_flag"] = False
                        st.session_state["feedback_pending"] = False
                        st.write(f"Feedback submitted: {'Approved' if is_approved else 'Rejected with comments.'}{st.session_state["feedback"]}")
                        st.write(f"Feedback processing completed. Graph needs resuming: {st.session_state['needs_resume_after_feedback']}")
                        st.write("Session state after feedback: %s", st.session_state)
                        st.rerun()
            else:
                st.success("✅ User stories approved. Planning phase completed.")
                st.markdown("The feedback form is disabled as the workflow is complete.")
            
       
        

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
            if submit and not st.session_state.get("planning_stage_running"):
                st.session_state["project_name"] = project_name.strip() or DefaultProjectName
                st.session_state["project_description"] = project_description.strip() or DefaultDescription
                st.session_state["project_goals"] = project_goals.strip() or DefaultGoals
                st.session_state["project_scope"] = project_scope.strip() or DefaultScope
                st.session_state["project_objectives"] = project_objectives.strip() or DefaultObjectives
                st.session_state["sdlc_stage"] = "planning"
                logger.info("Initial project details submitted. Running graph for the first time.")
                st.session_state["planning_stage_running"] = True
                self._run_sdlc_graph_initial()
                st.session_state["planning_stage_running"] = False
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
        st.session_state["user_stories_generated_flag"] = user_stories is not None
        logger.info("Initial graph run finished (interrupted). Artifacts stored in session state.")



    @log_entry_exit
    def _resume_sdlc_graph(self):
            """Resumes the graph execution from the checkpoint after feedback."""
            logger.info("Resuming SDLC graph execution...")
            feedback_data = st.session_state.get("feedback")
            logger.info(f"Feedback data from session state: %s", feedback_data)

            # Ensure config has thread_id
            if "configurable" not in self.config or "thread_id" not in self.config["configurable"]:
                logger.error("Thread ID missing in main config. Cannot resume.")
                st.error("Cannot resume workflow: Session thread ID is missing in configuration.")
                st.session_state["needs_resume_after_feedback"] = False
                st.session_state["planning_stage_running"] = False
                return
            thread_id = self.config["configurable"]["thread_id"] # Get thread_id from main config

            update_payload = {} # Dictionary for state updates

           
            try:
                if feedback_data:
                    update_payload['feedback'] = feedback_data
                    current_stage_value = 'planning' # TODO: Make this more robust if interrupts happen elsewhere

                    if isinstance(feedback_data, dict) and current_stage_value in feedback_data:
                        last_feedback = feedback_data[current_stage_value][-1].strip().lower() if feedback_data[current_stage_value] else ""
                        update_payload['feedback_decision'] = "accept" if last_feedback == "accept" else "reject"
                    else:
                        update_payload['feedback_decision'] = "reject" # Default safely
                    logger.info(f"Update payload prepared: {update_payload}")
                else:
                    # If no feedback data, we probably shouldn't be resuming this way
                    logger.warning("Resume triggered but no feedback data found in session state.")
                    # Decide how to handle this: maybe default to reject or raise error?
                    update_payload['feedback_decision'] = "reject" # Defaulting to reject if no feedback

                # We can also add/update 'last_updated' timestamp if desired
                update_payload['last_updated'] = datetime.now().isoformat()

            except Exception as e:
                logger.error(f"Error preparing update payload for thread_id {thread_id}: {e}", exc_info=True)
                st.error(f"Error preparing resume data: {e}. Please restart.")
                st.session_state["needs_resume_after_feedback"] = False
                st.session_state["planning_stage_running"] = False
                return

           
            if update_payload:
                try:
                    logger.info(f"Updating graph state for thread_id {thread_id} with payload: {update_payload}")
                    self.graph.update_state(
                        config=self.config, # Pass the main config containing thread_id
                        values=update_payload # Pass only the fields to update
                    )
                    logger.info(f"[OK] Updated graph state for thread_id {thread_id} with payload: {update_payload}")
                except Exception as e:
                    logger.error(f"Error calling graph.update_state for thread_id {thread_id}: {e}", exc_info=True)
                    st.error(f"Error updating workflow state: {e}. Please restart.")
                    st.session_state["needs_resume_after_feedback"] = False
                    st.session_state["planning_stage_running"] = False
                    return
            else:
                logger.warning("No update payload generated, skipping state update.")
               
                st.session_state["needs_resume_after_feedback"] = False
                st.session_state["planning_stage_running"] = False
                return


            # --- Resume Graph Execution using Command(resume=True) ---
            with st.spinner("Processing feedback and continuing workflow..."):
                try:
                    final_state = {}
                    # Revert to using Command(resume=True)
                    logger.info("Attempting graph stream with Command(resume=True)")
                    for event in self.graph.stream(Command(resume=True), config=self.config, stream_mode="values"):
                        logger.debug(f"Resume Stream Event: {event}")

                        node = event.get("log", {}).get("actions", [{}])[0].get("node")
                        state = event

                        if not isinstance(state, dict):
                            logger.warning(f"Received non-dict state in stream: {type(state)}. Skipping.")
                            continue

                        # Log entry into graph nodes if structure allows
                        if node: logger.info(f"Executing node: {node}")

                        logger.info(f"Node '{node}' generated state update.") # Log less verbosely
                        final_state.update(state) # Aggregate the latest state view

                        # Update session state based on the received state from the graph execution
                        if "generated_requirements" in state and state["generated_requirements"] is not None:
                            st.session_state["generated_requirements"] = state["generated_requirements"]
                            st.session_state["requirements_generated"] = True
                        if "user_stories" in state and state["user_stories"] is not None:
                            st.session_state["generated_user_stories"] = state["user_stories"]
                            st.session_state["user_stories_generated_flag"] = True
                        if "feedback_decision" in state:
                            logger.info(f"Feedback decision processed by graph node: {state['feedback_decision']}")

                except Exception as e:
                    logger.error(f"Error during graph stream after update_state/resume: {e}", exc_info=True)
                    st.error(f"An error occurred during workflow resumption: {e}")
                    st.session_state["planning_stage_running"] = False
                    return # Stop execution here

                # --- Post-Stream State Update ---
                final_feedback_decision = final_state.get("feedback_decision")
                logger.info(f"Final feedback decision after stream: {final_feedback_decision}")

                if final_feedback_decision == "accept":
                    if st.session_state["sdlc_stage"] == "planning":
                        st.session_state["user_stories_approved"] = True
                        logger.info("User stories approved. Proceeding to next phase.")
                    elif st.session_state["sdlc_stage"] == "design":
                        st.session_state["design_documents_approved"] = True
                        logger.info("Design documents approved. Proceeding to next phase.")
                    elif st.session_state["sdlc_stage"] == "development":
                        st.session_state["development_artifact_approved"] = True
                        logger.info("Development artifact approved. Proceeding to next phase.")
                    elif st.session_state["sdlc_stage"] == "testing":
                        st.session_state["testing_artifact_approved"] = True
                        logger.info("Testing artifact approved. Proceeding to next phase.")
                    elif st.session_state["sdlc_stage"] == "deployment":
                        st.session_state["deployment_artifact_approved"] = True
                        logger.info("Deployment artifact approved. Proceeding to next phase.")
                    else:
                        logger.error("Unknown SDLC stage. Cannot proceed.")
                        st.error("Unknown SDLC stage. Cannot proceed.")
                        st.session_state["user_stories_approved"] = False
                        st.session_state["user_stories_generated_flag"] = False
                        st.session_state["feedback_pending"] = False
                        st.session_state["needs_resume_after_feedback"] = False
                        st.session_state["planning_stage_running"] = False
                        return
                    
                    
                else:
                    # st.session_state["user_stories_generated_flag"] = final_state.get("user_stories") is not None
                    st.session_state["user_stories_approved"] = False
                    logger.info(f"Graph looped back or did not complete. Final feedback decision: {final_feedback_decision}")

                st.session_state["needs_resume_after_feedback"] = False
                st.session_state["planning_stage_running"] = False
                logger.info("Graph resumption stream processing completed. Graph completed flag: %s", st.session_state.get('user_stories_approved', False))

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
