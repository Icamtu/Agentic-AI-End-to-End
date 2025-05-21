from langgraph.graph import StateGraph, START, END
from src.langgraphagenticai.state.state import SDLCStages, SDLCState as State
from langchain_core.messages import SystemMessage, HumanMessage
import streamlit as st
import json
from datetime import datetime
from typing import List
from src.langgraphagenticai.logging.logging_utils import logger, log_entry_exit


import functools
import time


class SdlcNode:
    def __init__(self, model):
        """Initialize the BlogGenerationNode with an LLM."""
        self.llm = model

    @log_entry_exit
    def user_input(self, state: State) -> dict:
        """Handle user input, distinguishing between initial requirements and feedback."""
        logger.info(f"Executing user_input with state: {state}")
        if state.get_last_feedback_for_stage(SDLCStages.PLANNING):
            state.user_stories = None

        state.project_name = st.session_state.get("project_name")
        state.project_description = st.session_state.get("project_description")
        state.project_goals = st.session_state.get("project_goals")
        state.project_scope = st.session_state.get("project_scope")
        state.project_objectives = st.session_state.get("project_objectives")
        state.feedback = st.session_state.get("feedback", {})
        state.feedback_decision = st.session_state.get("feedback_decision")
        state.current_stage = st.session_state.get("current_stage", SDLCStages.PLANNING)
        state.generated_requirements = st.session_state.get("generated_requirements")
        state.user_stories = st.session_state.get("user_stories")
        
        return {"user_input": "captured"}

    @log_entry_exit
    def generate_requirements(self, state: State) -> dict:
        """Generate requirements based on user input."""
        logger.info(f"Generating requirements with state: {state}")
        try:
            requirements_input = {
                "project_name": state.project_name if state.project_name is not None else "No project name provided",
                "project_description": state.project_description if state.project_description is not None else "No project description provided",
                "project_goals": state.project_goals if state.project_goals is not None else "No project goals provided",
                "project_scope": state.project_scope if state.project_scope is not None else "No project scope provided",
                "project_objectives": state.project_objectives if state.project_objectives is not None else "No project objectives provided",
            }
            prompt_string = f"""Based on the following project details, generate a comprehensive list of detailed software requirements.\n
                                Ensure the requirements are clear, unambiguous, verifiable, and complete based on the provided description, goals, scope, and objectives.\n\n
                                Project Details:\n
                                {json.dumps(requirements_input, indent=2)}\n\n
                                Detailed Requirements:\n
                            """
            messages = [SystemMessage(content="You are an expert project requirements generator."),HumanMessage(content=prompt_string)]
            response = self.llm.invoke(messages)
            state.generated_requirements = response.content if hasattr(response, 'content') else str(response)  
            return {"generated_requirements": state.generated_requirements}
        except Exception as e:
            logger.error(f"Error generating requirements: {e}")
            state.generated_requirements = f"Error generating requirements: {str(e)}"
            return {"generated_requirements": state.generated_requirements}

    @log_entry_exit
    def generate_user_stories(self, state: State) -> dict:
        """Generate user stories based on the requirements."""
        # state.user_stories = "DUMMY USER STORIES: This is a dummy user stories list for testing."
        # return {"user_stories": state.user_stories}
        logger.info("Generating user stories")
        if not state.generated_requirements:
            state.user_stories = "No requirements generated yet."
            logger.warning("Cannot generate user stories without requirements.")
            return {"user_stories": state.user_stories}
        feedback = state.get_last_feedback_for_stage(SDLCStages.PLANNING)
        logger.info(f"Feedback for user stories: {feedback}")
        if feedback:
            prompt_string = f"""Based on the following software requirements AND feedback, generate a list of user stories.\n                            The previous version was rejected for the following reason: \"{feedback}\"\n                            Please make sure to address this feedback in your new user stories.\n                            \n                            Each user story should follow the format: 'As a [type of user], I want [some goal] so that [some reason/benefit].'\n                            Ensure the user stories cover the key functionalities outlined in the requirements and are actionable from a development perspective.\n\n                            Requirements:\n                            {state.generated_requirements}\n                            \n                            Previous Feedback to Address:\n                            {feedback}\n\n                            User Stories:\n                            """
            sys_prompt = f"""\n                                    You are a Senior Software Analyst expert in Agile SDLC and user story creation. Your task is to generate detailed user stories based on the provided requirements.\n\n                                    Project Name: {state.project_name or 'N/A'}\n\n                                    Guidelines:\n\n                                    One Requirement = One User Story: Create a distinct user story for each functional requirement identified.\n                                    Unique Identifier: Assign each user story a unique ID: [PROJECT_CODE]-US-[XXX] (e.g., BN-US-001 for 'The Book Nook'). Use a short uppercase code for the project.\n                                    Structure (for each story):\n                                    Unique Identifier: [PROJECT_CODE]-US-XXX\n                                    Title: Clear summary of the functionality.\n                                    Description: As a [user role], I want [goal/feature] so that [reason/benefit].\n                                    Acceptance Criteria: Bulleted list of testable conditions (- [Criterion]).\n                                    Clarity: Use domain-specific terms. Ensure stories are specific, testable, achievable, and Agile-aligned. \n                                    5. Incorporate Feedback: The previous version was rejected. Address the following feedback while refining the user stories: \"{feedback}\"""" 
            messages = [
                SystemMessage(content=sys_prompt),
                HumanMessage(content=prompt_string)
            ]
            response = self.llm.invoke(messages)
            state.user_stories = response.content if hasattr(response, 'content') else str(response)
            return {"user_stories": state.user_stories}
        else:
            try:
                if state.generated_requirements:
                    prompt_string = f"""Based on the following software requirements, generate a list of user stories.\n                                    Each user story should follow the format: 'As a [type of user], I want [some goal] so that [some reason/benefit].'\n                                    Ensure the user stories cover the key functionalities outlined in the requirements and are actionable from a development perspective.\n\n                                    Requirements:\n                                    {state.generated_requirements}\n\n                                    User Stories:\n                                    """
                    sys_prompt = f"""\n                                    You are a Senior Software Analyst expert in Agile SDLC and user story creation. Your task is to generate detailed user stories based on the provided requirements.\n\n                                    Project Name: {state.project_name or 'N/A'}\n\n                                    Guidelines:\n\n                                    One Requirement = One User Story: Create a distinct user story for each functional requirement identified.\n                                    Unique Identifier: Assign each user story a unique ID: [PROJECT_CODE]-US-[XXX] (e.g., BN-US-001 for 'The Book Nook'). Use a short uppercase code for the project.\n                                    Structure (for each story):\n                                    Unique Identifier: [PROJECT_CODE]-US-XXX\n                                    Title: Clear summary of the functionality.\n                                    Description: As a [user role], I want [goal/feature] so that [reason/benefit].\n                                    Acceptance Criteria: Bulleted list of testable conditions (- [Criterion]).\n                                    Clarity: Use domain-specific terms. Ensure stories are specific, testable, achievable, and Agile-aligned."""
                    messages = [
                        SystemMessage(content=sys_prompt),
                        HumanMessage(content=prompt_string)
                    ]
                    response = self.llm.invoke(messages)
                    state.user_stories = response.content if hasattr(response, 'content') else str(response)
                    return {"user_stories": state.user_stories}
                else:
                    state.user_stories = "No requirements generated yet."
                    return {"user_stories": state.user_stories}
            except Exception as e:
                logger.error(f"Error generating user stories: {e}")
                state.user_stories = f"Error generating user stories: {str(e)}"
                return {"user_stories": state.user_stories}
    
    @log_entry_exit
    def design_documents(self, state: State) -> dict:
        """Generate design documents based on user stories."""
        # state.design_documents = "DUMMY DESIGN DOCUMENT: This is a dummy design document for testing."
        # return {"design_documents": state.design_documents}
        state.feedback_decision = None
        logger.info("Generating design documents")
        if not state.user_stories:
            state.design_documents = "No user stories generated yet."
            logger.warning("Cannot generate design documents without user stories.")
            return {"design_documents": state.design_documents}
        try:
            prompt_string = f"""Based on the following user stories, generate a detailed design document.\n                            The design document should include:\n                            1. Overview of the system architecture\n                            2. Detailed component designs\n                            3. Data flow diagrams\n                            4. Database schema\n                            5. API specifications\n                            \n                            User Stories:\n                            {state.user_stories}\n\n                            Design Document:\n                            """
            messages = [SystemMessage(content="You are an expert software designer."), HumanMessage(content=prompt_string)]
            response = self.llm.invoke(messages)
            state.design_documents = response.content if hasattr(response, 'content') else str(response)
            return {"design_documents": state.design_documents}
        except Exception as e:
            logger.error(f"Error generating design documents: {e}")
            state.design_documents = f"Error generating design documents: {str(e)}"
            return {"design_documents": state.design_documents}
    
    @log_entry_exit
    def development_artifact(self, state: State) -> dict:
        """Generate development artifacts based on design documents."""
        # state.development_artifact = "DUMMY DEVELOPMENT ARTIFACT: This is a dummy development artifact for testing."
        # return {"development_artifact": state.development_artifact}
        logger.info("Generating development artifacts")
        if not state.design_documents:
            state.development_artifact = "No design documents generated yet."
            logger.warning("Cannot generate development artifacts without design documents.")
            return {"development_artifact": state.development_artifact}
        try:
            prompt_string = f"""Based on the following design documents, generate the development artifacts.\n                            The development artifacts should include:\n                            1. Source code\n                            2. Build scripts\n                            3. Configuration files\n                            4. Deployment instructions\n                            \n                            Design Documents:\n                            {state.design_documents}\n\n                            Development Artifacts:\n                            """
            messages = [SystemMessage(content="You are an expert software developer."), HumanMessage(content=prompt_string)]
            response = self.llm.invoke(messages)
            state.development_artifact = response.content if hasattr(response, 'content') else str(response)
            return {"development_artifact": state.development_artifact}
        except Exception as e:
            logger.error(f"Error generating development artifacts: {e}")
            state.development_artifact = f"Error generating development artifacts: {str(e)}"
            return {"development_artifact": state.development_artifact}
    
    @log_entry_exit
    def testing_artifact(self, state: State) -> dict:
        """Generate testing artifacts based on development artifacts."""
        # state.testing_artifact = "DUMMY TESTING ARTIFACT: This is a dummy testing artifact for testing."
        # return {"testing_artifact": state.testing_artifact}
        logger.info("Generating testing artifacts")
        if not state.development_artifact:
            state.testing_artifact = "No development artifacts generated yet."
            logger.warning("Cannot generate testing artifacts without development artifacts.")
            return {"testing_artifact": state.testing_artifact}
        try:
            prompt_string = f"""Based on the following development artifacts, generate the testing artifacts.\n                            The testing artifacts should include:\n                            1. Test cases\n                            2. Test scripts\n                            3. Test data\n                            4. Test plans\n                            \n                            Development Artifacts:\n                            {state.development_artifact}\n\n                            Testing Artifacts:\n                            """
            messages = [SystemMessage(content="You are an expert software tester."), HumanMessage(content=prompt_string)]
            response = self.llm.invoke(messages)
            state.testing_artifact = response.content if hasattr(response, 'content') else str(response)
            return {"testing_artifact": state.testing_artifact}
        except Exception as e:
            logger.error(f"Error generating testing artifacts: {e}")
            state.testing_artifact = f"Error generating testing artifacts: {str(e)}"
            return {"testing_artifact": state.testing_artifact}
    
    @log_entry_exit
    def deployment_artifact(self, state: State) -> dict:
        """Generate deployment artifacts based on testing artifacts."""
        # state.deployment_artifact = "DUMMY DEPLOYMENT ARTIFACT: This is a dummy deployment artifact for testing."
        # return {"deployment_artifact": state.deployment_artifact}
        logger.info("Generating deployment artifacts")
        if not state.testing_artifact:
            state.deployment_artifact = "No testing artifacts generated yet."
            logger.warning("Cannot generate deployment artifacts without testing artifacts.")
            return {"deployment_artifact": state.deployment_artifact}
        try:
            prompt_string = f"""Based on the following testing artifacts, generate the deployment artifacts.\n
                            The deployment artifacts should include:\n
                            1. Deployment scripts\n
                            2. Configuration files\n
                            3. User manuals\n
                            \n
                            Testing Artifacts:\n
                            {state.testing_artifact}\n\n
                            Deployment Artifacts:\n
                            """
            messages = [
                SystemMessage(content="You are an expert software deployer."),
                HumanMessage(content=prompt_string)
            ]
            response = self.llm.invoke(messages)
            state.deployment_artifact = response.content if hasattr(response, 'content') else str(response)
            return {"deployment_artifact": state.deployment_artifact}
        except Exception as e:
            logger.error(f"Error generating deployment artifacts: {e}")
            state.deployment_artifact = f"Error generating deployment artifacts: {str(e)}"
            return {"deployment_artifact": state.deployment_artifact}
            
    @log_entry_exit
    def process_feedback(self, state: State) -> dict:
        """
        Process user feedback and update state with decision.
        Only { "current_stage": ["accept"] } ends the process.
        """
        
        # logger.info(f"Input state: {state.to_dict()}")
        logger.info(f"Feedback: {state.feedback}")

        current_stage = state.current_stage
        feedback_for_stage = state.get_last_feedback_for_stage(current_stage)

        if feedback_for_stage is None:
            logger.warning(f"No feedback found for stage {current_stage}. Available feedback: {state.feedback}")

        state.add_feedback(current_stage, str(feedback_for_stage))

        logger.info(f"Processing feedback for stage: {current_stage}")
        logger.info(f"Feedback received: {feedback_for_stage}")

        if feedback_for_stage and feedback_for_stage.strip().lower() == "accept":
            logger.info(f"Feedback for stage '{current_stage}' is ACCEPT. Ending flow.")
            state.feedback_decision = "accept"
        else:
            logger.info(f"Feedback for stage '{current_stage}' is not accept. Looping back. Feedback is: {feedback_for_stage}")
            state.feedback_decision = "reject"
        logger.info(f"Feedback: {state.feedback}")
       
        return {"feedback_decision": state.feedback_decision}   

    @log_entry_exit
    def feedback_route(self, state: State) -> str:
        """Routes based on the feedback decision stored in the state."""
        logger.info(f"Entering feedback_route with decision: {state.feedback_decision}")

        if not isinstance(state, State):
            logger.error(f"Invalid state type: {type(state)}. Routing to reject.")
            return "reject"

        if state.feedback_decision == "accept":
            logger.info("Feedback accepted. Routing to next stage.")
            next_stage = state.get_next_stage()
            if next_stage:
                state.update_stage(next_stage)
                logger.info(f"Updated state to next stage: {next_stage}")
            else:
                logger.info("No next stage available. Ending process.")
                
            state.clear_feedback_decision()
            st.session_state["feedback_decision"] = None
            logger.info(f"Feedback: {state.feedback}")
            logger.info(f"Feedback decision: {state.feedback_decision}")
            return "accept"
        else:
            logger.info("Feedback rejected. Routing back for revision.")
            state.clear_feedback_decision()
            st.session_state["feedback_decision"] = None
            return "reject"


