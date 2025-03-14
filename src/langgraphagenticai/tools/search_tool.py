from langchain_community.tools.tavily_search import TavilySearchResults
from langgraph.prebuilt import ToolNode

def get_tools():
    """
    Returns a list of tools to be used in chatbot.
    """
    tools = [TavilySearchResults(max_results=2)]

    return tools

def create_tool_nodes(tools):
    """
    Creates & returns a tool node for the graph
    """
    return ToolNode(tools=tools)