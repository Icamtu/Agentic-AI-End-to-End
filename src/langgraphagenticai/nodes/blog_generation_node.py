# blog_generation_node.py
from src.langgraphagenticai.state.state import State, WorkerState, Section
from src.langgraphagenticai.tools.search_tool import get_tools
from pydantic import BaseModel, Field
from typing import List, Dict
from langgraph.constants import Send
from langchain_core.messages import HumanMessage, SystemMessage
from datetime import date

class Sections(BaseModel):
    sections: List[Section] = Field(description="List of sections for the blog report.")

class BlogGenerationNode:
    def __init__(self, model):
        """Initialize the BlogGenerationNode with an LLM and search tool."""
        self.planner = model.with_structured_output(Sections)
        self.llm = model
        self.tools = get_tools()
        self.search_tool = self.tools[0]

    def orchestrator(self, state: State) -> dict:
        """Generate a structured plan for the blog report and fetch verified updates."""
        topic = state["topic"]
        search_query = f"recent advancements and updates on {topic} site:*.edu | site:*.org | site:*.gov -inurl:(signup | login)"

        search_context, search_references = self.perform_search(search_query)

        report_sections = self.planner.invoke(
            [
                SystemMessage(content="Generate a structured plan for a blog report with clear section headings (e.g., ## Heading), incorporating verified recent updates if available."),
                HumanMessage(content=f"Topic: {topic}\nRecent verified updates:\n{search_context}"),
            ]
        )

        print("Generated Sections:", report_sections)
        return {
            "sections": report_sections.sections,
            "search_context": search_context,
            "search_references": search_references
        }

    def perform_search(self, query: str) -> tuple[str, Dict[str, str]]:
        """Perform a search and return verified results with content and valid URLs."""
        try:
            search_results = self.search_tool.invoke(query)
            if not search_results:
                raise ValueError("No valid search results returned.")
        except Exception as e:
            print(f"Search failed: {e}")
            return "No verified updates available.", {}

        # Filter for results with content and valid URLs
        filtered_results = [
            result for result in search_results 
            if "content" in result and result.get("url") and isinstance(result["content"], str) and len(result["content"]) > 20 and result["url"] != "No URL"
        ]

        if not filtered_results:
            print("No substantial search results with valid URLs found.")
            return "No verified updates with sufficient detail available.", {}

        search_context = "\n".join(result["content"] for result in filtered_results)
        search_references = {result["content"]: result["url"] for result in filtered_results}
        print("Search Context:", search_context)
        return search_context, search_references

    def remove_hallucination(self, generated_content: str, search_context: str, search_references: dict) -> tuple[str, List[str]]:
        """Remove unverified content and append only valid reference links, preserving structure."""
        content_lines = generated_content.split("\n")
        filtered_lines = []
        reference_links = set()
        in_references = False

        # Split search context into sentences for broader matching
        search_sentences = [s.strip() for s in search_context.split(".") if s.strip()]

        for line in content_lines:
            if line.strip().startswith("**References:**"):
                in_references = True
                continue
            if in_references:
                continue

            if not line.strip():
                filtered_lines.append(line)
                continue

            # Preserve headings
            if line.startswith("#"):
                filtered_lines.append(line)
                continue

            # Lenient verification: include only verified content
            verified = any(
                any(word.lower() in line.lower() for word in sentence.split() if len(word) > 3)
                for sentence in search_sentences
            )
            if verified:
                filtered_lines.append(line)
                for context, url in search_references.items():
                    if any(word.lower() in line.lower() for word in context.split() if len(word) > 3):
                        # Only add valid URLs (non-empty and not "No URL")
                        if url and url != "No URL" and url.startswith(("http://", "https://")):
                            reference_links.add(url)

        filtered_content = "\n".join(filtered_lines)
        if reference_links:
            filtered_content += "\n\n**References:**\n" + "\n".join([f"- [{url}]({url})" for url in reference_links])

        return filtered_content, list(reference_links)

    def llm_call(self, state: WorkerState) -> dict:
        """Generate a structured section of the report with markdown formatting."""
        section = state["section"]
        search_context = state.get("search_context", "")

        section_content = self.llm.invoke(
            [
                SystemMessage(
                    content="Generate a blog section starting with a markdown heading (##) matching the section name, followed by concise content strictly based on verified recent updates if provided. Use markdown formatting (e.g., paragraphs, lists). Avoid speculative or unverified claims."
                ),
                HumanMessage(
                    content=f"Section name: {section.name}\nDescription: {section.description}\nRecent verified updates: {search_context}"
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
            return {"final_report": "## No Content Generated\nNo sections were generated due to lack of verifiable data."}
        final_report = "\n\n---\n\n".join(section.strip() for section in completed_sections if section.strip())
        return {"final_report": final_report}

    def hallucination_checker(self, state: State) -> dict:
        """Check and remove hallucinations from the final report while preserving structure."""
        final_report = state["final_report"]
        search_context = state.get("search_context", "")
        search_references = state.get("search_references", {})

        if not final_report.strip():
            return {"final_report": "## No Content to Verify\nNo content was provided for verification."}

        sections = final_report.split("\n\n---\n\n")
        filtered_sections = []

        for section in sections:
            if section.strip():
                filtered_content, _ = self.remove_hallucination(section, search_context, search_references)
                if filtered_content.strip():  # Only include non-empty sections
                    filtered_sections.append(filtered_content)

        updated_report = "\n\n---\n\n".join(filtered_sections)
        if not updated_report.strip():
            updated_report = "## No Verified Content\nAll generated content lacked verification against available updates."
        return {"final_report": updated_report}

    def assign_workers(self, state: State) -> List[Send]:
        """Assign workers to generate each section."""
        search_context = state.get("search_context", "")
        search_references = state.get("search_references", {})
        return [
            Send("llm_call", {"section": s, "search_context": search_context, "search_references": search_references})
            for s in state["sections"]
        ]