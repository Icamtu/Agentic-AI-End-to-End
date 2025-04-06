# src/langgraphagenticai/graph/graph_builder_basic.py
from langgraph.graph import StateGraph, START, END
from src.langgraphagenticai.nodes.basic_chatbot_node import BasicChatbotNode
from src.langgraphagenticai.state.state import State
from langgraph.checkpoint.memory import MemorySaver

class BasicChatbotGraphBuilder:
    def __init__(self, llm, memory: MemorySaver):
        self.llm = llm
        self.memory = memory

    def build_graph(self):
        """
        Builds a graph for the Basic Chatbot use case.
        """
        graph_builder = StateGraph(state_schema=State)
        basic_chatbot_node = BasicChatbotNode(self.llm)
        graph_builder.add_node("chatbot", basic_chatbot_node.create_chatbot())
        graph_builder.add_edge(START, "chatbot")
        graph_builder.add_edge("chatbot", END)
        return graph_builder.compile(checkpointer=self.memory)