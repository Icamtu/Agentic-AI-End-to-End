from typing import Annotated, List, TypedDict, Optional, Dict, Any
from datetime import datetime
import operator
from pydantic import BaseModel, Field
from langgraph.graph.message import add_messages
from enum import Enum
class State(TypedDict):

    messages: Annotated[list, add_messages] # Chat history including user inputs and AI responses

# Schema for structured output to use in planning
class Section(BaseModel):
    name: str = Field(description="Name for this section of the report.")
    description: str = Field(description="Brief overview of the main topics and concepts to be covered in this section.")

class Sections(BaseModel):
    sections: List[Section] = Field(description="Sections of the report.")

# Graph state
class BlogState(TypedDict):

    messages: Annotated[list, add_messages] 
    #inputs
    topic: str  # Report topic from user input
    objective: str  # Objective from user input
    target_audience: str  # Target audience from user input
    tone_style: str  # Tone/style from user input
    word_count: int  # Word count from user input
    structure: str  # Structure from user input
    feedback: str  # Human feedback

    #for workers
    sections: List[Section]  # List of report sections
    completed_sections: Annotated[List[str], operator.add]  # All workers write to this key in parallel
    
    #for display in UI
    initial_draft: str  # Initial draft of the report
    final_report: str  # Final report
    draft_approved: bool  # Whether the draft is approved



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