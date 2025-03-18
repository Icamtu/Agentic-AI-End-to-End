# src/langgraphagenticai/nodes/basic_chatbot_node.py
from src.langgraphagenticai.state.state import State
from langchain_core.messages import AIMessage

class BasicChatbotNode:
    def __init__(self, model):
        self.llm = model
    
    def process(self, state: State) -> dict:
        messages = state["messages"]
        response = self.llm.invoke(messages)
        state["messages"].append(response if isinstance(response, AIMessage) else AIMessage(content=str(response)))
        return state