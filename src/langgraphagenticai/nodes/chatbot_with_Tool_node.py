# src/langgraphagenticai/nodes/chatbot_with_tool_node.py
from src.langgraphagenticai.state.state import State
from langchain_core.messages import AIMessage
from langchain_core.prompts import ChatPromptTemplate
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class ChatbotWithToolNode:
    def __init__(self, model):
        self.llm = model
        self.prompt = ChatPromptTemplate.from_messages([
            ("system", "You are a helpful assistant with access to tools. For queries requiring external data (e.g., search), use 'tavily_search_results_json'. Respond directly only if no tool is needed."),
            ("placeholder", "{messages}")
        ])
    
    def process(self, state: State) -> dict:
        messages = state["messages"]
        llm_response = self.llm.invoke(messages)
        tools_response = AIMessage(content=f"Tool integration for '{messages[-1].content}'")
        state["messages"].extend([llm_response, tools_response])
        return state
    
    def create_chatbot(self, tools):
        logger.info(f"Tools bound to LLM: {tools}")
        llm_with_tools = self.llm.bind_tools(tools)

        def chatbot_node(state: State) -> dict:
            try:
                messages = state["messages"]
                logger.info(f"Input messages: {messages}")
                prompted_input = self.prompt.format_prompt(messages=messages).to_messages()
                
                response = llm_with_tools.invoke(prompted_input)
                logger.info(f"Raw LLM response: {response}")
                
                # Handle tool calls
                if hasattr(response, 'tool_calls') and response.tool_calls:
                    logger.info(f"Tool call made: {response.tool_calls}")
                    for tool_call in response.tool_calls:
                        if tool_call.get('name') == "tavily_search_results_json":
                            # Execute tool with proper arguments
                            tool_args = tool_call.get('args', {})
                            search_query = tool_args.get('query', '')
                            
                            # Find and execute the Tavily tool
                            tavily_tool = next((t for t in tools if t.__class__.__name__ == 'TavilySearchResults'), None)
                            if tavily_tool:
                                search_results = tavily_tool(search_query)
                                state["messages"].append(AIMessage(content=f"Search results: {search_results}"))
                                # Get final response with search results
                                final_response = llm_with_tools.invoke(state["messages"])
                                response = final_response
                
                state["messages"].append(response if isinstance(response, AIMessage) else AIMessage(content=str(response)))
                
            except Exception as e:
                logger.error(f"Error processing message: {str(e)}")
                state["messages"].append(AIMessage(content="I apologize, but I encountered an error processing your request. Please try again."))
            
            return state
        
        return chatbot_node