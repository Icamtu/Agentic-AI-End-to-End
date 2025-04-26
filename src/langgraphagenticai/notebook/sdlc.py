import logging
from langgraph.graph import StateGraph, START, END
from langgraph.constants import Send
# from src.langgraphagenticai.state.state import State, WorkerState, Sections, Section  # Import from state.py
from langchain_core.messages import SystemMessage, HumanMessage
# import streamlit as st
import json
from datetime import datetime
# from src.langgraphagenticai.graph.graph_builder import GraphBuilder

logging.basicConfig(
    level=logging.DEBUG,  # Set the logging level to DEBUG
    format="\n**********\n%(levelname)s | %(asctime)s | %(message)s\n**********\n",  # Custom format with \n and *
    datefmt="%Y-%m-%d %H:%M:%S"  # Date format for better readability
)


logger = logging.getLogger(__name__)

import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()
os.environ["LANGSMITH_API_KEY"] = os.getenv("LANGCHAIN_API_KEY")



from langchain_google_genai import ChatGoogleGenerativeAI
# Define the model
model = ChatGoogleGenerativeAI(model="gemini-2.0-flash", temperature=0)


#########################
#########STATE###########
########################

from typing import Annotated, List, TypedDict, Optional, Dict, Any, Literal
from datetime import datetime
import operator
from pydantic import BaseModel, Field
from langgraph.graph.message import add_messages
from enum import Enum


# Schema for structured output to use in planning

#


class SDLCStages(Enum):
    """Software Development Life Cycle (SDLC) stages.
    This class defines the stages of the software development life cycle, including planning, design, development, testing, deployment.
    """
    
    PLANNING = "planning"
    DESIGN = "design"
    DEVELOPMENT = "development"
    TESTING = "testing"
    DEPLOYMENT = "deployment"
    COMPLETE = "complete"
    
