from langgraph.graph import StateGraph, START, END
from src.langgraphagenticai.state.state import SDLCStages, SDLCState as State
from langchain_core.messages import SystemMessage, HumanMessage
import streamlit as st
import json
from datetime import datetime
from typing import List
from src.langgraphagenticai.logging.logging_utils import logger, log_entry_exit
from src.langgraphagenticai.prompt_library import prompt 
from typing import Dict, Any
from tenacity import retry, stop_after_attempt, wait_exponential
import functools
import time
import re


class SdlcNode:
    def __init__(self, model):
        """Initialize the SdlcNode with an LLM."""
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
            requirements_input_json = json.dumps(requirements_input, indent=2)

            prompt_string = prompt.REQUIREMENTS_PROMPT_STRING.format(requirements_input=requirements_input_json)
            # Assuming REQUIREMENTS_sys_prompt does not need .format() or is formatted elsewhere if needed
            sys_prompt_content = prompt.REQUIREMENTS_sys_prompt 
            
            messages = [
                SystemMessage(content=sys_prompt_content),
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

        formatted_requirements = str(state.generated_requirements).replace('{', '{{').replace('}', '}}')

        feedback = state.get_last_feedback_for_stage(SDLCStages.PLANNING)
        logger.info(f"Feedback for user stories: {feedback}")

        project_name_val = state.project_name or 'N/A'
        project_name_formatted = str(project_name_val).replace('{', '{{').replace('}', '}}')


        if feedback:
            formatted_feedback = str(feedback).replace('{', '{{').replace('}', '}}')
            try:
                prompt_string = prompt.USER_STORIES_FEEDBACK_PROMPT_STRING.format(
                                    generated_requirements=formatted_requirements,
                                    feedback=formatted_feedback
                )
                sys_prompt_content = prompt.USER_STORIES_FEEDBACK_SYS_PROMPT.format(
                                    generated_requirements=formatted_requirements,
                                    project_name=project_name_formatted,
                                    feedback=formatted_feedback
                                )
            except KeyError as e:
                logger.error(f"KeyError during formatting USER_STORIES_FEEDBACK prompts: {e}")
                logger.error(f"Available keys: generated_requirements, project_name, feedback")
                state.user_stories = f"Error formatting user story prompt: {e}"
                return {"user_stories": state.user_stories}
        else:
            try:
                prompt_string = prompt.USER_STORIES_NO_FEEDBACK_PROMPT_STRING.format(
                                    generated_requirements=formatted_requirements,
                                    project_name=project_name_formatted
                                )
                sys_prompt_content = prompt.USER_STORIES_NO_FEEDBACK_SYS_PROMPT.format(
                                    generated_requirements=formatted_requirements,
                                    project_name=project_name_formatted
                                )
            except KeyError as e:
                logger.error(f"KeyError during formatting USER_STORIES_NO_FEEDBACK prompts: {e}")
                logger.error(f"Available keys: generated_requirements, project_name")
                state.user_stories = f"Error formatting user story prompt: {e}"
                return {"user_stories": state.user_stories}
        
        try:
            messages = [
                SystemMessage(content=sys_prompt_content),
                HumanMessage(content=prompt_string)
            ]
            response = self.llm.invoke(messages)
            state.user_stories = response.content if hasattr(response, 'content') else str(response)
            st.session_state["user_stories"] = state.user_stories # Update session state
            logger.info(f"--- RAW state.user_stories after generation ---")
            logger.info(state.user_stories)
            logger.info(f"--- END RAW state.user_stories ---")

            return {"user_stories": state.user_stories}
        except Exception as e:
            logger.error(f"Error generating user stories: {e}")
            state.user_stories = f"Error generating user stories: {str(e)}"
            return {"user_stories": state.user_stories}

    @log_entry_exit
    def design_documents(self, state: State) -> dict[str, str]:
        """Generate design documents based on user stories with robust validation."""
        state.feedback_decision = None
        logger.info("Generating design documents")

        if not state.user_stories or not str(state.user_stories).strip():
            state.design_documents = "No user stories provided for design document generation."
            logger.warning("Cannot generate design documents without user stories.")
            return {"design_documents": state.design_documents}

        
        user_stories_for_prompt = str(state.user_stories).replace('{', '{{').replace('}', '}}')
        
        project_name_val = state.project_name or 'N/A'
        project_name_for_prompt = str(project_name_val).replace('{', '{{').replace('}', '}}')

        logger.info(f"--- User Stories for TDD Prompt (escaped) ---")
        logger.info(user_stories_for_prompt[:1000] + "..." if len(user_stories_for_prompt) > 1000 else user_stories_for_prompt) # Log a snippet
        logger.info(f"--- END User Stories for TDD Prompt ---")


       
        feedback = state.get_last_feedback_for_stage(SDLCStages.DESIGN)
        logger.info(f"Feedback for design documents: {feedback or 'None'}")
        if feedback:
            formatted_feedback = str(feedback).replace('{', '{{').replace('}', '}}')
            logger.info(f"Formatted feedback for design documents: {formatted_feedback[:200]}...")
            try:
                prompt_string_content = prompt.DESIGN_DOCUMENTS_FEEDBACK_PROMPT_STRING.format(
                    user_stories=user_stories_for_prompt,
                    user_feedback=formatted_feedback,
                    project_name=project_name_for_prompt
                )
                sys_prompt_content = prompt.DESIGN_DOCUMENTS_FEEDBACK_SYS_PROMPT.format(
                    user_stories=user_stories_for_prompt,
                    feedback=formatted_feedback,
                    project_name=project_name_for_prompt
                )
                messages = [
                    SystemMessage(content=sys_prompt_content),
                    HumanMessage(content=prompt_string_content)
                ]
                response = self.llm.invoke(messages)
                state.design_documents = response.content if hasattr(response, 'content') else str(response)
                logger.info("Design documents generated successfully with feedback.")
                return {"design_documents": state.design_documents}
            except KeyError as ke:
                error_msg = f"KeyError during TDD prompt formatting with feedback: {str(ke)}. This means a placeholder in your DESIGN_DOCUMENTS_FEEDBACK prompts was not found in the .format() call."
                logger.error(error_msg)
                logger.error(f"User stories (snippet): {user_stories_for_prompt[:200]}")
                logger.error(f"Project name: {project_name_for_prompt}")
                state.design_documents = error_msg
                return {"design_documents": state.design_documents}
            except Exception as e:
                error_msg = f"Error generating design documents with feedback: {type(e).__name__} - {str(e)}"
                state.design_documents = error_msg
                logger.error(f"{error_msg}, Input User Stories (snippet): {user_stories_for_prompt[:200]}...")
                return {"design_documents": state.design_documents}
         

        else:
            try:
                            
                sys_prompt_content = prompt.DESIGN_DOCUMENTS_NO_FEEDBACK_SYS_PROMPT.format(
                    user_stories=user_stories_for_prompt,
                    project_name=project_name_for_prompt
                )
                prompt_string_content = prompt.DESIGN_DOCUMENTS_NO_FEEDBACK_PROMPT_STRING.format(
                    user_stories=user_stories_for_prompt,
                    project_name=project_name_for_prompt # Assuming this is also needed here
                )
                
                logger.debug(f"--- Formatted System Prompt for TDD (first 500 chars) ---")
                logger.debug(sys_prompt_content[:500] + "...")
                logger.debug(f"--- Formatted Human Prompt for TDD (first 500 chars) ---")
                logger.debug(prompt_string_content[:500] + "...")

                messages = [
                    SystemMessage(content=sys_prompt_content),
                    HumanMessage(content=prompt_string_content)
                ]
            
                response = self.llm.invoke(messages)
                state.design_documents = response.content if hasattr(response, 'content') else str(response)
                logger.info("Design documents generated successfully.")
                return {"design_documents": state.design_documents}

            except KeyError as ke:
                error_msg = f"KeyError during TDD prompt formatting: {str(ke)}. This means a placeholder in your DESIGN_DOCUMENTS_... prompts was not found in the .format() call."
                logger.error(error_msg)
                logger.error(f"User stories (snippet): {user_stories_for_prompt[:200]}")
                logger.error(f"Project name: {project_name_for_prompt}")
                state.design_documents = error_msg
                return {"design_documents": state.design_documents}
            except Exception as e:
                error_msg = f"Error generating design documents: {type(e).__name__} - {str(e)}"
                state.design_documents = error_msg
                logger.error(f"{error_msg}, Input User Stories (snippet): {user_stories_for_prompt[:200]}...")
                return {"design_documents": state.design_documents}
      
    @log_entry_exit
    def development_artifact(self, state: State) -> dict:
        """Generate development artifacts based on design documents."""
        logger.info("Generating development artifacts")
        if not state.design_documents:
            state.development_artifact = "No design documents generated yet."
            logger.warning("Cannot generate development artifacts without design documents.")
            return {"development_artifact": state.development_artifact}
        
        # Escape design_documents and project_name for .format()
        design_documents_for_prompt = str(state.design_documents).replace('{', '{{').replace('}', '}}')
        project_name_val = state.project_name or 'N/A'
        project_name_for_prompt = str(project_name_val).replace('{', '{{').replace('}', '}}')

        if feedback := state.get_last_feedback_for_stage(SDLCStages.DEVELOPMENT):
            feedback_for_prompt = str(feedback).replace('{', '{{').replace('}', '}}')
            logger.info(f"Feedback for development artifacts: {feedback_for_prompt[:200]}...")  # Log a snippet
            try:
                prompt_string = prompt.DEVELOPMENT_ARTIFACT_FEEDBACK_PROMPT_STRING.format(
                    design_documents=design_documents_for_prompt,
                    feedback=feedback_for_prompt
                )
                sys_prompt_content = prompt.DEVELOPMENT_ARTIFACT_FEEDBACK_SYS_PROMPT.format(
                    design_documents=design_documents_for_prompt,
                    project_name=project_name_for_prompt,
                    feedback=feedback_for_prompt
                )
                messages = [
                    SystemMessage(content=sys_prompt_content),
                    HumanMessage(content=prompt_string)
                ]
                response = self.llm.invoke(messages)
                state.development_artifact = response.content if hasattr(response, 'content') else str(response)
                return {"development_artifact": state.development_artifact}
            except KeyError as ke:
                error_msg = f"KeyError during DEVELOPMENT_ARTIFACT_FEEDBACK prompt formatting: {str(ke)}."
                logger.error(error_msg)
                logger.error(f"Design documents (snippet): {design_documents_for_prompt[:200]}")
        else: 

            try:
                prompt_string = prompt.DEVELOPMENT_ARTIFACT_PROMPT_STRING.format(
                    design_documents=design_documents_for_prompt,
                    project_name=project_name_for_prompt
                    
                )
                sys_prompt_content = prompt.DEVELOPMENT_ARTIFACT_SYS_PROMPT.format(
                    project_name=project_name_for_prompt
                )
                messages = [
                    SystemMessage(content=sys_prompt_content),
                    HumanMessage(content=prompt_string)
                ]
                response = self.llm.invoke(messages)
                state.development_artifact = response.content if hasattr(response, 'content') else str(response)
                return {"development_artifact": state.development_artifact}
            except KeyError as ke:
                error_msg = f"KeyError during DEVELOPMENT_ARTIFACT prompt formatting: {str(ke)}."
                logger.error(error_msg)
                state.development_artifact = error_msg
                return {"development_artifact": state.development_artifact}
            except Exception as e:
                logger.error(f"Error generating development artifacts: {e}")
                state.development_artifact = f"Error generating development artifacts: {str(e)}"
                return {"development_artifact": state.development_artifact}
    
    @log_entry_exit
    def testing_artifact(self, state: State) -> dict:
        """Generate testing artifacts based on development artifacts."""
        logger.info("Generating testing artifacts")
        if not state.development_artifact:
            state.testing_artifact = "No development artifacts generated yet."
            logger.warning("Cannot generate testing artifacts without development artifacts.")
            return {"testing_artifact": state.testing_artifact}

        # Escape inputs for .format()
        user_stories_for_prompt = str(state.user_stories).replace('{', '{{').replace('}', '}}')
        development_artifact_for_prompt = str(state.development_artifact).replace('{', '{{').replace('}', '}}')
        project_name_val = state.project_name or 'N/A'
        project_name_for_prompt = str(project_name_val).replace('{', '{{').replace('}', '}}')

        if feedback := state.get_last_feedback_for_stage(SDLCStages.TESTING):
            feedback_for_prompt = str(feedback).replace('{', '{{').replace('}', '}}')
            logger.info(f"Feedback for testing artifacts: {feedback_for_prompt[:200]}...")  # Log a snippet
            try:
                prompt_string = prompt.TESTING_ARTIFACT_FEEDBACK_PROMPT_STRING.format(
                    user_stories=user_stories_for_prompt,
                    development_artifact=development_artifact_for_prompt,
                    feedback=feedback_for_prompt
                )
                sys_prompt_content = prompt.TESTING_ARTIFACT_FEEDBACK_SYS_PROMPT.format(
                    project_name=project_name_for_prompt,
                    feedback=feedback_for_prompt
                )
                messages = [
                    SystemMessage(content=sys_prompt_content),
                    HumanMessage(content=prompt_string)
                ]
                response = self.llm.invoke(messages)
                state.testing_artifact = response.content if hasattr(response, 'content') else str(response)
                return {"testing_artifact": state.testing_artifact}
            except KeyError as ke:
                error_msg = f"KeyError during TESTING_ARTIFACT_FEEDBACK prompt formatting: {str(ke)}."
                logger.error(error_msg)
                logger.error(f"User stories (snippet): {user_stories_for_prompt[:200]}")
                logger.error(f"Development artifact (snippet): {development_artifact_for_prompt[:200]}")
                state.testing_artifact = error_msg
                return {"testing_artifact": state.testing_artifact}
            except Exception as e:
                error_msg = f"Error generating testing artifacts with feedback: {type(e).__name__} - {str(e)}"
                state.testing_artifact = error_msg
                logger.error(f"{error_msg}, Input User Stories (snippet): {user_stories_for_prompt[:200]}...")
                return {"testing_artifact": state.testing_artifact}
         
         # No feedback case
        else:
            
            try:
                prompt_string = prompt.TESTING_ARTIFACT_PROMPT_STRING.format(
                    user_stories=user_stories_for_prompt,
                    development_artifact=development_artifact_for_prompt
                )
                sys_prompt_content = prompt.TESTING_ARTIFACT_SYS_PROMPT.format(
                    project_name=project_name_for_prompt
                )
                messages = [
                    SystemMessage(content=sys_prompt_content),
                    HumanMessage(content=prompt_string)
                ]
                response = self.llm.invoke(messages)
                state.testing_artifact = response.content if hasattr(response, 'content') else str(response)
                return {"testing_artifact": state.testing_artifact}
            except KeyError as ke:
                error_msg = f"KeyError during TESTING_ARTIFACT prompt formatting: {str(ke)}."
                logger.error(error_msg)
                state.testing_artifact = error_msg
                return {"testing_artifact": state.testing_artifact}
            except Exception as e:
                logger.error(f"Error generating testing artifacts: {e}")
                state.testing_artifact = f"Error generating testing artifacts: {str(e)}"
                return {"testing_artifact": state.testing_artifact}
    
    @log_entry_exit
    def deployment_artifact(self, state: State) -> dict:
        """Generate deployment artifacts based on testing artifacts."""
        logger.info("Generating deployment artifacts")
        if not state.testing_artifact:
            state.deployment_artifact = "No testing artifacts generated yet."
            logger.warning("Cannot generate deployment artifacts without testing artifacts.")
            return {"deployment_artifact": state.deployment_artifact}

  
        testing_artifact_for_prompt = str(state.testing_artifact).replace('{', '{{').replace('}', '}}')
        project_name_val = state.project_name or 'N/A'
        project_name_for_prompt = str(project_name_val).replace('{', '{{').replace('}', '}}')
        
        try:
            # --- IMPORTANT: Review prompt.DEPLOYMENT_ARTIFACT_PROMPT_STRING ---
            # It currently has .format(state=state). This is unusual.
            # It should likely be .format(testing_artifact=testing_artifact_for_prompt, project_name=project_name_for_prompt)
            # or similar, depending on its actual placeholders.
            # For now, I'll assume it expects 'testing_artifact' and 'project_name' as keys.
            # You MUST adjust this if your prompt uses different placeholder names.
            
            # Tentative formatting based on common patterns, ADJUST IF YOUR PROMPT IS DIFFERENT
            try:
                prompt_string_content = prompt.DEPLOYMENT_ARTIFACT_PROMPT_STRING.format(
                    testing_artifact=testing_artifact_for_prompt 
                    # Add other fields from 'state' if your prompt actually uses them like {state.project_name}
                )
                # Assuming DEPLOYMENT_ARTIFACT_SYS_PROMPT expects project_name
                sys_prompt_content = prompt.DEPLOYMENT_ARTIFACT_SYS_PROMPT.format(
                    project_name=project_name_for_prompt
                )
            except KeyError as ke:
                 # Fallback if the prompt string uses {state.testing_artifact} directly (less common for general prompts)
                if 'state.testing_artifact' in str(ke): # Check if the error is about 'state.testing_artifact'
                    prompt_string_content = prompt.DEPLOYMENT_ARTIFACT_PROMPT_STRING.format(
                        state=state # Pass the whole state object if the prompt needs it this way
                    )
                    sys_prompt_content = prompt.DEPLOYMENT_ARTIFACT_SYS_PROMPT.format(
                        project_name=project_name_for_prompt # This part is likely fine
                    )
                else: # Re-raise if it's a different KeyError
                    raise ke


            messages = [
                SystemMessage(content=sys_prompt_content), 
                HumanMessage(content=prompt_string_content)
            ]
            response = self.llm.invoke(messages)
            state.deployment_artifact = response.content if hasattr(response, 'content') else str(response)
            return {"deployment_artifact": state.deployment_artifact}
        except KeyError as ke:
            error_msg = f"KeyError during DEPLOYMENT_ARTIFACT prompt formatting: {str(ke)}. Review prompt placeholders."
            logger.error(error_msg)
            logger.error(f"Prompt string might be: {prompt.DEPLOYMENT_ARTIFACT_PROMPT_STRING}")
            state.deployment_artifact = error_msg
            return {"deployment_artifact": state.deployment_artifact}
        except Exception as e:
            logger.error(f"Error generating deployment artifacts: {e}")
            state.deployment_artifact = f"Error generating deployment artifacts: {str(e)}"
            return {"deployment_artifact": state.deployment_artifact}
            
    @log_entry_exit
    def process_feedback(self, state: State) -> dict:
        """
        Process user feedback and update state with decision.
        """
        logger.info(f"Processing feedback. Current feedback state: {state.feedback}")
        current_stage = state.current_stage
        # feedback_decision is set by the UI/controller before calling this node
        feedback_text_from_ui = state.feedback.get(current_stage.value, [None])[-1] # Get latest feedback for current stage

        logger.info(f"Processing feedback for stage: {current_stage}, Decision from UI: {state.feedback_decision}, Text: {feedback_text_from_ui}")

        if state.feedback_decision == "accept":
            logger.info(f"Feedback for stage '{current_stage}' is ACCEPT based on UI decision.")
            # Optionally, store "accept" as a feedback entry if needed for history, though decision is primary
            state.add_feedback(current_stage, "User accepted.") 
        elif state.feedback_decision == "reject":
            logger.info(f"Feedback for stage '{current_stage}' is REJECT based on UI decision. Feedback text: {feedback_text_from_ui}")
            if feedback_text_from_ui:
                 state.add_feedback(current_stage, str(feedback_text_from_ui)) # Add the actual feedback text
            else:
                 state.add_feedback(current_stage, "User rejected, no specific feedback provided.")
        else: # Should not happen if UI sets feedback_decision correctly
            logger.warning(f"Unknown feedback_decision '{state.feedback_decision}' for stage {current_stage}. Defaulting to reject.")
            state.feedback_decision = "reject"
            state.add_feedback(current_stage, f"System default to reject due to unknown decision: {state.feedback_decision}")
       
        logger.info(f"Updated feedback state: {state.feedback}")
        return {"feedback_decision": state.feedback_decision}   

    @log_entry_exit
    def feedback_route(self, state: State) -> str:
        """Routes based on the feedback decision stored in the state."""
        logger.info(f"Entering feedback_route with decision: {state.feedback_decision}")

        if not isinstance(state, State):
            logger.error(f"Invalid state type: {type(state)}. Routing to reject.")
            return "reject" # Or handle as an error state

        decision = state.feedback_decision # Already processed in process_feedback

        if decision == "accept":
            logger.info("Feedback accepted. Routing to next stage.")
            next_stage = state.get_next_stage()
            if next_stage:
                state.update_stage(next_stage) # This should update current_stage
                st.session_state["current_stage"] = state.current_stage # Reflect in Streamlit
                logger.info(f"Updated state to next stage: {state.current_stage}")
            else:
                logger.info("No next stage available. Ending process.")
                # No need to update current_stage if ending
            
            state.clear_feedback_decision() # Clear for the next cycle
            st.session_state["feedback_decision"] = None # Reflect in Streamlit
            # Clear specific feedback text from UI for the accepted stage if desired
            # st.session_state["feedback"] = {} # Or selectively clear
            logger.info(f"Feedback decision cleared. Current state feedback: {state.feedback}")
            return "accept"
        else: # Covers 'reject' and any other case defaulting to reject
            logger.info(f"Feedback decision is '{decision}'. Routing back for revision of stage {state.current_stage}.")
            # The current stage remains the same for revision.
            state.clear_feedback_decision()
            st.session_state["feedback_decision"] = None
            logger.info(f"Feedback decision cleared for revision. Current state feedback: {state.feedback}")
            return "reject"