# src/langgraphagenticai/nodes/chatbot_with_tool_node.py
from src.langgraphagenticai.state.state import State
from langchain_core.messages import AIMessage
from langchain_core.prompts import ChatPromptTemplate
from datetime import datetime
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class ChatbotWithToolNode:
    """
    Chatbot logic enhanced with tool integration and date awareness.
    """
    def __init__(self,model):
        self.llm = model
        self.prompt = ChatPromptTemplate.from_messages([
            ("system", "You are an AI assistant. The current date is {current_date}. "
                       "Use this information to provide up-to-date responses. "
                       "If you need to fetch current information, call the appropriate tool(max 2 times) but do not repeatedly call the tool."
                       "if you got result from tool call then stop calling tool and provide the result to user"),
            ("user", "{input}")
        ])

    def process(self, state: State) -> dict:
        """
        Processes the input state and generates a response with tool integration and date awareness.
        """
        user_input = state["messages"][-1] if state["messages"] else ""
        current_date = datetime.now().strftime("%B %d, %Y")  # e.g., "March 24, 2025""

        # Prepare the prompt with the current date
        formatted_prompt = self.prompt.format(
            current_date=current_date,
            input=user_input
        )
        # Invoke the LLM with the formatted prompt
        llm_response = self.llm.invoke(formatted_prompt)

       
        # Simulate tool-specific logic based on user input
        tools_response = f"Tool integration for: '{user_input}' with date: {current_date}"

        return {"messages": [llm_response, tools_response]}
    
    def create_chatbot(self, tools):
        """
        Returns a chatbot node function with tool binding and date awareness.
        """
        llm_with_tools = self.llm.bind_tools(tools)

        def chatbot_node(state: State):
            """
            Chatbot logic for processing the input state and returning a response.
            """
            current_date = datetime.now().strftime("%B %d, %Y")  # e.g., "March 24, 2025"
            user_input = state["messages"][-1] if state["messages"] else ""

            # Format the prompt with the current date
            formatted_prompt = self.prompt.format(
                current_date=current_date,
                input=user_input
            )
            # Invoke the LLM with tools enabled
            response = llm_with_tools.invoke(formatted_prompt)

            return {"messages": [response]}
            
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