class SDLCState(BaseModel):

    """
    Software Development Life Cycle (SDLC) state.
    This class represents the state of a software development project, including the current stage, inputs, artifacts, and feedback.
    
    eg:
    Requirements are the foundation of any project. They provide a clear understanding of what needs to be built and why. In the context of software development, requirements are typically categorized into four main types:
    1. Project Description:

        Definition: A concise and high-level summary of what the project is about. It provides a general understanding of the project's purpose and nature.
        Focus: Briefly explains the project to someone unfamiliar with it.
        Level of Detail: High-level, introductory.
    2. Project Goals:

        Definition: Broad, overarching statements that define the desired long-term outcomes or the ultimate impact the project aims to achieve. They are often strategic and qualitative.   
        Focus: The "why" behind the project – what business benefit or overall improvement is expected.
        Level of Detail: High-level, aspirational.
    3. Project Scope:

        Definition: Clearly defines the boundaries of the project. It specifies what will be included in the project and, equally importantly, what will not be included. It outlines the deliverables, features, functions, tasks, and resources involved.   
        Focus: The "what" of the project – what work needs to be done and what will be delivered.
        Level of Detail: Detailed, specific inclusions and exclusions.
    4. Project Objectives:

        Definition: Specific, measurable, achievable, relevant, and time-bound (SMART) statements that detail how the project goals will be accomplished. They are concrete steps or milestones that contribute to achieving the broader goals.   
        Focus: The "how" of achieving the goals – the specific, actionable steps and targets.   
        Level of Detail: Specific, quantifiable, and time-bound.
        Example Project: Developing a Mobile Application for a Local Bookstore

Project Description: Develop a user-friendly mobile application for "The Book Nook," a local bookstore in Bangalore, to allow customers to browse their inventory, place orders online, and learn about upcoming events.


"""

    # core state attributes 
    session_id: str = Field(...,description="Unique identifier for the session.")
    current_stage: SDLCStages = Field(default=SDLCStages.PLANNING, description="Current stage of the software development life cycle.")

   # Inputs gathered during various stages, especially Planning
    project_name: Optional[str] = Field(None, description="Name of the project.")
    project_description: Optional[str] = Field(None, description="Description of the project.")
    project_goals: Optional[str] = Field(None, description="Goals of the project.")
    project_scope: Optional[str] = Field(None, description="Scope of the project.")
    project_objectives: Optional[str] = Field(None, description="Objectives of the project.")
    requirements: Optional[str] = Field(None, description="Detailed project requirements.")
    user_stories: Optional[str] = Field(None, description="User stories generated based on requirements.")

    # Artifacts generated during different SDLC stages
    generated_requirements: Optional[str] = Field(None, description="Generated requirements based on user input.")
    generated_user_stories: Optional[str] = Field(None, description="Generated user stories based on requirements.")
    planning_artifact: Optional[str] = Field(None, description="Artifact generated during the planning stage.")
    design_artifact: Optional[str] = Field(None, description="Artifact generated during the design stage.")
    development_artifact: Optional[str] = Field(None, description="Artifact generated during the development stage.")
    testing_artifact: Optional[str] = Field(None, description="Artifact generated during the testing stage.")
    deployment_artifact: Optional[str] = Field(None, description="Artifact generated during the deployment stage.")

    # Feedback
    feedback: Dict[str, List[str]] = Field(default_factory=dict, description="User feedback by stage")
    feedback_decision: Optional[str] = Field(None, description="Decision after processing feedback (accept/reject)")

    # Metadata
    created_at: str = Field(default_factory=lambda: datetime.now().isoformat(), description="Creation timestamp")
    last_updated: str = Field(default_factory=lambda: datetime.now().isoformat(), description="Last update timestamp")
    history: List[Dict[str, Any]] = Field(default_factory=list, description="State history for monitoring")

    def to_dict(self) -> Dict[str, Any]:
        """Convert state to dictionary."""
        return self.model_dump()

    
    def update_stage(self, new_stage: SDLCStages):
        """
        Update current stage and record in history.

        Args:
            new_stage (SDLCStages): The new stage.
        """
        # Record current state in history
        self.history.append({
            "stage": self.current_stage.value if isinstance(self.current_stage, SDLCStages) else self.current_stage,
            "timestamp": datetime.now().isoformat()
        })

        # Update stage
        self.current_stage = new_stage
        self.last_updated = datetime.now().isoformat()
    def add_feedback(self, stage: SDLCStages, feedback_text: str):
        """
        Add feedback for a specific stage.

        Args:
            stage (SDLCStages): The SDLC stage.
            feedback_text (str): The feedback text.
        """
        stage_value = stage.value
        if stage_value not in self.feedback:
            self.feedback[stage_value] = []

        self.feedback[stage_value].append(feedback_text)
        self.last_updated = datetime.now().isoformat()
    
    def get_last_feedback_for_stage(self, stage: SDLCStages) -> Optional[str]:
        """Get the last feedback entry for a specific SDLC stage."""
        stage_value = stage.value
        if stage_value in self.feedback and self.feedback[stage_value]:
            return self.feedback[stage_value][-1]
        return None

    def get_next_stage(self) -> Optional[SDLCStages]:
        """
        Get the next stage in the SDLC process.

        Returns:
            Optional[SDLCStages]: The next stage, or None if at the end.
        """
        stages_list = list(SDLCStages)
        try:
            current_index = stages_list.index(self.current_stage)
            if current_index < len(stages_list) - 1:
                return stages_list[current_index + 1]
            return SDLCStages.COMPLETE  # Or None, depending on desired end behavior
        except ValueError:
            return SDLCStages.PLANNING
    


    def get_all_artifacts(self) -> Dict[str, Optional[str]]:
        """
        Get all artifacts in the state.

        Returns:
            Dict[str, Optional[str]]: All artifacts.
        """
        return {
            "requirements": self.requirements,
            "planning_artifact": self.planning_artifact,
            "design_artifact": self.design_artifact,
            "development_artifact": self.development_artifact,
            "testing_artifact": self.testing_artifact,
            "deployment_artifact": self.deployment_artifact,
        }



