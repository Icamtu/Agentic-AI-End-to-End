# src/langgraphagenticai/nodes/basic_chatbot_node.py
from src.langgraphagenticai.state.state import State
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
import logging

logger = logging.getLogger(__name__)

class BasicChatbotNode:
    def __init__(self, model):
        self.llm = model

    def process(self, state: State) -> dict:
        messages = state["messages"]
        response = self.llm.invoke(messages)
        state["messages"].append(response if isinstance(response, AIMessage) else AIMessage(content=str(response)))
        return state

    def create_chatbot(self):
        """
        Creates and returns a basic chatbot function that processes messages using the LLM.
        """
        def chatbot(state: State) -> dict:
            try:
                if not state.get("messages"):
                    logger.warning("No messages found in state")
                    return {"messages": [AIMessage(content="No input received. How can I help you?")]}

                # Get the last message
                last_message = state["messages"][-1]
                
                # Process with LLM
                response = self.llm.invoke([
                    SystemMessage(content="You are a helpful AI assistant."),
                    *state["messages"]
                ])

                # Update state with response
                return {"messages": [*state["messages"], AIMessage(content=response.content)]}

            except Exception as e:
                logger.error(f"Error in chatbot processing: {e}")
                return {"messages": [AIMessage(content=f"I encountered an error: {str(e)}")]}

        return chatbot