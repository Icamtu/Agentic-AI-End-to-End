from langgraph.graph import StateGraph, START, END
from src.langgraphagenticai.state.state import SDLCStages, SDLCState as State
from langchain_core.messages import SystemMessage, HumanMessage
import streamlit as st
import json
from datetime import datetime
from typing import List
from src.langgraphagenticai.logging.logging_utils import logger, log_entry_exit
from src.langgraphagenticai.prompt_library import prompt
import json
from tenacity import retry, stop_after_attempt, wait_exponential
import functools
import time
import re


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
            # Prepare dynamic input
            requirements_input_json = json.dumps(requirements_input, indent=2)

            # Render prompt string with runtime data
            prompt_string = prompt.REQUIREMENTS_PROMPT_STRING.format(requirements_input=requirements_input_json)
            sys_prompt = prompt.REQUIREMENTS_sys_prompt
                                
              
            
            messages = [
                SystemMessage(content=sys_prompt),
                HumanMessage(content=prompt_string)
            ]
           
            
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
        
        logger.info("Generating user stories")
        if not state.generated_requirements:
            state.user_stories = "No requirements generated yet."
            logger.warning("Cannot generate user stories without requirements.")
            return {"user_stories": state.user_stories}
        feedback = state.get_last_feedback_for_stage(SDLCStages.PLANNING)
        logger.info(f"Feedback for user stories: {feedback}")
        if feedback:
            prompt_string = prompt.USER_STORIES_FEEDBACK_PROMPT_STRING.format(
                                generated_requirements=state.generated_requirements,
                                # project_name=state.project_name or 'N/A',
                                feedback=feedback
            )
            
            sys_prompt = prompt.USER_STORIES_FEEDBACK_SYS_PROMPT.format(
                                generated_requirements=state.generated_requirements,
                                project_name=state.project_name or 'N/A',
                                feedback=feedback
                            )
            
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
                    prompt_string = prompt.USER_STORIES_NO_FEEDBACK_PROMPT_STRING.format(
                                generated_requirements=state.generated_requirements,
                                project_name=state.project_name or 'N/A'
                            )
                            
                    sys_prompt = prompt.USER_STORIES_NO_FEEDBACK_SYS_PROMPT.format(
                                                generated_requirements=state.generated_requirements,
                                                project_name=state.project_name or 'N/A'
                                            )
                    
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
    def _sanitize_json(self, input_str: str) -> dict | list:
        """Sanitize and validate JSON input, raising ValueError on failure."""
        try:
            # Remove control characters and stray newlines
            # This regex matches control characters (0x00-0x1F and 0x7F)
            cleaned = re.sub(r'[\x00-\x1F\x7F]', '', input_str).replace('\n', ' ').replace('\r', '').strip()
            data = json.loads(cleaned)
            # Validate basic structure
            if isinstance(data, list):
                for item in data:
                    if not all(key in item for key in ['id', 'title', 'user_story', 'acceptance_criteria']):
                        raise ValueError("Invalid user story structure: missing required fields")
            elif not all(key in data for key in ['id', 'title', 'user_story', 'acceptance_criteria']):
                raise ValueError("Invalid user story structure: missing required fields")
            return data
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON: {str(e)}")
        except Exception as e:
            raise ValueError(f"JSON validation error: {str(e)}")
    @log_entry_exit
    def _is_json(self, input_str: str) -> bool:
        """Check if input is valid JSON."""
        try:
            json.loads(input_str)
            return True
        except json.JSONDecodeError:
            return False

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=4, max=10))
    def _generate_tdd(self, sys_prompt: str, prompt_string: str) -> str:
        """Generate TDD with retry logic."""
        try:
            messages = [
                SystemMessage(content=sys_prompt),
                HumanMessage(content=prompt_string)
            ]
            response = self.llm.invoke(messages)
            return response.content if hasattr(response, 'content') else str(response)
        except Exception as e:
            logger.error(f"LLM invocation failed: {str(e)}")
            raise
    @log_entry_exit
    def design_documents(self, state: State) -> dict[str, str]:
        """Generate design documents based on user stories with robust validation."""
        state.feedback_decision = None
        logger.info("Generating design documents")

        # Handle empty or missing user stories
        if not state.user_stories or not state.user_stories.strip():
            state.design_documents = "No user stories provided for design document generation."
            logger.warning("Cannot generate design documents without user stories.")
            return {"design_documents": state.design_documents}

        # Validate and sanitize user stories
        sanitized_stories = state.user_stories
        if self._is_json(state.user_stories):
            try:
                sanitized_stories = json.dumps(self._sanitize_json(state.user_stories))
                logger.info("Sanitized JSON user stories successfully")
            except ValueError as e:
                state.design_documents = f"Invalid user stories format: {str(e)}"
                logger.error(f"User stories validation failed: {str(e)}, Input: {state.user_stories[:100]}...")
                return {"design_documents": state.design_documents}
        else:
            # If not JSON, use the original string directly
            sanitized_stories = state.user_stories
            logger.info("User stories are not JSON, using raw string.")


        # Get feedback for design stage
        feedback = state.get_last_feedback_for_stage(SDLCStages.DESIGN)
        logger.info(f"Feedback for design documents: {feedback or 'None'}")

        try:
            # Prepare prompt based on feedback presence
            # Corrected prompt variable names as there are no feedback-specific design document prompts
            sys_prompt = prompt.DESIGN_DOCUMENTS_NO_FEEDBACK_SYS_PROMPT.format(
                user_stories=sanitized_stories,
                project_name=state.project_name or 'N/A'
            )
            prompt_string = prompt.DESIGN_DOCUMENTS_NO_FEEDBACK_PROMPT_STRING.format(
                user_stories=sanitized_stories,
                project_name=state.project_name or 'N/A'
            )

            # Generate TDD with retry
            state.design_documents = self._generate_tdd(sys_prompt, prompt_string)
            logger.info("Design documents generated successfully")
            return {"design_documents": state.design_documents}

        except Exception as e:
            error_msg = f"Error generating design documents: {type(e).__name__} - {str(e)}"
            state.design_documents = error_msg
            logger.error(f"{error_msg}, Input: {sanitized_stories[:100]}...")
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
            prompt_string = prompt.DEVELOPMENT_ARTIFACT_PROMPT_STRING.format(
                design_documents=state.design_documents
            )
            messages = [
                SystemMessage(content=prompt.DEVELOPMENT_ARTIFACT_SYS_PROMPT.format(
                    project_name=state.project_name or 'N/A'
                )),
                HumanMessage(content=prompt_string)
            ]
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
            prompt_string = prompt.TESTING_ARTIFACT_PROMPT_STRING.format(
                user_stories=state.user_stories,
                development_artifact=state.development_artifact
            )
            messages = [
                SystemMessage(content=prompt.TESTING_ARTIFACT_SYS_PROMPT.format(
                    project_name=state.project_name or 'N/A'
                )),
                HumanMessage(content=prompt_string)
            ]
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
            prompt_string = prompt.DEPLOYMENT_ARTIFACT_PROMPT_STRING.format(state=state)
            messages = [SystemMessage(content=prompt.DEPLOYMENT_ARTIFACT_SYS_PROMPT), HumanMessage(content=prompt_string)]
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


