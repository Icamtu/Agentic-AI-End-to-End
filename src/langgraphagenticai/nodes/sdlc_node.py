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
            state.generated_requirements = self.llm(messages)
            return {"generated_requirements": state.generated_requirements}
        except Exception as e:
            logger.error(f"Error generating requirements: {e}")
            state.generated_requirements = f"Error generating requirements: {str(e)}"
            return {"generated_requirements": state.generated_requirements}

   
    @log_entry_exit
    def generate_user_stories(self, state: State) -> dict:
        """Generate user stories based on the requirements."""
        logger.info("Generating user stories")

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
                               You are a Senior Software Analyst with expertise in Agile Software Development Life Cycle (SDLC) and user story creation. 
                               Your task is to generate a separate and detailed user story for each individual requirement from the project details provided below.

                                Project Details
                                Project Name: {state.project_name}
                                Requirements:
                                {state.generated_requirements}

                                User Story Generation Guidelines
                                One Requirement = One User Story
                                Create one user story for each requirement provided.

                                Unique Identifier Format
                                Assign each user story a unique identifier using the following convention:

                                css
                                Copy
                                Edit
                                [PROJECT_CODE]-US-[XXX]
                                PROJECT_CODE: A short, uppercase abbreviation of the project name (e.g., “CRM” for Customer Relationship Management).

                                US: Stands for User Story.

                                XXX: A zero-padded sequential number starting from 001 (e.g., CRM-US-001, CRM-US-002, ...).

                                User Story Structure Each user story must include:

                                Title: A clear and concise summary of the functionality.

                                Description (follow this exact format):

                                css
                                Copy
                                Edit
                                As a [user role], I want [goal or feature] so that [reason or benefit].
                                Acceptance Criteria: A bulleted list of testable and verifiable conditions.

                                Language & Terminology

                                Use domain-specific terms to ensure clarity and accuracy.

                                Ensure each user story is specific, testable, achievable, and aligned with Agile principles.

                                {f"5. Incorporate Feedback\n - Additionally, consider the following while refining the user stories: {state.get_last_feedback_for_stage(SDLCStages.PLANNING)}" if state.get_last_feedback_for_stage(SDLCStages.PLANNING) else ""}
                                Expected Output Format (for Each User Story)
                                less
                                Copy
                                Edit
                                Unique Identifier: [PROJECT_CODE]-US-XXX

                                Title: [User Story Title]

                                Description:
                                As a [user role], I want [feature] so that [benefit].

                                Acceptance Criteria:
                                - [Criterion 1]
                                - [Criterion 2]
                                - [Criterion 3]
                                - [Criterion 4]
                                """
                messages = [
                    SystemMessage(content="You are an expert at creating user stories for software development projects. Each user story should follow the format: 'As a [type of user], I want [some goal] so that [some reason/benefit].' Ensure the user stories are clear, concise, and cover the key functionalities outlined in the requirements."),
                    HumanMessage(content=prompt_string)
                ]
                state.user_stories = self.llm(messages)
                return {"user_stories": state.user_stories}
            else:
                state.user_stories = "No requirements generated yet."
                return {"user_stories": state.user_stories}
        except Exception as e:
            logger.error(f"Error generating user stories: {e}")
            state.user_stories = f"Error generating user stories: {str(e)}"
            return {"user_stories": state.user_stories}
    
    @log_entry_exit
    def process_feedback(self, state: State) -> str:  # Return "accept" or "reject"
        """Process user feedback and return a decision for graph routing."""
        logger.info(f"Processing feedback for stage: {state.current_stage.value}")

        feedback_data = st.session_state.get("feedback", {})
        logger.info(f"Feedback data: {feedback_data}")
        if feedback_data is None:
            logger.info("No feedback found in session state. Assuming acceptance.")
            return "accept"
        decision = feedback_data.get("approved")
        feedback_text = feedback_data.get("comments")

        if decision == True:
            if "feedback" in st.session_state:
                del st.session_state["feedback"]
                logger.info("Feedback cleared from session state - Approved.")
            return "accept"
        elif decision == False and feedback_text:
            stage_for_feedback = state.current_stage
            state.add_feedback(stage_for_feedback, feedback_text)
            logger.info(f"Feedback added for stage: {stage_for_feedback.value} - Rejected.")
            if "feedback" in st.session_state:
                del st.session_state["feedback"]
                logger.info("Feedback cleared from session state - Rejection processed.")
            return "reject"
        else:
            return "accept"  
    
   


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