########################################################################################################
##############################sdlcNode########################################################
########################################################################################################

from langgraph.graph import StateGraph, START, END
# from src.langgraphagenticai.state.state import SDLCStages, SDLCState as State
from langchain_core.messages import SystemMessage, HumanMessage
import streamlit as st
import json
from datetime import datetime
from typing import List
# from src.langgraphagenticai.logging.logging_utils import logger, log_entry_exit


import functools
import time


class SdlcNode:
    def __init__(self, model):
        """Initialize the BlogGenerationNode with an LLM."""
        self.llm = model

    # @log_entry_exit
    def user_input(self, state: SDLCState) -> dict:
        """Handle user input, distinguishing between initial requirements and feedback."""
        logger.debug(f"Executing user_input with state: {state}")
        if state.get_last_feedback_for_stage(SDLCStages.PLANNING):
            state.user_stories = None

        state.project_name = st.session_state.get("project_name")
        state.project_description = st.session_state.get("project_description")
        state.project_goals = st.session_state.get("project_goals")
        state.project_scope = st.session_state.get("project_scope")
        state.project_objectives = st.session_state.get("project_objectives")

        return {"user_input": "captured"}

    # def generate_requirements(self, state: SDLCState) -> dict:
    #     """Generate requirements based on user input."""
    #     logger.debug(f"Generating requirements with state: {state}")
    #     try:
    #         requirements_input = {
    #             "project_name": state.project_name if state.project_name is not None else "No project name provided",
    #             "project_description": state.project_description if state.project_description is not None else "No project description provided",
    #             "project_goals": state.project_goals if state.project_goals is not None else "No project goals provided",
    #             "project_scope": state.project_scope if state.project_scope is not None else "No project scope provided",
    #             "project_objectives": state.project_objectives if state.project_objectives is not None else "No project objectives provided",
    #         }
    #         prompt_string = f"""Based on the following project details, generate a comprehensive list of detailed software requirements.
    #                             Ensure the requirements are clear, unambiguous, verifiable, and complete based on the provided description, goals, scope, and objectives.

    #                             Project Details:
    #                             {json.dumps(requirements_input, indent=2)}

    #                             Detailed Requirements:
    #                         """""
    #         # Construct a list of messages for the LLM
    #         messages = [SystemMessage(content="You are an expert project requirements generator."),HumanMessage(content=prompt_string)]
    #         response = self.llm.invoke(messages)
    #         state.generated_requirements = response.content if hasattr(response, 'content') else str(response)  
    #         return {"generated_requirements": state.generated_requirements}
    #     except Exception as e:
    #         logger.error(f"Error generating requirements: {e}")
    #         state.generated_requirements = f"Error generating requirements: {str(e)}"
    #         return {"generated_requirements": state.generated_requirements}

    def generate_requirements(self, state: SDLCState) -> dict:
        """Dummy requirements generator for testing feedback loop."""
        logger.debug("Dummy generate_requirements called")
        state.generated_requirements = "DUMMY REQUIREMENTS"
        return {"generated_requirements": state.generated_requirements}

    # def generate_user_stories(self, state: SDLCState) -> dict:
    #     """Generate user stories based on the requirements, incorporating feedback if available."""
    #     logger.debug("Generating user stories")
    #     if not state.generated_requirements:
    #         state.user_stories = "No requirements generated yet."
    #         logger.warning("Cannot generate user stories without requirements.")
    #         return {"user_stories": state.user_stories}
        
    #     feedback = state.get_last_feedback_for_stage(SDLCStages.PLANNING)
    #     logger.debug(f"Feedback for user stories: {feedback}")
    #     if feedback:
    #         prompt_string = f"""Based on the following software requirements AND feedback, generate a list of user stories.
    #                         The previous version was rejected for the following reason: "{feedback}"
    #                         Please make sure to address this feedback in your new user stories.
                            
    #                         Each user story should follow the format: 'As a [type of user], I want [some goal] so that [some reason/benefit].'
    #                         Ensure the user stories cover the key functionalities outlined in the requirements and are actionable from a development perspective.

    #                         Requirements:
    #                         {state.generated_requirements}
                            
    #                         Previous Feedback to Address:
    #                         {feedback}

    #                         User Stories:
    #                         """""
    #     else:

    #         try:
    #             if state.generated_requirements:
    #                 prompt_string =  f"""Based on the following software requirements, generate a list of user stories.
    #                                 Each user story should follow the format: 'As a [type of user], I want [some goal] so that [some reason/benefit].'
    #                                 Ensure the user stories cover the key functionalities outlined in the requirements and are actionable from a development perspective.

    #                                 Requirements:
    #                                 {state.generated_requirements}

    #                                 User Stories:
    #                                 """""
    #                 sys_prompt= f"""
    #                                 You are a Senior Software Analyst expert in Agile SDLC and user story creation. Your task is to generate detailed user stories based on the provided requirements.

    #                                 Project Name: {state.project_name or 'N/A'}

    #                                 Guidelines:

    #                                 One Requirement = One User Story: Create a distinct user story for each functional requirement identified.
    #                                 Unique Identifier: Assign each user story a unique ID: [PROJECT_CODE]-US-[XXX] (e.g., BN-US-001 for 'The Book Nook'). Use a short uppercase code for the project.
    #                                 Structure (for each story):
    #                                 Unique Identifier: [PROJECT_CODE]-US-XXX
    #                                 Title: Clear summary of the functionality.
    #                                 Description: As a [user role], I want [goal/feature] so that [reason/benefit].
    #                                 Acceptance Criteria: Bulleted list of testable conditions (- [Criterion]).
    #                                 Clarity: Use domain-specific terms. Ensure stories are specific, testable, achievable, and Agile-aligned. 
    #                                 {f'5. Incorporate Feedback: The previous version was rejected. Address the following feedback while refining the user stories: "{feedback}"' if feedback else ''} """ 
                    
    #                 messages = [
    #                     SystemMessage(content=sys_prompt),
    #                     HumanMessage(content=prompt_string)
    #                 ]
    #                 response = self.llm.invoke(messages)
    #                 state.user_stories = response.content if hasattr(response, 'content') else str(response)
    #                 return {"user_stories": state.user_stories}
    #             else:
    #                 state.user_stories = "No requirements generated yet."
    #                 return {"user_stories": state.user_stories}
    #         except Exception as e:
    #             logger.error(f"Error generating user stories: {e}")
    #             state.user_stories = f"Error generating user stories: {str(e)}"
    #             return {"user_stories": state.user_stories}

    def generate_user_stories(self, state: SDLCState) -> dict:
        """Dummy user stories generator for testing feedback loop."""
        logger.debug("Dummy generate_user_stories called")
        state.user_stories = "DUMMY USER STORIES"
        return {"user_stories": state.user_stories}
    
    
    def process_feedback(self, state: SDLCState) -> dict:
        """
        Process user feedback passed via state and update state with decision.
        Only { "current_stage": ["accept"] } ends the process.
        """
        current_stage_value = state.current_stage.value if isinstance(state.current_stage, SDLCStages) else state.current_stage
        logger.debug(f"Processing feedback for stage: {current_stage_value}")

        raw_feedback = state.feedback
        logger.debug(f"Raw feedback data: {raw_feedback}")

        # Only accept if feedback is {current_stage: ["accept"]}
        if (
            isinstance(raw_feedback, dict)
            and current_stage_value in raw_feedback
            and isinstance(raw_feedback[current_stage_value], list)
            and raw_feedback[current_stage_value]
            and raw_feedback[current_stage_value][-1].strip().lower() == "accept"
        ):
            state.feedback_decision = "accept"
            return {
                "feedback_decision": "accept",
                "feedback": state.feedback
            }
        else:
            state.feedback_decision = "reject"
            return {
                "feedback_decision": "reject",
                "feedback": state.feedback
            }
    
    def feedback_route(self, state: SDLCState) -> str:
        logger.debug(f"Routing feedback with state type: {type(state)}")
        logger.debug(f"State content: {state}")
        
        feedback_decision = None
        
        # If state is a dict with feedback_decision
        if isinstance(state, dict) and "feedback_decision" in state:
            feedback_decision = state["feedback_decision"]
            logger.debug(f"Found feedback_decision in state dict: {feedback_decision}")
        # If state is a SDLCState object
        elif isinstance(state, SDLCState):
            logger.debug(f"State is SDLCState object")
            if hasattr(state, "feedback_decision"):
                feedback_decision = state.feedback_decision
                logger.debug(f"Found feedback_decision as attribute: {feedback_decision}")
        # Try to get from node output
        else:
            logger.debug(f"State is neither dict nor SDLCState, trying alternative methods")
            try:
                if hasattr(state, "get"):
                    node_output = state.get("ProcessFeedback", {})
                    logger.debug(f"ProcessFeedback node output: {node_output}")
                    feedback_decision = node_output.get("feedback_decision")
                    logger.debug(f"Found feedback_decision in node output: {feedback_decision}")
            except Exception as e:
                logger.error(f"Error extracting feedback_decision: {e}")
        
        route = "accept" if feedback_decision == "accept" else "reject"
        logger.debug(f"Final routing decision: {route}")
        return route


