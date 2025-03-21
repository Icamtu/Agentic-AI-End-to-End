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
                            tool_args = tool_call.get('args', {})
                            search_query = tool_args.get('query', '')
                            
                            # Find and execute the Tavily tool
                            tavily_tool = next((t for t in tools if t.__class__.__name__ == 'TavilySearchResults'), None)
                            if tavily_tool:
                                search_results = tavily_tool(search_query)
                                # Format search results in a clean markdown structure
                                formatted_results = self._format_search_results(search_results)
                                state["messages"].append(AIMessage(content=formatted_results))
                                # Get final response with search results
                                final_response = llm_with_tools.invoke(state["messages"])
                                response = final_response

                # Format the final response content
                formatted_response = self._format_response_content(response)
                state["messages"].append(AIMessage(content=formatted_response))
                
            except Exception as e:
                logger.error(f"Error processing message: {str(e)}")
                state["messages"].append(AIMessage(content="I apologize, but I encountered an error processing your request. Please try again."))
            
            return state

        return chatbot_node

    def _format_search_results(self, results):
        """Format search results in a clean markdown structure."""
        if not results:
            return "No search results found."
            
        formatted = "### Search Results\n\n"
        for i, result in enumerate(results, 1):
            if isinstance(result, dict):
                title = result.get('title', 'Untitled')
                content = result.get('content', '').strip()
                formatted += f"**{i}. {title}**\n{content}\n\n"
        return formatted

    def _format_response_content(self, response):
        """Format the response content with proper markdown structure."""
        if not hasattr(response, 'content'):
            return str(response)
            
        content = response.content
        
        # If content contains section headers, ensure proper formatting
        if "# " in content or "## " in content:
            # Ensure consistent header formatting
            lines = content.split('\n')
            formatted_lines = []
            for line in lines:
                # Fix section headers
                if line.strip().startswith('#'):
                    line = line.strip()
                    if not line.startswith('# ') and not line.startswith('## '):
                        line = f"## {line.lstrip('#').strip()}"
                formatted_lines.append(line)
            content = '\n\n'.join(formatted_lines)
        
        return content.strip()