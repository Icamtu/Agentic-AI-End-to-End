import streamlit as st
from langchain_core.messages import HumanMessage, AIMessage, ToolMessage

class DisplayResultStreamlit:
    def __init__(self, usecase, graph, user_message, response=None):
        self.usecase = usecase
        self.graph = graph
        self.user_message = user_message
        self.response = response
    
    def display_result_on_ui(self):
        """Display the latest assistant response from the graph and return it."""
        usecase = self.usecase
        response = self.response

        if not response:
            st.error("No response provided to display.")
            return "Error: No response"

        if usecase == "Basic Chatbot":
            assistant_response = response["messages"][-1].content if response["messages"] else "No response"
            st.markdown(assistant_response)
            return assistant_response

        elif usecase == "Chatbot with Tool":
            # Display only the latest relevant message
            last_message = response["messages"][-1]
            if isinstance(last_message, ToolMessage):
                st.write("Tool Call Start")
                st.write(last_message.content)
                st.write("Tool Call End")
                assistant_response = last_message.content
            elif isinstance(last_message, AIMessage) and last_message.content:
                st.write(last_message.content)
                assistant_response = last_message.content
            else:
                assistant_response = "No response"
            return assistant_response

        elif usecase == "Blog Generation":
            assistant_response = response.get("final_report", "No blog generated")
            st.markdown("### Generated Blog")
            st.markdown(assistant_response)
            return assistant_response

        elif usecase == "Coding Peer Review":
            feedback = response.get("review_output", "No review generated")
            corrected_code = response.get("corrected_code", "No corrected code provided")
            st.markdown("### Code Review Feedback")
            st.markdown(feedback)
            st.markdown("### Corrected Code")
            st.markdown(corrected_code)
            return feedback + "\n\n" + corrected_code  # Combined for history

        else:
            st.error(f"Unknown use case: {usecase}")
            return "Error: Unknown use case"