##################################################################################################
########################          graph_builder           ##########################################
##################################################################################################

# src/langgraphagenticai/graph/graph_builder_sdlc.py
from langgraph.graph import StateGraph, START, END
# from src.langgraphagenticai.nodes.sdlc_node import SdlcNode
# from src.langgraphagenticai.state.state import SDLCStages, SDLCState as State
from langgraph.checkpoint.memory import MemorySaver
from pydantic import BaseModel, Field
from langchain_core.messages import SystemMessage, HumanMessage
import logging
import json
import logging
import functools
import time
# from src.langgraphagenticai.logging.logging_utils import logger, log_entry_exit

class SdlcGraphBuilder:
    def __init__(self, llm, memory: MemorySaver=None):
        self.llm = llm
        self.memory = MemorySaver()

    # @log_entry_exit
    def build_graph(self):
        try:
            if not self.llm:
                raise ValueError("LLM model not initialized")

            graph_builder = StateGraph(state_schema=SDLCState)
            sldc_node = SdlcNode(self.llm)

            # Add nodes
            graph_builder.add_node("Requirement", sldc_node.user_input)
            graph_builder.add_node("GenerateRequirements", sldc_node.generate_requirements)
            graph_builder.add_node("GenerateUserStories", sldc_node.generate_user_stories)
            graph_builder.add_node("ProcessFeedback", sldc_node.process_feedback)

            # Define Edges
            graph_builder.add_edge(START, "Requirement")
            graph_builder.add_edge("Requirement", "GenerateRequirements")
            graph_builder.add_edge("GenerateRequirements", "GenerateUserStories")
            graph_builder.add_edge("GenerateUserStories", "ProcessFeedback")

            # Conditional edge after feedback processing
            graph_builder.add_conditional_edges(
                "ProcessFeedback",
                sldc_node.feedback_route,
                {
                    "accept": END,
                    "reject": "GenerateUserStories"
                }
            )

            # Compile with interrupt
            graph = graph_builder.compile(
                interrupt_before=["ProcessFeedback"],
                checkpointer=self.memory
            )
            logger.debug("Graph compiled with checkpointer: %s", self.memory)
            return graph
        except Exception as e:
            logger.error(f"Error building graph: {e}")
            raise

# Assuming 'model' is your initialized LLM
sdlc_builder_instance = SdlcGraphBuilder(model)
agent = sdlc_builder_instance.build_graph()