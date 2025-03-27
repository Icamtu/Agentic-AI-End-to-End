# src/langgraphagenticai/graph/graph_builder.py
from langgraph.graph import StateGraph, START, END
from src.langgraphagenticai.nodes.blog_generation_node import BlogGenerationNode
from src.langgraphagenticai.nodes.basic_chatbot_node import BasicChatbotNode
from src.langgraphagenticai.nodes.chatbot_with_Tool_node import ChatbotWithToolNode
from src.langgraphagenticai.tools.search_tool import get_tools, create_tool_nodes
from langgraph.prebuilt import tools_condition, ToolNode
from src.langgraphagenticai.state.state import State
from langgraph.checkpoint.memory import MemorySaver
from pydantic import BaseModel, Field
from langchain_core.messages import SystemMessage, HumanMessage
import logging
import json

logger = logging.getLogger(__name__)

class ReviewFeedback(BaseModel):
    approved: bool = Field(description="Approval status: True for approved, False for rejected")
    comments: str = Field(description="Reviewer comments")

class GraphBuilder:
    def __init__(self, llm):
        self.llm = llm
        self.memory = MemorySaver()

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

    def basic_chatbot_build_graph(self):
        """
        Builds a graph for the Basic Chatbot use case.
        """
        graph_builder = StateGraph(state_schema=State)
        basic_chatbot_node = BasicChatbotNode(self.llm)
        graph_builder.add_node("chatbot", basic_chatbot_node.create_chatbot())
        graph_builder.add_edge(START, "chatbot")
        graph_builder.add_edge("chatbot", END)
        return graph_builder.compile(checkpointer=self.memory)

    def chatbot_with_tool_build_graph(self):
        """
        Builds a graph for the Chatbot with Tool use case.
        """
        graph_builder = StateGraph(state_schema=State)
        
        # Define the tool and tool node
        tools = get_tools()
        tool_node = create_tool_nodes(tools)

        # Define chatbot node
        chatbot_with_tool_node = ChatbotWithToolNode(self.llm)
        chatbot_node = chatbot_with_tool_node.create_chatbot(tools)

        graph_builder.add_node("chatbot", chatbot_node)
        graph_builder.add_node("tools", tool_node)
        
        graph_builder.add_edge(START, "chatbot")
        graph_builder.add_conditional_edges("chatbot", tools_condition)
        graph_builder.add_edge("tools", "chatbot")
        return graph_builder.compile(checkpointer=self.memory)

    def blog_generation_build_graph(self):
        """
        Builds a graph for the Blog Generation use case with button-based feedback and LLM-driven structure generation.
        """
        try:
            if not self.llm:
                raise ValueError("LLM model not initialized")

            graph_builder = StateGraph(state_schema=State)
            blog_node = BlogGenerationNode(self.llm)
            
            # Modify user_input node to use LLM for structure
            def user_input_with_validation(state: State) -> dict:
                user_message = state["messages"][-1].content if state["messages"] else ""
                result = blog_node.user_input(state)  # Initial parsing
                # Use LLM to interpret full user input for structure
                full_input = user_message  # Use raw message for maximum context
                result["structure"] = ", ".join(self.validate_and_standardize_structure(full_input))
                logger.info(f"Validated structure: {result['structure']}")
                return result

            # Add nodes with validated user input
            graph_builder.add_node("user_input", user_input_with_validation)
            graph_builder.add_node("outline_generator", blog_node.outline_generator)
            graph_builder.add_node("outline_review", blog_node.outline_review)
            graph_builder.add_node("draft_generator", blog_node.draft_generator)
            graph_builder.add_node("draft_review", blog_node.draft_review)
            graph_builder.add_node("web_search", blog_node.web_search)
            graph_builder.add_node("revision_generator", blog_node.revision_generator)

            # Define edges
            graph_builder.add_edge(START, "user_input")
            graph_builder.add_edge("user_input", "outline_generator")
            graph_builder.add_edge("outline_generator", "outline_review")
            
            # Conditional edge for outline review based on button feedback
            def determine_outline_review(state):
                if not state:
                    logger.error("Invalid state provided")
                    return "outline_review"
                feedback = state.get("outline_feedback", "")
                if not feedback:  # No feedback yet, stay at review
                    return "outline_review"
                return "draft_generator" if feedback == "approved" else "outline_generator"

            graph_builder.add_conditional_edges(
                "outline_review",
                determine_outline_review,
                {"outline_review": "outline_review", "outline_generator": "outline_generator", "draft_generator": "draft_generator"}
            )

            # Draft generator conditional edge for web search
            graph_builder.add_conditional_edges(
                "draft_generator",
                lambda state: "web_search" if state.get("needs_facts", False) else "draft_review",
                {"web_search": "web_search", "draft_review": "draft_review"}
            )
            graph_builder.add_edge("web_search", "draft_generator")
            
            # Conditional edge for draft review based on button feedback
            def determine_draft_review(state):
                if not state:
                    logger.error("Invalid state provided")
                    return "draft_review"
                feedback = state.get("draft_feedback", "")
                if not feedback:  # No feedback yet, stay at review
                    return "draft_review"
                return END if feedback == "approved" else "revision_generator"

            graph_builder.add_conditional_edges(
                "draft_review",
                determine_draft_review,
                {"draft_review": "draft_review", "revision_generator": "revision_generator", END: END}
            )
            graph_builder.add_edge("revision_generator", "draft_review")

            # Compile with interrupts at review nodes
            return graph_builder.compile(interrupt_before=["outline_review", "draft_review"], checkpointer=self.memory)
        except Exception as e:
            logger.error(f"Error building blog generation graph: {e}")
            return None

    def setup_graph(self, usecase):
        """
        Sets up the appropriate graph based on the selected use case.
        """
        if usecase == "Basic Chatbot":
            return self.basic_chatbot_build_graph()
        elif usecase == "Chatbot with Tool":
            return self.chatbot_with_tool_build_graph()
        elif usecase == "Blog Generation":
            return self.blog_generation_build_graph()
        else:
            raise ValueError(f"Unknown use case: {usecase}")