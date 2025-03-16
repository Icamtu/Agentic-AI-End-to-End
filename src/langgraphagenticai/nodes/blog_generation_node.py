# blog_generation_node.py
from src.langgraphagenticai.state.state import State, WorkerState, Section
from pydantic import BaseModel, Field
from typing import List
from langgraph.constants import Send
from langchain_core.messages import HumanMessage, SystemMessage

class Sections(BaseModel):
    sections: List[Section] = Field(description="List of sections for the blog report.")

class BlogGenerationNode:
    def __init__(self, model):
        """Initialize the BlogGenerationNode with an LLM."""
        self.planner = model.with_structured_output(Sections)
        self.llm = model

    def orchestrator(self, state: State) -> dict:
        """Generate a structured plan for the blog report."""
        topic = state["topic"]

        report_sections = self.planner.invoke(
            [
                SystemMessage(content=f"Generate a structured plan for a blog report with clear section headings (e.g., ## Heading). "
                                      f"Ensure the content is relevant to the topic: {topic}."),
                HumanMessage(content=f"Topic: {topic}")
            ]
        )

        print("Generated Sections:", report_sections)
        return {
            "sections": report_sections.sections
        }

    def llm_call(self, state: WorkerState) -> dict:
        """Generate a structured section of the report with markdown formatting."""
        section = state["section"]

        section_content = self.llm.invoke(
            [
                SystemMessage(
                    content="Generate a blog section starting with a markdown heading (##) matching the section name. "
                            "Use markdown formatting (e.g., paragraphs, lists). Avoid speculative claims."
                ),
                HumanMessage(
                    content=f"Section name: {section.name}\nDescription: {section.description}"
                ),
            ]
        )

        content = section_content.content if hasattr(section_content, "content") else str(section_content)
        if not content.startswith(f"## {section.name}"):
            content = f"## {section.name}\n{content.strip()}"

        return {"completed_sections": [content]}

    def synthesizer(self, state: State) -> dict:
        """Combine completed sections into a structured final report."""
        completed_sections = state["completed_sections"]
        if not completed_sections:
            return {"final_report": "## No Content Generated\nNo sections were generated."}

        final_report = "\n\n---\n\n".join(section.strip() for section in completed_sections if section.strip())
        return {"final_report": final_report}

    def assign_workers(self, state: State) -> List[Send]:
        """Assign workers to generate each section."""
        return [
            Send("llm_call", {"section": s})
            for s in state["sections"]
        ]
