# src/langgraphagenticai/nodes/code_reviewer_node.py
from src.langgraphagenticai.state.state import State
from langchain_core.messages import HumanMessage, SystemMessage, AIMessage
from langchain_core.prompts import ChatPromptTemplate
import logging

# Configure basic logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class CodeReviewerNode:
    def __init__(self, model):
        """Initialize the CodeReviewerNode with a LangChain LLM model.

        Args:
            model: A LangChain LLM instance capable of generating text responses.
        """
        self.llm = model
        # Prompt for structured feedback and corrected code
        self.review_prompt = ChatPromptTemplate.from_messages([
            ("system", "You are an expert code reviewer. Review the provided code and provide concise, actionable feedback in markdown format. "
                       "Use headings (e.g., ## Strengths, ## Issues) and bullet points where applicable. "
                       "Focus on the code itself and avoid speculative comments. "
                       "Then, provide a corrected version of the code in a markdown code block (```python\n...\n```). "
                       "If no corrections are needed, restate the original code with a note. "
                       "Assume the code is in Python unless otherwise specified."),
            ("human", "Review this code:\n```python\n{code}\n```")
        ])

    def review_code(self, state: State) -> dict:
        """Review the provided code, provide feedback, and return a corrected version, integrating with chat history.

        Args:
            state (State): The current state containing 'messages' (list of messages) and optionally 'code_input' (str).

        Returns:
            dict: A dictionary with 'review_output' (feedback), 'corrected_code' (corrected version), and 'output' (combined).
        """
        # Safely get code input, with fallback to last message or empty string
        code = state.get("code_input", state["messages"][-1].content if state.get("messages", []) else "")
        
        # Validate input
        if not code.strip():
            feedback = "## No Code Provided\nPlease provide code to review."
            corrected_code = ""
            combined_output = feedback
        else:
            # Generate review and corrected code with structured prompt
            review = self.llm.invoke(
                self.review_prompt.format_prompt(code=code).to_messages()
            )
            review_content = review.content if hasattr(review, "content") else str(review)
            
            # Ensure markdown formatting for feedback
            if not review_content.startswith("##"):
                logger.warning("LLM did not return markdown-formatted review; adding default heading.")
                review_content = f"## Code Review Feedback\n{review_content}"

            # Extract feedback and corrected code (assuming LLM follows prompt structure)
            # Split on the last occurrence of a code block to separate feedback from corrected code
            if "```python" in review_content:
                feedback, corrected_part = review_content.rsplit("```python", 1)
                corrected_code = f"```python{corrected_part.strip()}".rstrip("```") + "\n```"
                feedback = feedback.strip()
            else:
                feedback = review_content
                corrected_code = f"```python\n{code.strip()}\n```\n## Note\nNo corrections needed."
            
            # Combine for chat history
            combined_output = f"{feedback}\n\n## Corrected Code\n{corrected_code}"

        # Append combined output to chat history as an AIMessage
        state["messages"].append(AIMessage(content=combined_output))
        
        return {
            "review_output": feedback,        # Feedback text
            "corrected_code": corrected_code, # Corrected code block
            "output": combined_output         # Combined for compatibility
        }