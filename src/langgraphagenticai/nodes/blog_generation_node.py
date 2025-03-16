# blog_generation_node.py
from src.langgraphagenticai.state.state import State, WorkerState, Section
from pydantic import BaseModel, Field
from typing import List
from langgraph.constants import Send
from langchain_core.messages import HumanMessage, SystemMessage

class Sections(BaseModel):
    sections: List[Section] = Field(description="Sections of the report.")

class BlogGenerationNode:
    def __init__(self, model):
        # Planner uses structured output for sections
        self.planner = model.with_structured_output(Sections)
        # LLM for content generation does not use structured output
        self.llm = model  # Raw LLM for generating text

    def orchestrator(self, state: State) -> dict:
        """Orchestrator that generates a plan for the report"""
        report_sections = self.planner.invoke(
            [
                SystemMessage(content="Generate a plan for the report."),
                HumanMessage(content=f"Here is the report topic: {state['topic']}"),
            ]
        )
        print("Report Sections:", report_sections)
        return {"sections": report_sections.sections}

    def llm_call(self, state: WorkerState) -> dict:
        """Worker writes a section of the report"""
        section_content = self.llm.invoke(
            [
                SystemMessage(
                    content="Write a report section following the provided name and description. Include no preamble for each section. Use markdown formatting."
                ),
                HumanMessage(
                    content=f"Here is the section name: {state['section'].name} and description: {state['section'].description}"
                ),
            ]
        )
        # Ensure we get the content as a string
        content = section_content.content if hasattr(section_content, "content") else str(section_content)
        return {"completed_sections": [content]}

    def synthesizer(self, state: State) -> dict:
        """Synthesize full report from sections"""
        completed_sections = state["completed_sections"]
        completed_report_sections = "\n\n---\n\n".join(completed_sections)
        return {"final_report": completed_report_sections}

    def assign_workers(self, state: State) -> List[Send]:
        """Assign a worker to each section in the plan"""
        return [Send("llm_call", {"section": s}) for s in state["sections"]]