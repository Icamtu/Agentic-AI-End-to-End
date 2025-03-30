import logging
from langgraph.graph import StateGraph, START, END
from langgraph.constants import Send
from src.langgraphagenticai.state.state import State, WorkerState, Sections, Section  # Import from state.py
from langchain_core.messages import SystemMessage, HumanMessage
import streamlit as st
import json


# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class BlogGenerationNode:
    def __init__(self, model):
        """Initialize the BlogGenerationNode with an LLM."""
        self.llm = model
        self.planner = model.with_structured_output(Sections)


    def user_input(self, state: State) -> dict:
        """Handle user input (Node A)."""
        logger.info(f"Executing user_input with state: {state}")
        user_message = state["messages"][-1].content if state["messages"] else ""
        requirements = {}
        for line in user_message.split("\n"):
            if ": " in line:
                key, value = line.split(": ", 1)
                requirements[key.lower().replace(" & ", "_").replace(" ", "_")] = value
        result = {
            "topic": requirements.get("topic", "No topic provided"),
            "objective": requirements.get("objective", "Informative"),
            "target_audience": requirements.get("target_audience", "General Audience"),
            "tone_style": requirements.get("tone_style", "Casual"),
            "word_count": int(requirements.get("word_count", 1000)),
            "structure": requirements.get("structure", "Introduction, Main Points, Conclusion")
        }
        logger.info(f"Parsed requirements: {result}")
        return result


    def orchestrator(self,state: State) -> dict:
        """Orchestrator that generates a plan for the report."""
        logger.info(f"Executing orchestrator with state: {state}")
        structure_list = [s.strip() for s in state["structure"].split(",")]
        section_count = len(structure_list)
        
        prompt = (
            f"Generate a structured plan for a blog report with exactly {section_count} sections. "
            f"Ensure the content is relevant to the topic: {state['topic']}. "
            f"The blog's objective is {state['objective']}, aimed at {state['target_audience']}, "
            f"with a {state['tone_style']} tone. Target a word count of {state['word_count']} words. "
            f"Use this exact structure and section names: {', '.join(structure_list)}. "
            f"Do not add extra sections or change the names."
        )
        report_sections = self.planner.invoke([
            SystemMessage(content=prompt),
            HumanMessage(content=f"Topic: {state['topic']}")
        ])
        logger.info(f"Report Sections: {report_sections}")
        return {"sections": report_sections.sections}

    def llm_call(self,state: WorkerState) -> dict:
        """Worker writes a section of the report."""
        section = self.llm.invoke([
            SystemMessage(content="Write a report section following the provided name and description. Include no preamble for each section. Use markdown formatting."),
            HumanMessage(content=f"Here is the section name: {state['section'].name} and description: {state['section'].description}")
        ])
        return {"completed_sections": [section.content]}

    def synthesizer(self,state: State) -> dict:
        """Synthesize full report from sections."""
        completed_sections = state["completed_sections"]
        final_report = "\n\n---\n\n".join(completed_sections)
        logger.info(f"Synthesized report: {final_report}")
        return {"final_report": final_report}

    def feedback_collector(self, state: State) -> dict:
        """Collect human feedback on the draft."""
        logger.info("Executing feedback_collector")
        
        # Check if we have a new human message with feedback
        if state["messages"] and isinstance(state["messages"][-1], HumanMessage):
            try:
                # Parse the feedback from the human message
                feedback_data = json.loads(state["messages"][-1].content)
                is_approved = feedback_data.get("approved", False)
                comments = feedback_data.get("comments", "")
                
                logger.info(f"Parsed feedback: approved={is_approved}, comments={comments}")
                
                return {
                    "feedback": comments,
                    "draft_approved": is_approved,
                    "blog_content": state.get("final_report", "")  # Keep the content in state
                }
            except json.JSONDecodeError:
                # Not a valid JSON feedback
                logger.warning("Invalid feedback format")
                return {"feedback": "", "draft_approved": False}
        
        # No feedback yet
        return {"feedback": "", "draft_approved": False}
    def revision_generator(self,state: State) -> dict:
        """Revise the report based on human feedback."""
        if state["draft_approved"]:
            return {"final_report": state["final_report"]}  # No revision needed
        
        feedback = state["feedback"]
        completed_sections = state["completed_sections"]
        revised_sections = []
        
        for section in completed_sections:
            revised_content = self.llm.invoke([
                SystemMessage(content=f"Refine this section based on feedback: {feedback}. Keep prior content and adjust as requested. Use markdown formatting."),
                HumanMessage(content=section)
            ])
            revised_sections.append(revised_content.content)
        
        logger.info(f"Revised sections: {revised_sections}")
        return {"completed_sections": revised_sections}

    # Conditional edge function to create llm_call workers
    def assign_workers(self,state: State):
        """Assign a worker to each section in the plan."""
        return [Send("llm_call", {"section": s}) for s in state["sections"]]

    # Conditional edge for feedback loop
    def route_feedback(self,state: State):
        """Route based on whether draft is approved."""
        if state["draft_approved"]:
            return END
        return "revision_generator"
