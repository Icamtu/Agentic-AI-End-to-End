from typing import Annotated, List, TypedDict
import operator
from pydantic import BaseModel, Field
from langgraph.graph.message import add_messages

# Schema for structured output to use in planning
class Section(BaseModel):
    name: str = Field(description="Name for this section of the report.")
    description: str = Field(description="Brief overview of the main topics and concepts to be covered in this section.")

class Sections(BaseModel):
    sections: List[Section] = Field(description="Sections of the report.")

# Graph state
class State(TypedDict):

    messages: Annotated[list, add_messages] # Chat history including user inputs and AI responses
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

# Worker state
class WorkerState(TypedDict):
    section: Section
    completed_sections: Annotated[List[str], operator.add]