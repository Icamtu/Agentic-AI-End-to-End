# src/langgraphagenticai/graph/graph_builder_blog.py
from langgraph.graph import StateGraph, START, END
from src.langgraphagenticai.nodes.blog_generation_node import BlogGenerationNode
from src.langgraphagenticai.state.state import BlogState as State
from langgraph.checkpoint.memory import MemorySaver
from pydantic import BaseModel, Field
from langchain_core.messages import SystemMessage, HumanMessage
import logging
import json
import logging
import functools
import time


logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(), # Logs to console
        # logging.FileHandler("app.log") # Optional: Logs to a file
    ]
)

logger = logging.getLogger(__name__)

def log_entry_exit(func):
    """
    A decorator that logs the entry and exit of a function.
    It also logs the execution time.
    """
    @functools.wraps(func) # Preserves function metadata (like __name__, __doc__)
    def wrapper(*args, **kwargs):
        func_name = func.__name__
        logger.info(f"\n{'='*20}\n:Entering: {func_name}\n{'='*20}\n")
        start_time = time.perf_counter() # More precise than time.time()
        try:
            result = func(*args, **kwargs)
            end_time = time.perf_counter()
            execution_time = end_time - start_time
            logger.info(f"\n{'='*20}\n:Exiting: {func_name} (Execution Time: {execution_time:.4f} seconds)\n{'='*20}\n")
            return result
        except Exception as e:
            end_time = time.perf_counter()
            execution_time = end_time - start_time
            logger.error(f"{'='*20}:Error Exception in {func_name}: {e} (Execution Time: {execution_time:.4f} seconds)", exc_info=True)
            # Re-raise the exception after logging
            raise
    return wrapper

logging.basicConfig(
    level=logging.INFO,  # Set the minimum log level to INFO
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s\n'  # Format for log messages
)
logger = logging.getLogger(__name__)

class ReviewFeedback(BaseModel):
    approved: bool = Field(description="Approval status: True for approved, False for rejected")
    comments: str = Field(description="Reviewer comments")

class BlogGraphBuilder:
    def __init__(self, llm, memory: MemorySaver=None):
        self.llm = llm
        self.memory = memory if memory is not None else MemorySaver()
        
    @log_entry_exit
    def validate_and_standardize_structure(self, user_input: str) -> list:
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

    @log_entry_exit
    def build_graph(self):
        """
        Builds a graph for the Blog Generation use case.
        Focuses on reliable checkpointing by adjusting interrupt timing.
        """
        try:
            if not self.llm:
                raise ValueError("LLM model not initialized")

            graph_builder = StateGraph(state_schema=State)
            blog_node = BlogGenerationNode(self.llm)

            # Add nodes
            graph_builder.add_node("user_input", blog_node.user_input)
            graph_builder.add_node("orchestrator", blog_node.orchestrator)
            graph_builder.add_node("llm_call", blog_node.llm_call)
            graph_builder.add_node("synthesizer", blog_node.synthesizer)
            graph_builder.add_node("feedback_collector", blog_node.feedback_collector)
            graph_builder.add_node("file_generator", blog_node.file_generator)
            

            # Add edges
            graph_builder.add_edge(START,"user_input")
            graph_builder.add_edge("user_input", "orchestrator")
            graph_builder.add_conditional_edges("orchestrator", lambda state: blog_node.assign_workers(state), ["llm_call"])
            graph_builder.add_edge("llm_call", "synthesizer")
            graph_builder.add_edge("synthesizer", "feedback_collector")

            # Restore original conditional edges for feedback
            graph_builder.add_conditional_edges(
                "feedback_collector",
                blog_node.route_feedback,
                {
                    # If revision needed, go directly back to orchestrator
                    "orchestrator": "orchestrator", # Restored from "reset_sections"
                    "file_generator": "file_generator"
                }
            )

     

            graph_builder.add_edge("file_generator", END)

          
            return graph_builder.compile(interrupt_before=["feedback_collector"], checkpointer=self.memory) # Changed from interrupt_after
        except Exception as e:
            logger.error(f"Error building graph: {e}")
            raise