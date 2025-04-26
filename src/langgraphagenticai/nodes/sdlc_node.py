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
            prompt_string = f"""Based on the following project details, generate a comprehensive list of detailed software requirements.
                                Ensure the requirements are clear, unambiguous, verifiable, and complete based on the provided description, goals, scope, and objectives.

                                Project Details:
                                {json.dumps(requirements_input, indent=2)}

                                Detailed Requirements:
                            """""
            # Construct a list of messages for the LLM
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
        """Generate user stories based on the requirements, incorporating feedback if available."""
        logger.info("Generating user stories")
        if not state.generated_requirements:
            state.user_stories = "No requirements generated yet."
            logger.warning("Cannot generate user stories without requirements.")
            return {"user_stories": state.user_stories}
        
        feedback = state.get_last_feedback_for_stage(SDLCStages.PLANNING)
        logger.info(f"Feedback for user stories: {feedback}")
        if feedback:
            prompt_string = f"""Based on the following software requirements AND feedback, generate a list of user stories.
                            The previous version was rejected for the following reason: "{feedback}"
                            Please make sure to address this feedback in your new user stories.
                            
                            Each user story should follow the format: 'As a [type of user], I want [some goal] so that [some reason/benefit].'
                            Ensure the user stories cover the key functionalities outlined in the requirements and are actionable from a development perspective.

                            Requirements:
                            {state.generated_requirements}
                            
                            Previous Feedback to Address:
                            {feedback}

                            User Stories:
                            """""
        else:

            try:
                if state.generated_requirements:
                    prompt_string =  f"""Based on the following software requirements, generate a list of user stories.
                                    Each user story should follow the format: 'As a [type of user], I want [some goal] so that [some reason/benefit].'
                                    Ensure the user stories cover the key functionalities outlined in the requirements and are actionable from a development perspective.

                                    Requirements:
                                    {state.generated_requirements}

                                    User Stories:
                                    """""
                    sys_prompt= f"""
                                    You are a Senior Software Analyst expert in Agile SDLC and user story creation. Your task is to generate detailed user stories based on the provided requirements.

                                    Project Name: {state.project_name or 'N/A'}

                                    Guidelines:

                                    One Requirement = One User Story: Create a distinct user story for each functional requirement identified.
                                    Unique Identifier: Assign each user story a unique ID: [PROJECT_CODE]-US-[XXX] (e.g., BN-US-001 for 'The Book Nook'). Use a short uppercase code for the project.
                                    Structure (for each story):
                                    Unique Identifier: [PROJECT_CODE]-US-XXX
                                    Title: Clear summary of the functionality.
                                    Description: As a [user role], I want [goal/feature] so that [reason/benefit].
                                    Acceptance Criteria: Bulleted list of testable conditions (- [Criterion]).
                                    Clarity: Use domain-specific terms. Ensure stories are specific, testable, achievable, and Agile-aligned. 
                                    {f'5. Incorporate Feedback: The previous version was rejected. Address the following feedback while refining the user stories: "{feedback}"' if feedback else ''} """ 
                    
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
    def process_feedback(self, state: State) -> dict:
        """Process user feedback by adding it to the state."""
        current_stage_value = "N/A"
        current_stage_obj = state.get('current_stage')

        # Determine the current stage
        if isinstance(current_stage_obj, SDLCStages):
            current_stage_value = current_stage_obj.value
        elif isinstance(current_stage_obj, str):
            current_stage_value = current_stage_obj
        else:
            logger.warning("Current stage is not an SDLCStages enum or a string. Using 'N/A'.")

        logger.info(f"Processing feedback for stage: {current_stage_value}")

        # Read feedback from the graph state
        feedback_data = state.get("feedback")  # Changed "feedback_input" to "feedback"
        logger.info(f"Feedback data received in process_feedback: {feedback_data}")

        # Process the feedback - store it in the state, associated with the current stage
        if feedback_data is not None:
            decision = feedback_data.get("approved")
            feedback_text = feedback_data.get("comments")

            if decision is False and feedback_text:
                # Use the actual current stage for feedback
                stage_for_feedback_value = current_stage_value  
                
                if isinstance(state, State) and hasattr(state, 'add_feedback'):
                    state.add_feedback(SDLCStages(stage_for_feedback_value), feedback_text)  # Convert back to enum
                elif isinstance(state, dict):
                    if 'feedback' not in state:
                        state['feedback'] = {}
                    if stage_for_feedback_value not in state['feedback']:
                        state['feedback'][stage_for_feedback_value] = []
                    state['feedback'][stage_for_feedback_value].append(feedback_text)
                else:
                    logger.error("State object does not have 'add_feedback' method and is not a dict.")

                logger.info(f"Feedback added to graph state for stage: {stage_for_feedback_value} - Rejected.")

        return state

    @log_entry_exit
    def feedbackRoute(self, state: State) -> str:
        """Route feedback based on SDLCState feedback format (Dict[str, List[str]]).
        Accept if feedback for current stage is empty or not present, reject if there are comments.
        """
        # Get current stage as string
        current_stage = state.get('current_stage')
        if hasattr(current_stage, 'value'):
            current_stage = current_stage.value
        elif isinstance(current_stage, str):
            pass
        else:
            current_stage = str(current_stage)

        feedback_dict = state.get('feedback', {})
        feedback_list = feedback_dict.get(current_stage, [])

        logger.info(f"feedbackRoute: current_stage={current_stage}, feedback_dict={feedback_dict}")

        if not feedback_list:
            logger.info(f"Feedback for stage '{current_stage}' is empty or not present. Accepting.")
            return "accept"
        else:
            logger.info(f"Feedback for stage '{current_stage}' present: {feedback_list}. Rejecting.")
            return "reject"