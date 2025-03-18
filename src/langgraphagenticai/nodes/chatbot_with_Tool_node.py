# from src.langgraphagenticai.state.state import State

# class ChatbotWithToolNode:
#     """"
#     Chatbot logic for Chatbot with Tool use case.
#     """
#     def __init__(self,model):
#         self.llm=model
    
#     def process(self,state:State)->dict:
#         """
#         Processes the input state and generates a response with tool integration.
#         """
#         user_input=state['messages'][-1] if state['messages'] else ''
#         llm_response=self.llm.invoke([{"role":"user","content":user_input}])

#         # simulate tool integration
#         tools_response=f"Tool integration for '{user_input}'"

#         return {"messages":[llm_response,tools_response]}
    
#     def create_chatbot(self,tools):
#         """ 
#         Returns a chatbot node function.
#         """
#         llm_with_tools= self.llm.bind_tools(tools)

#         def chatbot_node(state:State):
#             """ 
#             Chatbot logic for processing the input state and returning a response.
#             """
#             return {"messages": llm_with_tools.invoke(state['messages'])}
        
#         return chatbot_node
    

from src.langgraphagenticai.state.state import State
from langchain_core.messages import AIMessage, SystemMessage
from langchain_core.prompts import ChatPromptTemplate

class ChatbotWithToolNode:
    """
    Chatbot logic for Chatbot with Tool use case.
    """
    def __init__(self, model):
        self.llm = model
        # Define a prompt to ensure focused responses
        self.prompt = ChatPromptTemplate.from_messages([
            ("system", "You are a helpful assistant. Use the conversation history to inform your response, but only answer the current query without repeating old data unless directly relevant."),
            ("placeholder", "{messages}")
        ])
    
    def process(self, state: State) -> dict:
        """
        Processes the input state and generates a response with tool integration.
        Deprecated: Use create_chatbot for the graph.
        """
        messages = state["messages"]
        llm_response = self.llm.invoke(messages)
        tools_response = AIMessage(content=f"Tool integration for '{messages[-1].content}'")
        state["messages"].extend([llm_response, tools_response])
        return state
    
    def create_chatbot(self, tools):
        """ 
        Returns a chatbot node function with tool integration.
        """
        llm_with_tools = self.llm.bind_tools(tools)

        def chatbot_node(state: State) -> dict:
            """ 
            Chatbot logic for processing the input state and returning a response.
            Appends the LLM response to the message history.
            """
            messages = state["messages"]
            # Combine prompt with messages
            prompted_input = self.prompt.format_prompt(messages=messages).to_messages()
            response = llm_with_tools.invoke(prompted_input)
            state["messages"].append(response if isinstance(response, AIMessage) else AIMessage(content=str(response)))
            return state
        
        return chatbot_node