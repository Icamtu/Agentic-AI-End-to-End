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

Project Description: Develop a user-friendly mobile application for "The Book Nook," a local bookstore in Nellore, to allow customers to browse their inventory, place orders online, and learn about upcoming events.

Project Goals:

        Increase sales and revenue for The Book Nook.
        Enhance customer engagement and loyalty.
        Modernize The Book Nook's presence and reach a wider audience in Nellore.
Project Scope:

Inclusions:
    Developing a mobile application compatible with Android and iOS.
    Features: Browsing book catalog with search and filtering, viewing book details (description, author, price, availability), creating user accounts, adding books to a shopping cart, secure online payment integration, order history, push notifications for new arrivals and events, information about store hours and location.
    Integration with the bookstore's existing inventory management system.
    Basic user support documentation.
Exclusions:
    Developing a separate tablet application.
    Implementing a loyalty points program (will be considered in a future phase).
    Integrating with social media platforms for direct purchasing.
    Providing real-time inventory updates beyond a daily sync.
    Developing advanced analytics dashboards for the bookstore owner in this phase.
Project Objectives (SMART):

    Increase online sales by 15% within the first six months of the app launch (Measurable, Achievable, Relevant, Time-bound).
    Achieve an average user rating of 4.5 stars or higher on both app stores within three months of launch (Measurable, Achievable, Relevant, Time-bound).
    Acquire 500 new registered app users within the first month of launch (Measurable, Achievable, Relevant, Time-bound).
    Successfully integrate the app with the existing inventory system with no data loss by the end of the development phase (Measurable, Achievable, Relevant, Time-bound).
    In Summary:

The description gives a general idea of the project.
The goals state the desired high-level outcomes.
The scope defines the boundaries of the work to be done.
The objectives provide specific, measurable steps to achieve the goals within the defined scope.   
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

    # Artifacts generated during different SDLC stages
    planning_artifact: Optional[str] = Field(None, description="Artifact generated during the planning stage.")
    design_artifact: Optional[str] = Field(None, description="Artifact generated during the design stage.")
    development_artifact: Optional[str] = Field(None, description="Artifact generated during the development stage.")
    testing_artifact: Optional[str] = Field(None, description="Artifact generated during the testing stage.")
    deployment_artifact: Optional[str] = Field(None, description="Artifact generated during the deployment stage.")

    # Feedback
    feedback: Dict[str, List[str]] = Field(default_factory=dict, description="User feedback by stage")

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