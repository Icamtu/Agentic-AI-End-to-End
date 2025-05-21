import logging
from langgraph.graph import StateGraph, START, END
from langgraph.constants import Send
import json
from datetime import datetime
from langgraph.checkpoint.memory import MemorySaver
from typing import Annotated, List, TypedDict, Optional, Dict, Any, Literal
from pydantic import BaseModel, Field
from enum import Enum
from langchain_core.messages import SystemMessage, HumanMessage
import os
from dotenv import load_dotenv
import functools
import time

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format="\n**********\n%(levelname)s | %(asctime)s | %(message)s\n**********\n",
    datefmt="%Y-%m-%d %H:%M:%S"
)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()
os.environ["LANGSMITH_API_KEY"] = os.getenv("LANGCHAIN_API_KEY")

# Define the model
from langchain_google_genai import ChatGoogleGenerativeAI
model = ChatGoogleGenerativeAI(model="gemini-2.0-flash", temperature=0)

#########################
#########STATE###########
########################

class SDLCStages(Enum):
    """Software Development Life Cycle (SDLC) stages."""
    PLANNING = "planning"
    DESIGN = "design"
    DEVELOPMENT = "development"
    TESTING = "testing"
    DEPLOYMENT = "deployment"
    COMPLETE = "complete"
    
class SDLCState(BaseModel):
    """Software Development Life Cycle (SDLC) state."""
    
    # core state attributes 
    session_id: str = Field(..., description="Unique identifier for the session.")
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
        """Update current stage and record in history."""
        self.history.append({
            "stage": self.current_stage.value if isinstance(self.current_stage, SDLCStages) else self.current_stage,
            "timestamp": datetime.now().isoformat()
        })
        self.current_stage = new_stage
        self.last_updated = datetime.now().isoformat()
        
    def add_feedback(self, stage: SDLCStages, feedback_text: str):
        """Add feedback for a specific stage."""
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
        """Get the next stage in the SDLC process."""
        stages_list = list(SDLCStages)
        try:
            current_index = stages_list.index(self.current_stage)
            if current_index < len(stages_list) - 1:
                return stages_list[current_index + 1]
            return SDLCStages.COMPLETE
        except ValueError:
            return SDLCStages.PLANNING
    
    def get_all_artifacts(self) -> Dict[str, Optional[str]]:
        """Get all artifacts in the state."""
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

class SdlcNode:
    def __init__(self, model):
        """Initialize the SDLC Node with an LLM."""
        self.llm = model

    def user_input(self, state: SDLCState) -> dict:
        """Handle user input, distinguishing between initial requirements and feedback."""
        logger.debug(f"Executing user_input with state: {state}")
        if state.get_last_feedback_for_stage(SDLCStages.PLANNING):
            state.user_stories = None

        # For testing, use hard-coded values instead of Streamlit
        # In production, uncomment and use the streamlit imports
        state.project_name = "Test Project"  # st.session_state.get("project_name")
        state.project_description = "Test Description"  # st.session_state.get("project_description")
        state.project_goals = "Test Goals"  # st.session_state.get("project_goals")
        state.project_scope = "Test Scope"  # st.session_state.get("project_scope")
        state.project_objectives = "Test Objectives"  # st.session_state.get("project_objectives")

        return {"user_input": "captured"}

    def generate_requirements(self, state: SDLCState) -> dict:
        """Dummy requirements generator for testing feedback loop."""
        logger.debug("Dummy generate_requirements called")
        state.generated_requirements = "DUMMY REQUIREMENTS"
        return {"generated_requirements": state.generated_requirements}

    def generate_user_stories(self, state: SDLCState) -> dict:
        """Dummy user stories generator for testing feedback loop."""
        logger.debug("Dummy generate_user_stories called")
        state.user_stories = "DUMMY USER STORIES"
        return {"user_stories": state.user_stories}
    
    def process_feedback(self, state: SDLCState) -> dict:
        """Process user feedback and update state with decision."""
        current_stage_value = state.current_stage.value if isinstance(state.current_stage, SDLCStages) else state.current_stage
        logger.debug(f"Processing feedback for stage: {current_stage_value}")

        # Simplified feedback check - just look at the feedback value in state
        feedback = state.feedback.get(current_stage_value, [])
        latest_feedback = feedback[-1] if feedback else None
        
        if latest_feedback and latest_feedback.strip().lower() == "accept":
            state.feedback_decision = "accept"
        else:
            state.feedback_decision = "reject"
            
        logger.debug(f"Feedback decision: {state.feedback_decision}")
        return {
            "feedback_decision": state.feedback_decision,
            "feedback": state.feedback
        }
    
    def feedback_route(self, state: SDLCState) -> str:
        """Simplified routing based on feedback decision."""
        # Simple routing based on feedback_decision attribute
        if hasattr(state, "feedback_decision"):
            route = "accept" if state.feedback_decision == "accept" else "reject"
            logger.debug(f"Routing based on feedback_decision: {route}")
            return route
        
        # Fallback to reject if no decision found
        logger.debug("No feedback_decision found, defaulting to 'reject'")
        return "reject"

##################################################################################################
########################          graph_builder           ##########################################
##################################################################################################

class SdlcGraphBuilder:
    def __init__(self, llm, memory: MemorySaver=None):
        self.llm = llm
        # self.memory = memory or MemorySaver()

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
                interrupt_before=["ProcessFeedback"]
                # checkpointer=self.memory
            )
            # logger.debug("Graph compiled with checkpointer: %s", self.memory)
            return graph
        except Exception as e:
            logger.error(f"Error building graph: {e}")
            raise

# Initialize the graph builder and agent
sdlc_builder_instance = SdlcGraphBuilder(model)
agent = sdlc_builder_instance.build_graph()