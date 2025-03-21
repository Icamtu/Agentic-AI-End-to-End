# src/langgraphagenticai/state/state.py
from typing import List, Dict, Optional
from typing_extensions import TypedDict
from langchain_core.messages import BaseMessage

class Section(TypedDict):
    """Represents a single section of the blog."""
    name: str
    description: str

class State(TypedDict, total=False):
    """State schema for the LangGraph workflow, with all fields optional."""
    messages: List[BaseMessage]  # Chat history including user inputs and AI responses
    topic: str  # Blog topic from user input
    objective: str  # Blog objective (e.g., Informative, Persuasive)
    target_audience: str  # Intended audience (e.g., General Audience)
    tone_style: str  # Tone and style (e.g., Casual, Formal)
    word_count: int  # Target word count for the blog
    structure: str  # Blog structure (e.g., "Introduction, Main Points, Conclusion")
    sections: List[Section]  # List of blog sections with names and descriptions
    search_results: Dict[str, str]  # Web search results keyed by section name
    completed_sections: List[str]  # Generated sections of the draft
    needs_facts: bool  # Flag to trigger web search
    outline_feedback: str  # Feedback from outline review ("approved" or "add_more_details")
    draft_feedback: str  # Feedback from draft review ("approved" or "add_more_details")
    outline_approved: bool  # Approval status of the outline
    draft_approved: bool  # Approval status of the draft
    feedback: str  # General feedback string for revisions