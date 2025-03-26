# src/langgraphagenticai/graph/graph_builder.py
from langgraph.graph import StateGraph, START, END
from src.langgraphagenticai.nodes.blog_generation_node import BlogGenerationNode
from src.langgraphagenticai.nodes.basic_chatbot_node import BasicChatbotNode
from src.langgraphagenticai.nodes.chatbot_with_Tool_node import ChatbotWithToolNode
from src.langgraphagenticai.tools.search_tool import get_tools, create_tool_nodes
from langgraph.prebuilt import tools_condition,ToolNode
from src.langgraphagenticai.state.state import State
from langgraph.checkpoint.memory import MemorySaver
from pydantic import BaseModel, Field
import logging

logger = logging.getLogger(__name__)

class ReviewFeedback(BaseModel):
    approved: bool = Field(description="Approval status: True for approved, False for rejected")
    comments: str = Field(description="Reviewer comments")

class GraphBuilder:
    def __init__(self, llm):
        self.llm = llm
        self.memory = MemorySaver()

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
        
         ## Define the tool and tool node

        tools=get_tools()
        tool_node=create_tool_nodes(tools)

        # Define chatbot node
        chatbot_with_tool_node = ChatbotWithToolNode(self.llm)
        chatbot_node = chatbot_with_tool_node.create_chatbot(tools)

        graph_builder.add_node("chatbot", chatbot_node)
        graph_builder.add_node("tools", tool_node)
        
        graph_builder.add_edge(START, "chatbot")
        graph_builder.add_conditional_edges("chatbot",tools_condition,)
        graph_builder.add_edge("tools", "chatbot")
        return graph_builder.compile(checkpointer=self.memory)

    def blog_generation_build_graph(self):
        """
        Builds a graph for the Blog Generation use case with button-based feedback.
        """
        try:
            if not self.llm:
                raise ValueError("LLM model not initialized")

            # Add structure validation helper
            def validate_and_standardize_structure(structure: str) -> list:
                if not structure or structure.strip() == "":
                    return ["Introduction", "Main Content", "Conclusion"]
                sections = [s.strip().capitalize() for s in structure.split(",")]
                if len(sections) < 1:
                    return ["Introduction", "Main Content", "Conclusion"]
                return sections

            graph_builder = StateGraph(state_schema=State)
            blog_node = BlogGenerationNode(self.llm)
            
            # Modify user_input node to include structure validation
            def user_input_with_validation(state: State) -> dict:
                result = blog_node.user_input(state)
                raw_structure = result.get("structure", "")
                result["structure"] = ", ".join(validate_and_standardize_structure(raw_structure))
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