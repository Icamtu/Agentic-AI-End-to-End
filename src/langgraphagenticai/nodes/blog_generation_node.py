import logging
from langgraph.graph import StateGraph, START, END
from langgraph.constants import Send
from src.langgraphagenticai.state.state import State, WorkerState, Sections, Section  # Import from state.py
from langchain_core.messages import SystemMessage, HumanMessage
import streamlit as st
import json
from datetime import datetime
from typing import List


logging.basicConfig(
    level=logging.INFO,  # Set the minimum log level to INFO
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s\n'  # Format for log messages
)

logger = logging.getLogger(__name__)

class BlogGenerationNode:
    def __init__(self, model):
        """Initialize the BlogGenerationNode with an LLM."""
        self.llm = model
        self.planner = model.with_structured_output(Sections)

    def validate_and_standardize_structure(self, user_input: str) -> List[str]:
        """
        Uses an LLM to interpret user input and generate a standardized list of blog section names.
        Ensures the user's specified structure is respected if provided.

        Args:
            user_input (str): The full user input from the Streamlit form (e.g., "Topic: AI\nStructure: Intro, Benefits, Summary").

        Returns:
            List[str]: A list of standardized section names (e.g., ["Intro", "Benefits", "Summary"]).
        """
        # Default structure if all else fails
        default_structure = ["Introduction", "Main Content", "Conclusion"]

        # If input is empty or whitespace-only, return default
        if not user_input or not user_input.strip():
            logger.info("Empty or whitespace-only input; returning default structure")
            return default_structure

        # Extract the user's structure if provided
        user_structure = None
        for line in user_input.split("\n"):
            if line.lower().startswith("structure:"):
                user_structure = line.split(":", 1)[1].strip()
                break

        if not user_structure:
            logger.info("No structure provided; returning default structure")
            return default_structure

        # Define the prompt for the LLM
        system_prompt = (
            "You are an expert blog planner. Your task is to analyze the user's input and extract or infer a clear, concise structure "
            "for a blog post as a list of section names. The input may explicitly list sections (e.g., 'Structure: Intro, Benefits, Summary') "
            "or describe them implicitly (e.g., 'I want an intro, some benefits, and a conclusion'). "
            "If the user provides a 'Structure' field (e.g., 'Structure: Intro, Benefits, Summary'), you MUST use those exact section names "
            "without modification, except for capitalizing the first letter of each section. "
            "If no structure is provided or it's unclear, propose a logical default structure based on the topic or context. "
            "Return the result as a JSON object with a single key 'sections' containing the list of section names. "
            "Capitalize each section name and avoid adding unnecessary sections beyond what’s indicated."
        )

        # Prepare messages for the LLM
        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=f"User input: {user_input}")
        ]

        try:
            # Invoke the LLM and expect a JSON response
            response = self.llm.invoke(messages)
            response_content = response.content if hasattr(response, "content") else str(response)
            logger.info(f"LLM response for structure: {response_content}")

            # Parse the JSON response
            result = json.loads(response_content)
            sections = result.get("sections", default_structure)

            # Validate and standardize the output
            if not isinstance(sections, list) or not sections:
                logger.warning("LLM returned invalid sections; using default structure")
                return default_structure

            # Clean up section names: strip whitespace, capitalize, remove empty strings
            cleaned_sections = [s.strip().capitalize() for s in sections if s.strip()]

            # If user provided a structure, enforce it
            if user_structure:
                user_sections = [s.strip().capitalize() for s in user_structure.split(",") if s.strip()]
                if len(cleaned_sections) == len(user_sections):
                    # Override LLM sections with user sections if lengths match
                    cleaned_sections = user_sections
                else:
                    logger.warning(f"LLM section count ({len(cleaned_sections)}) doesn't match user section count ({len(user_sections)}); using user structure")
                    cleaned_sections = user_sections

            return cleaned_sections if cleaned_sections else default_structure

        except Exception as e:
            logger.error(f"Error in LLM structure generation: {e}")
            return default_structure

    def user_input(self, state: State) -> dict:
        """Handle user input."""
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
            "structure": requirements.get("structure", "Introduction, Main Points, Conclusion"),
            "feedback": state.get("feedback", "No feedback provided yet.") # Initialize feedback here
        }

        # Update the state with the standardized structure
        standardized_structure = self.validate_and_standardize_structure(user_message)
        result["structure"] = ", ".join(standardized_structure)

        logger.info(f"Parsed requirements: {result}")
        return result

    def orchestrator(self, state: State) -> dict:
        """Orchestrator that generates a plan for the report."""
        logger.info(f"Executing orchestrator with state: {state}")
        logger.info(f"\n{'='*20}:Current feedback in orchestrator state:{'='*20}\n{'='*20}{state.get('feedback')}{'='*20}\n")
        structure_list = [s.strip() for s in state["structure"].split(",")]
        section_count = len(structure_list)

        prompt = (
            f"Create a detailed and structured plan for a blog report consisting of exactly {section_count} sections. "
            f"The content should be directly relevant to the topic: '{state['topic']}'. "
            f"The primary objective of the blog is to {state['objective']}, targeting an audience of {state['target_audience']}. "
            f"Please maintain a {state['tone_style']} tone throughout the writing. "
            f"Aim for a total word count of approximately {state['word_count']} words. "
            f"Follow this specific structure and section names: {', '.join(structure_list)}. "
            f"Incorporate {state['feedback']} to enhance the quality of the content. "
            f"Please refrain from adding any extra sections or altering the section names unless {state['feedback']} is provided."
        )

        feedback = state.get("feedback", "No feedback provided yet.")
        report_sections = self.planner.invoke([
            SystemMessage(content=prompt),
            HumanMessage(content=f"Topic: {state['topic']} with feedback {feedback}")
        ])
        logger.info(f"Report Sections: {report_sections}")
        return {"sections": report_sections.sections}

    def llm_call(self, state: WorkerState) -> dict:
        """Worker writes a section of the report."""
        section = self.llm.invoke([
            SystemMessage(content="Write a report section following the provided name and description. Include no preamble for each section. Use markdown formatting."),
            HumanMessage(content=f"Here is the section name: {state['section'].name} and description: {state['section'].description}")
        ])
        return {"completed_sections": [section.content]}

    def synthesizer(self, state: State) -> dict:
        """Synthesize full report from sections."""
        completed_sections = state["completed_sections"]
        initial_draft = "\n\n---\n\n".join(completed_sections)
        logger.info(f"Synthesized report: {initial_draft}")
        return {"initial_draft": initial_draft}

    def feedback_collector(self, state: State) -> dict:
        logger.info(f"\n\n----------------:Entered feedback_collector with state:----------------------\n\n{state}")
        logger.info(f"Message count: {len(state.get('messages', []))}")
        logger.info(f"Last message type: {type(state['messages'][-1]) if state.get('messages') else 'None'}")
        
        if state.get("messages") and len(state["messages"]) > 0 and isinstance(state["messages"][-1], HumanMessage):
            try:
                feedback_data = json.loads(state["messages"][-1].content)
                is_approved = feedback_data.get("approved", False)
                comments = feedback_data.get("comments", "")
                logger.info(f"Parsed feedback: approved={is_approved}, comments={comments}")

                if is_approved:
                    logger.info("Content approved, preparing final report")
                    final_report = state.get("initial_draft", "")
                    collector_output = {
                        "feedback": comments,
                        "draft_approved": True,
                        "final_report": final_report
                    }
                else:
                    collector_output = {
                        "feedback": comments,
                        "draft_approved": False,
                        "final_report": ""
                    }
                logger.info(f"{'='*20}:feedback_collector output:{'='*20}\n{collector_output}") # Add this log
                return collector_output

            except json.JSONDecodeError:
                logger.warning("Invalid feedback format; returning default values")
                return {"feedback": "", "draft_approved": False, "final_report": ""}

        logger.info("No new feedback message found; returning default values")
        return {"feedback": "", "draft_approved": False, "final_report": ""}

    def file_generator(self, state: State) -> dict:
        """Generates the final report and ends the process."""
        final_report = state["final_report"]
        # In a real scenario, you would save this to a file
        logger.info(f"Final Report Generated:\n{final_report}")
        return {"final_report_path": "report.md"} # Simulate saving to a file

    # Conditional edge function to create llm_call workers
    def assign_workers(self, state: State):
        """Assign a worker to each section in the plan."""
        return [Send("llm_call", {"section": s}) for s in state["sections"]]

    # Conditional edge for feedback loop
    def route_feedback(self, state: State):
        """Route based on whether draft is approved."""
        draft_approved = state.get('draft_approved', False)
        logger.info(f"route_feedback: draft_approved = {draft_approved}")
        
        if draft_approved is True:  # Strict comparison
            logger.info("Draft approved; routing to file_generator")
            return "file_generator"
        else:
            logger.info("Draft not approved; routing back to orchestrator for revision")
            return "orchestrator"
