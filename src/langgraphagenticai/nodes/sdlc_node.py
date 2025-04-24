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
    def process_feedback(self, state: State) -> dict: # Return a dictionary to update state
        """Process user feedback from session state and update state with decision."""
        # Ensure current_stage is valid before accessing .value
        current_stage_value = "N/A"
        if isinstance(state.get('current_stage'), SDLCStages):
             current_stage_value = state['current_stage'].value
        elif isinstance(state.get('current_stage'), str):
             current_stage_value = state['current_stage'] # Handle if it's already a string

        logger.info(f"Processing feedback for stage: {current_stage_value}")

        feedback_data = st.session_state.get("feedback") # Get the whole dict or None
        logger.info(f"Feedback data from session state: {feedback_data}")

        decision_result = "accept" # Default to accept

        # --- Clear feedback from session state AFTER reading ---
        if "feedback" in st.session_state:
            try:
                del st.session_state["feedback"]
                logger.info("Feedback cleared from session state.")
            except KeyError:
                logger.warning("Attempted to delete 'feedback' from session state, but it was already gone.")

        # --- Process the feedback data ---
        if feedback_data is None:
            logger.info("No feedback data found. Assuming acceptance.")
            decision_result = "accept"
        else:
            decision = feedback_data.get("approved")
            feedback_text = feedback_data.get("comments")
            logger.info(f"Decision from feedback: {decision}, Comments: {feedback_text}")

            if decision is True:
                logger.info("Feedback decision: Approved.")
                decision_result = "accept"
            elif decision is False and feedback_text:
                # Add feedback to the graph state
                stage_for_feedback = SDLCStages.PLANNING # Assuming feedback is for planning
                state.add_feedback(stage_for_feedback, feedback_text)
                logger.info(f"Feedback added to graph state for stage: {stage_for_feedback.value} - Rejected.")
                decision_result = "reject"
            else:
                # Handle cases like Reject without comments, or unexpected data
                logger.warning("Feedback decision was 'Reject' but no comments provided, or data invalid. Defaulting to accept.")
                decision_result = "accept"

        # Return the decision within the state update dictionary
        return {"feedback_decision": decision_result} 
    
   


        # if feedback_text and feedback_text.strip(): # Check if feedback exists and is not just whitespace
        #     logger.info(f"Feedback received: {feedback_text}")
        #     # Add feedback to the state associated with the current stage
        #     # The feedback is typically about the *output* of the previous stage,
        #     # but we associate it with the *current* stage where it's processed.
        #     # Or, one could argue it belongs to the stage *just completed*.
        #     # Let's associate it with the stage that produced the artifact being reviewed.
        #     # If this node is called *after* generating user stories (part of PLANNING),
        #     # then the feedback is about the planning artifacts.
        #     stage_for_feedback = SDLCStages.PLANNING # Assuming feedback after user stories review is about planning
        #     state.add_feedback(stage_for_feedback, feedback_text)
        #     logger.info(f"Feedback added for stage: {stage_for_feedback.value}")

        #     # Clear the feedback from session state after processing
        #     if "user_feedback" in st.session_state:
        #         del st.session_state["user_feedback"]
        #         logger.info("Feedback cleared from session state.")

            # You might want to store the raw feedback text temporarily or trigger a revision process
            # state.raw_feedback = feedback_text # Example of storing raw feedback if needed

        #     return {"feedback_processed": True, "status": "feedback_added"}
        # else:
        #     logger.info("No new user feedback found in session state.")
            # return {"feedback_processed": False, "status": "no_feedback"}

    # Add more nodes for Design, Development, Testing, Deployment etc. following a similar pattern
    # Each node would take the state, perform an action (potentially using LLM),
    # update the state with the generated artifact, and return a dict indicating the result.

    # Example placeholder for a Planning Review node (determines next step after planning)
    # @log_entry_exit
    # def user_story_review_router(self, state: State) -> dict:
    #     """Route to the appropriate review node based on the current stage."""
    #     logger.info(f"Routing user story review for stage: {state.current_stage.value}")
    
    #     st.session_state.feedback.comments
    #     feedback_text = st.session_state.get("feedback")
    #     if feedback_text and feedback_text.strip():
    #         logger.info(f"Feedback received: {feedback_text}")
    #         return self.generate_user_stories(state)
    #     else:
    #         logger.info("No new user feedback found in session state.")
    #         return {"feedback_processed": False, "status": "no_feedback"}