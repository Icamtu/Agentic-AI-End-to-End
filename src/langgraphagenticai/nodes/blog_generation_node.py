# src/langgraphagenticai/nodes/blog_generation_node.py
from src.langgraphagenticai.state.state import State, WorkerState, Section
from pydantic import BaseModel, Field
from typing import List
from langgraph.constants import Send
from langchain_core.messages import HumanMessage, SystemMessage, AIMessage
from langchain_core.prompts import ChatPromptTemplate

class Sections(BaseModel):
    sections: List[Section] = Field(description="List of sections for the blog report.")

class BlogGenerationNode:
    def __init__(self, model):
        """Initialize the BlogGenerationNode with an LLM."""
        self.planner = model.with_structured_output(Sections)
        self.llm = model
        self.section_prompt = ChatPromptTemplate.from_messages([
            ("system", "You are a blog writer. Generate a section starting with a markdown heading (##) matching the section name. "
                       "Use the provided description to guide the content. Use markdown formatting (e.g., paragraphs, lists). "
                       "Focus only on the current section and avoid repeating prior content unless directly relevant."),
            ("human", "Section name: {name}\nDescription: {description}")
        ])

    def orchestrator(self, state: State) -> dict:
        """Generate a structured plan for the blog report based on the topic."""
        # Use the last message as the topic if 'topic' isn't set
        topic = state.get("topic", state["messages"][-1].content if state["messages"] else "No topic provided")
        
        report_sections = self.planner.invoke(
            [
                SystemMessage(content="Generate a structured plan for a blog report with clear section headings (e.g., ## Heading). "
                                      f"Ensure the content is relevant to the topic: {topic}."),
                HumanMessage(content=f"Topic: {topic}")
            ]
        )

        print("Generated Sections:", report_sections)
        return {
            "sections": report_sections.sections,
            "topic": topic  # Ensure topic is set in state for consistency
        }

    def llm_call(self, state: WorkerState) -> dict:
        """Generate a structured section of the report with markdown formatting."""
        section = state["section"]

        section_content = self.llm.invoke(
            self.section_prompt.format_prompt(
                name=section.name,
                description=section.description
            ).to_messages()
        )

        content = section_content.content if hasattr(section_content, "content") else str(section_content)
        if not content.startswith(f"## {section.name}"):
            content = f"## {section.name}\n{content.strip()}"

        return {"completed_sections": [content]}

    def synthesizer(self, state: State) -> dict:
        """Combine completed sections into a structured final report and add to messages."""
        completed_sections = state["completed_sections"]
        if not completed_sections:
            final_report = "## No Content Generated\nNo sections were generated."
        else:
            final_report = "\n\n---\n\n".join(section.strip() for section in completed_sections if section.strip())

        # Add the final report to the chat history as an AIMessage
        state["messages"].append(AIMessage(content=final_report))
        return {"final_report": final_report}

    def assign_workers(self, state: State) -> List[Send]:
        """Assign workers to generate each section."""
        if not state.get("sections"):
            print("No sections to assign.")
            return []
        return [
            Send("llm_call", {"section": s})
            for s in state["sections"]
        ]