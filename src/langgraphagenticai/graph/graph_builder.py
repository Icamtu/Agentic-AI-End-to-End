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

logging.basicConfig(
    level=logging.INFO,  # Set the minimum log level to INFO
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s\n'  # Format for log messages
)
logger = logging.getLogger(__name__)



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
        Builds a graph for the Blog Generation use case.
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
            graph_builder.add_node("file_generator", blog_node.file_generator) # Changed node name

            # Add edges
            graph_builder.set_entry_point("user_input") # Changed from START
            graph_builder.add_edge("user_input", "orchestrator")
            graph_builder.add_conditional_edges("orchestrator", lambda state: blog_node.assign_workers(state), ["llm_call"])
            graph_builder.add_edge("llm_call", "synthesizer")
            graph_builder.add_edge("synthesizer", "feedback_collector")
            graph_builder.add_conditional_edges(
                "feedback_collector",
                blog_node.route_feedback,  # Use instance method
                {
                    "orchestrator": "orchestrator",
                    "file_generator": "file_generator" 
                }
            )
            

            
            graph_builder.add_edge("file_generator", END)

            # Compile with interrupts after synthesizer to allow feedback collection
            # In your initialization code
            compiled_graph = graph_builder.compile(
                interrupt_after=["synthesizer"],  # Interrupt after synthesizer instead of feedback_collector
                checkpointer=self.memory
            )
            logger.info("Compiled graph edges: %s", compiled_graph.get_graph().edges)
            return compiled_graph
        except Exception as e:
            print(f"{e}")

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
