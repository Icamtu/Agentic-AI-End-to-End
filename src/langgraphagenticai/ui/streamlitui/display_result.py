import streamlit as st
from langchain_core.messages import HumanMessage, AIMessage, ToolMessage
import json

class DisplayResultStreamlit:
    def __init__(self,usecase,graph,user_message):
        self.usecase= usecase
        self.graph= graph
        self.user_message=user_message
    
    def display_result_on_ui(self):
        usecase= self.usecase
        graph = self.graph
        user_message = self.user_message
        if usecase =="Basic Chatbot":
                for event in graph.stream({'messages':("user",user_message)}):
                    print(event.values())
                    for value in event.values():
                        print(value['messages'])
                        with st.chat_message("user"):
                            st.write(user_message)
                        with st.chat_message("assistant"):
                            st.write(value["messages"].content)
    
        elif usecase=="Chatbot with Tool":
             # Prepare state and invoke the graph
            initial_state = {"messages": [user_message]}
            res = graph.invoke(initial_state)
            for message in res['messages']:
                if type(message) == HumanMessage:
                    with st.chat_message("user"):
                        st.write(message.content)
                elif type(message)==ToolMessage:
                    with st.chat_message("ai"):
                        st.write("Tool Call Start")
                        st.write(message.content)
                        st.write("Tool Call End")
                elif type(message)==AIMessage and message.content:
                    with st.chat_message("assistant"):
                        st.write(message.content)
        elif usecase == "Blog Generation":
            # Prepare state and invoke the graph for blog generation
            initial_state = {
                "messages": [HumanMessage(content=user_message)],
                "topic": user_message,  # Assume user_message is the topic
                "sections": [],
                "completed_sections": [],
                "final_report": ""
            }
            res = graph.invoke(initial_state)
            with st.chat_message("user"):
                st.write(f"Blog topic: {user_message}")
            with st.chat_message("assistant"):
                st.markdown("### Generated Blog")
                st.markdown(res["final_report"])  # Display the final report in markdown

        elif usecase == "Coding Peer Review":
            # Prepare state and invoke the graph for code review
            initial_state = {
                "messages": [HumanMessage(content="Review this code")],
                "code_input": user_message,  # Assume user_message is the code
                "review_output": ""
            }
            res = graph.invoke(initial_state)
            with st.chat_message("user"):
                st.code(user_message, language="python")  # Display code in a code block
            with st.chat_message("assistant"):
                st.markdown("### Code Review Feedback")
                st.markdown(res["review_output"])  # Display review in markdown

        else:
            st.error(f"Unknown use case: {usecase}")