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
            prompt_string = f"Generate detailed requirements for the following project details:\n{json.dumps(requirements_input, indent=2)}"
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
                prompt_string = f"Generate user stories based on the following requirements:\n{state.generated_requirements}"
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