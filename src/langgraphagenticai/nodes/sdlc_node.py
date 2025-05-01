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
        state.feedback = st.session_state.get("feedback")
        state.feedback_decision = st.session_state.get("feedback_decision")
        state.current_stage = st.session_state.get("current_stage")
        state.generated_requirements = st.session_state.get("generated_requirements")
        state.user_stories = st.session_state.get("user_stories")
        
        return {"user_input": "captured"}

    @log_entry_exit
    def generate_requirements(self, state: State) -> dict:
        """DUMMY: Generate requirements based on user input (original code commented for testing)."""
        # logger.info(f"Generating requirements with state: {state}")
        # try:
        #     requirements_input = {
        #         "project_name": state.project_name if state.project_name is not None else "No project name provided",
        #         "project_description": state.project_description if state.project_description is not None else "No project description provided",
        #         "project_goals": state.project_goals if state.project_goals is not None else "No project goals provided",
        #         "project_scope": state.project_scope if state.project_scope is not None else "No project scope provided",
        #         "project_objectives": state.project_objectives if state.project_objectives is not None else "No project objectives provided",
        #     }
        #     prompt_string = f"""Based on the following project details, generate a comprehensive list of detailed software requirements.\n                                Ensure the requirements are clear, unambiguous, verifiable, and complete based on the provided description, goals, scope, and objectives.\n\n                                Project Details:\n                                {json.dumps(requirements_input, indent=2)}\n\n                                Detailed Requirements:\n                            """"
        #     messages = [SystemMessage(content="You are an expert project requirements generator."),HumanMessage(content=prompt_string)]
        #     response = self.llm.invoke(messages)
        #     state.generated_requirements = response.content if hasattr(response, 'content') else str(response)  
        #     return {"generated_requirements": state.generated_requirements}
        # except Exception as e:
        #     logger.error(f"Error generating requirements: {e}")
        #     state.generated_requirements = f"Error generating requirements: {str(e)}"
        #     return {"generated_requirements": state.generated_requirements}
        state.generated_requirements = "DUMMY REQUIREMENTS: This is a dummy requirements list for testing."
        return {"generated_requirements": state.generated_requirements}

    @log_entry_exit
    def generate_user_stories(self, state: State) -> dict:
        """DUMMY: Generate user stories based on the requirements (original code commented for testing)."""
        # logger.info("Generating user stories")
        # if not state.generated_requirements:
        #     state.user_stories = "No requirements generated yet."
        #     logger.warning("Cannot generate user stories without requirements.")
        #     return {"user_stories": state.user_stories}
        # feedback = state.get_last_feedback_for_stage(SDLCStages.PLANNING)
        # logger.info(f"Feedback for user stories: {feedback}")
        # if feedback:
        #     prompt_string = f"""Based on the following software requirements AND feedback, generate a list of user stories.\n                            The previous version was rejected for the following reason: \"{feedback}\"\n                            Please make sure to address this feedback in your new user stories.\n                            \n                            Each user story should follow the format: 'As a [type of user], I want [some goal] so that [some reason/benefit].'\n                            Ensure the user stories cover the key functionalities outlined in the requirements and are actionable from a development perspective.\n\n                            Requirements:\n                            {state.generated_requirements}\n                            \n                            Previous Feedback to Address:\n                            {feedback}\n\n                            User Stories:\n                            """"
        # else:
        #     try:
        #         if state.generated_requirements:
        #             prompt_string =  f"""Based on the following software requirements, generate a list of user stories.\n                                    Each user story should follow the format: 'As a [type of user], I want [some goal] so that [some reason/benefit].'\n                                    Ensure the user stories cover the key functionalities outlined in the requirements and are actionable from a development perspective.\n\n                                    Requirements:\n                                    {state.generated_requirements}\n\n                                    User Stories:\n                                    """"
        #             sys_prompt= f"""\n                                    You are a Senior Software Analyst expert in Agile SDLC and user story creation. Your task is to generate detailed user stories based on the provided requirements.\n\n                                    Project Name: {state.project_name or 'N/A'}\n\n                                    Guidelines:\n\n                                    One Requirement = One User Story: Create a distinct user story for each functional requirement identified.\n                                    Unique Identifier: Assign each user story a unique ID: [PROJECT_CODE]-US-[XXX] (e.g., BN-US-001 for 'The Book Nook'). Use a short uppercase code for the project.\n                                    Structure (for each story):\n                                    Unique Identifier: [PROJECT_CODE]-US-XXX\n                                    Title: Clear summary of the functionality.\n                                    Description: As a [user role], I want [goal/feature] so that [reason/benefit].\n                                    Acceptance Criteria: Bulleted list of testable conditions (- [Criterion]).\n                                    Clarity: Use domain-specific terms. Ensure stories are specific, testable, achievable, and Agile-aligned. \n                                    {f'5. Incorporate Feedback: The previous version was rejected. Address the following feedback while refining the user stories: "{feedback}"' if feedback else ''} """ 
        #             messages = [
        #                 SystemMessage(content=sys_prompt),
        #                 HumanMessage(content=prompt_string)
        #             ]
        #             response = self.llm.invoke(messages)
        #             state.user_stories = response.content if hasattr(response, 'content') else str(response)
        #             return {"user_stories": state.user_stories}
        #         else:
        #             state.user_stories = "No requirements generated yet."
        #             return {"user_stories": state.user_stories}
        #     except Exception as e:
        #         logger.error(f"Error generating user stories: {e}")
        #         state.user_stories = f"Error generating user stories: {str(e)}"
        #         return {"user_stories": state.user_stories}
        state.user_stories = "DUMMY USER STORIES: This is a dummy user stories list for testing."
        return {"user_stories": state.user_stories}
    
    @log_entry_exit
    def process_feedback(self, state: State) -> dict:
        """
        Process user feedback passed via state and update state with decision.
        Only { "current_stage": ["accept"] } ends the process.
        """
        logger.info(f"--- Entering process_feedback ---")
        logger.info(f"Input state: {state.to_dict() if hasattr(state, 'to_dict') else state}")
        logger.info(f"State type: {type(state)}")
        #logger.info(f"State feedback in st: {st.session_state['feedback']}")  # Removed - no longer needed

        # Access feedback directly from state
        #state.feedback = st.session_state["feedback"] # Removed - no longer needed

        current_stage = state.get("current_stage") if isinstance(state, dict) else state.current_stage
        raw_feedback = state.get("feedback", {}) if isinstance(state, dict) else getattr(state, "feedback", {})

        if isinstance(current_stage, str):
            current_stage_value = current_stage
        else:
            current_stage_value = current_stage.value if hasattr(current_stage, "value") else str(current_stage)

        logger.info(f"Processing feedback for stage: {current_stage_value}")
        logger.info(f"Raw feedback data received in state: {raw_feedback}")

        # Only accept if feedback is {current_stage: ["accept"]}
        logger.info(f"Checking acceptance: current_stage_value={current_stage_value}, raw_feedback={raw_feedback}")
        if (
            isinstance(raw_feedback, dict)
            and current_stage_value in raw_feedback
            and isinstance(raw_feedback[current_stage_value], list)
            and raw_feedback[current_stage_value]
            and raw_feedback[current_stage_value][-1].strip().lower() == "accept"
        ):
            logger.info(f"Feedback for stage '{current_stage_value}' is ACCEPT. Ending flow.")
            if isinstance(state, dict):
                state["feedback_decision"] = "accept"
            else:
                state.feedback_decision = "accept"
        else:
            logger.info(f"Feedback for stage '{current_stage_value}' is not accept. Looping back. Feedback is: {raw_feedback}")
            if isinstance(state, dict):
                state["feedback_decision"] = "reject"
            else:
                state.feedback_decision = "reject"

        return_value = {
            "feedback_decision": state["feedback_decision"] if isinstance(state, dict) else state.feedback_decision,
            "feedback": raw_feedback
        }
        logger.info(f"Returning from process_feedback: {return_value}")
        logger.info(f"--- Exiting process_feedback ---")
        return return_value

    @log_entry_exit
    def feedback_route(self, state: State) -> str:
        """Routes based on the feedback decision stored in the state."""
        logger.info(f"--- Entering feedback_route ---")
        logger.info(f"Routing feedback. Current state includes feedback_decision: {hasattr(state, 'feedback_decision')}")
        
        logger.info(f"Full state content received by feedback_route: {state.to_dict() if isinstance(state, State) else state}")

        if not isinstance(state, State):
            logger.error(f"Incorrect state type passed to feedback_route: {type(state)}. Defaulting to reject.")
            logger.info(f"--- Exiting feedback_route (routing: reject due to type error) ---")
            
            return "reject"

    
        feedback_decision = state.feedback_decision
        logger.info(f"Feedback decision read from state object: {feedback_decision}")

        if feedback_decision == "accept":
            logger.info("Feedback accepted. Routing to END.")
            logger.info(f"--- Exiting feedback_route (routing: accept) ---")
            return "accept"
        else:
            
            logger.info(f"Feedback decision is '{feedback_decision}'. Routing back for revision.")
            logger.info(f"--- Exiting feedback_route (routing: reject) ---")
            return "reject"

    def update_checkpoint_state(self, checkpoint_state, feedback_data):
        if checkpoint_state is not None:
            if isinstance(checkpoint_state, dict):
                if "channel_values" in checkpoint_state and isinstance(checkpoint_state["channel_values"], dict):
                    checkpoint_state["channel_values"]["feedback"] = feedback_data
                checkpoint_state["feedback"] = feedback_data  # <-- add this line
            else:
                setattr(checkpoint_state, "feedback", feedback_data)
        else:
            checkpoint_state = {"feedback": feedback_data}
