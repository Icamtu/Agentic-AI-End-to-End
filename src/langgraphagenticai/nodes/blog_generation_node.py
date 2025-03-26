# src/langgraphagenticai/nodes/blog_generation_node.py
from src.langgraphagenticai.state.state import State, Section
from pydantic import BaseModel, Field
from typing import List, Dict, Optional
from langchain_core.messages import HumanMessage, SystemMessage, AIMessage
from langchain_core.prompts import ChatPromptTemplate
from src.langgraphagenticai.tools.search_tool import get_tools
import logging
import streamlit as st
import json

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class Sections(BaseModel):
    sections: List[Section] = Field(description="List of sections for the blog report.")

class BlogGenerationNode:
    def __init__(self, model):
        """Initialize the BlogGenerationNode with an LLM."""
        self.planner = model.with_structured_output(Sections)
        self.llm = model
        tools = get_tools(max_results=3)
        self.search_tool = tools[0] if tools else None
        if not self.search_tool:
            logger.warning("No search tool available; web search will be skipped.")
        self.draft_prompt = ChatPromptTemplate.from_messages([
            ("system", "You are a blog writer. Generate a section starting with a markdown heading (##) matching the section name. "
                       "Use the provided description and web search results to guide the content. Use markdown formatting (e.g., paragraphs, lists). "
                       "Focus only on the current section and avoid repeating prior content unless directly relevant. "
                       "Web search results: {search_results}"),
            ("human", "Section name: {name}\nDescription: {description}")
        ])
        self.feedback_prompt = ChatPromptTemplate.from_messages([
            ("system", "Refine the blog sections based on feedback: {feedback}. Keep prior content and adjust as requested."),
            ("placeholder", "{messages}")
        ])

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

    def outline_generator(self, state: State) -> dict:
        """Generate the blog outline based on user requirements (Node B)."""
        logger.info(f"Executing outline_generator with state: {state}")
        topic = state.get("topic", "No topic provided")
        objective = state.get("objective", "Informative")
        target_audience = state.get("target_audience", "General Audience")
        tone_style = state.get("tone_style", "Casual")
        word_count = state.get("word_count", 1000)
        structure = state.get("structure", "Introduction, Main Points, Conclusion")

        structure_list = [s.strip() for s in structure.split(",")]
        section_count = len(structure_list)

        prompt = (
            f"Generate a structured plan for a blog report with exactly {section_count} sections, using clear section headings (e.g., ## Heading). "
            f"Ensure the content is relevant to the topic: {topic}. "
            f"The blog's objective is {objective}, aimed at {target_audience}, with a {tone_style} tone. "
            f"Target a word count of {word_count} words. "
            f"Use this exact structure and section names: {', '.join(structure_list)}. Do not add extra sections or change the names."
            f"\nReturn the result as a JSON object with a 'sections' key, where each section has 'name' and 'description' fields."
        )
        messages = [
            SystemMessage(content=prompt),
            HumanMessage(content=f"Topic: {topic}")
        ]
        logger.info(f"Outline generator input messages: {messages}")
        try:
            logger.info("Invoking LLM for outline generation")
            report_sections = self.planner.invoke(messages)
            logger.info(f"Raw LLM output: {report_sections}")

            # Handle various LLM output formats
            if isinstance(report_sections, list):
                sections = [Section(name=s["name"], description=s["description"]) for s in report_sections]
                report_sections = Sections(sections=sections)
            elif isinstance(report_sections, dict):
                if "sections" in report_sections:
                    sections = [Section(name=s["name"], description=s["description"]) 
                               for s in report_sections["sections"]]
                    report_sections = Sections(sections=sections)
            
            # Create formatted outline text with clear section
            outline = "\n".join([f"- **{s['name']}**: {s['description']}" for s in report_sections.sections])
            outline_message = f"Generated outline:\n{outline}\n\nPlease review the outline above."
            
            # Ensure both sections and messages are properly set in state
            state["messages"].append(AIMessage(content=outline_message))
            state["sections"] = report_sections.sections
            
            # Return both sections and messages in the result
            return {
                "sections": report_sections.sections,
                "messages": state["messages"]
            }

        except Exception as e:
            logger.error(f"LLM invocation failed: {e}")
            state["messages"].append(AIMessage(content=f"Error generating outline: {e}"))
            return {"sections": [], "messages": state["messages"]}

    def outline_review(self, state: State) -> dict:
        """Handle human review of the outline (Outline Review-Human, Node C)."""
        logger.info(f"Executing outline_review with state: {state}")
        feedback = st.session_state.get("outline_feedback", "")
        state["outline_feedback"] = feedback  # Sync feedback from Streamlit state
        logger.info(f"Outline feedback set: {feedback}")
        return {"outline_approved": feedback == "approved", "outline_feedback": feedback}

    def web_search(self, state: State) -> dict:
        """Fetch web search results for each section (Web Search/Scraping, Node I)."""
        logger.info(f"Executing web_search with state: {state}")
        search_results = {}
        if not self.search_tool:
            logger.info("No search tool available; skipping web search.")
            return {"search_results": {s['name']: "No search tool configured." for s in state["sections"]}}
        for section in state["sections"]:
            query = f"{state['topic']} {section['name']}"
            logger.info(f"Searching for: {query}")
            try:
                results = self.search_tool.invoke({"query": query})
                search_results[section['name']] = "\n".join([r.get("content", "") for r in results])
            except Exception as e:
                logger.error(f"Web search failed for {query}: {e}")
                search_results[section['name']] = "No data available due to search error."
        logger.info(f"Search results: {search_results}")
        return {"search_results": search_results}

    def draft_generator(self, state: State) -> dict:
        """Generate the initial draft using search results (Draft Generator-LLM, Node D)."""
        logger.info(f"Executing draft_generator with state: {state}")
        if not state.get("search_results"):
            logger.info("No search results found, triggering web search.")
            return {"needs_facts": True}
        
        completed_sections = []
        final_draft = []
        
        # Format each section with consistent styling
        for section in state["sections"]:
            prompt_inputs = {
                "name": section['name'],
                "description": section['description'],
                "search_results": state["search_results"].get(section['name'], "No data")
            }
            messages = self.draft_prompt.format_messages(**prompt_inputs)
            logger.info(f"Draft prompt messages: {messages}")
            try:
                content = self.llm.invoke(messages).content
                # Ensure consistent section formatting
                section_content = self._format_section_content(section['name'], content)
                completed_sections.append(section_content)
                final_draft.append(section_content)
            except Exception as e:
                logger.error(f"Failed to generate section {section['name']}: {e}")
                error_content = f"## {section['name']}\nError: {e}"
                completed_sections.append(error_content)
                final_draft.append(error_content)
        
        # Join sections with clear separation and formatting
        draft = "\n\n".join(final_draft)
        
        # Create a formatted display version with consistent styling
        display_content = self._format_display_content(draft)
        
        # Update state
        state["completed_sections"] = completed_sections
        state["messages"].append(AIMessage(content=display_content))
        
        logger.info(f"Generated draft with {len(completed_sections)} sections")
        return {
            "completed_sections": completed_sections,
            "draft_content": draft,
            "needs_facts": False
        }

    def _format_section_content(self, section_name: str, content: str) -> str:
        """Format a single section with consistent styling."""
        # Clean up the content
        content = content.strip()
        
        # Ensure section starts with proper heading
        if not content.startswith(f"## {section_name}"):
            content = f"## {section_name}\n\n{content}"
        
        # Format paragraphs with proper spacing
        paragraphs = content.split("\n\n")
        formatted_paragraphs = []
        
        for para in paragraphs:
            # Clean up paragraph
            para = para.strip()
            if para.startswith("#"):  # It's a heading
                formatted_paragraphs.append(para)
            else:  # It's a regular paragraph
                formatted_paragraphs.append(para)
        
        return "\n\n".join(formatted_paragraphs)

    def _format_display_content(self, draft: str) -> str:
        """Format the complete draft for display."""
        return (
            "# Generated Blog Draft\n\n"
            f"{draft}\n\n"
            "---\n\n"
            "Please review the draft with the buttons below."
        )

    def draft_review(self, state: State) -> dict:
        """Handle human review of the draft (Draft Review-Human, Node E)."""
        logger.info(f"Executing draft_review with state: {state}")
        feedback = st.session_state.get("draft_feedback", "")
        state["draft_feedback"] = feedback  # Sync feedback from Streamlit state
        logger.info(f"Draft feedback set: {feedback}")
        if feedback == "approved":
            final_draft = "\n\n---\n\n".join(state["completed_sections"])
            state["messages"].append(AIMessage(content=f"Final approved draft:\n{final_draft}"))
            logger.info(f"Updated state with final draft: {state}")
        return {"draft_approved": feedback == "approved", "feedback": feedback}

    def revision_generator(self, state: State) -> dict:
        """Refine the draft based on human feedback (Revision Generator-LLM, Node F)."""
        logger.info(f"Executing revision_generator with state: {state}")
        feedback = state.get("feedback", "")
        prompt_inputs = {
            "feedback": feedback,
            "messages": state["messages"]
        }
        messages = self.feedback_prompt.format_messages(**prompt_inputs)
        logger.info(f"Feedback prompt messages: {messages}")
        try:
            refined = self.llm.invoke(messages).content.split("\n\n---\n\n")
            draft = "\n\n---\n\n".join(refined)
            state["messages"].append(AIMessage(content=f"Refined draft:\n{draft}\nPlease review again with the buttons below."))
            logger.info(f"Updated state with refined draft: {state}")
            return {"completed_sections": refined, "feedback": feedback}
        except Exception as e:
            logger.error(f"Failed to refine draft: {e}")
            state["messages"].append(AIMessage(content=f"Error refining draft: {e}"))
            return {"completed_sections": state["completed_sections"], "feedback": feedback}