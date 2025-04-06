# src/langgraphagenticai/graph/graph_builder_tool.py
from langgraph.graph import StateGraph, START, END
from src.langgraphagenticai.nodes.chatbot_with_Tool_node import ChatbotWithToolNode
from src.langgraphagenticai.tools.search_tool import get_tools, create_tool_nodes
from langgraph.prebuilt import tools_condition
from src.langgraphagenticai.state.state import State
from langgraph.checkpoint.memory import MemorySaver

class ChatbotWithToolGraphBuilder:
    def __init__(self, llm, memory: MemorySaver):
        self.llm = llm
        self.memory = memory

    def build_graph(self):
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