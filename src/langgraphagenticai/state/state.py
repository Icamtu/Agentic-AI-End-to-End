from typing import Annotated, List, Optional
from typing_extensions import TypedDict
from langgraph.graph.message import add_messages
import operator
from pydantic import BaseModel, Field

# Schema for Blog Generation sections
class Section(BaseModel):
    name: str = Field(description="Name for this section of the report.")
    description: str = Field(description="Brief overview of the main topics and concepts to be covered in this section.")

# Unified State for all use cases
class State(TypedDict, total=False):  # total=False makes all fields optional
    """
    Represents the structure of the state used in the graph for multiple use cases:
    - Chat Bot: messages
    - Bot with Tool: messages, tool_output
    - Blog Generation: messages, topic, sections, completed_sections, final_report
    - Code Reviewer: messages, code_input, review_output
    """
    messages: Annotated[List, add_messages]  # Common to all: Chat history
    topic: str  # Blog Generation: Report topic
    sections: List[Section]  # Blog Generation: List of report sections
    completed_sections: Annotated[List[str], operator.add]  # Blog Generation: Completed sections
    final_report: str  # Blog Generation: Final report
    tool_output: str  # Bot with Tool: Output from tool execution
    code_input: str  # Code Reviewer: Input code to review
    review_output: str  # Code Reviewer: Review results

# Worker State for Blog Generation
class WorkerState(TypedDict):
    section: Section
    completed_sections: Annotated[List[str], operator.add]