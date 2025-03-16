# code_reviewer_node.py
from src.langgraphagenticai.state.state import State
from langchain_core.messages import HumanMessage, SystemMessage

class CodeReviewerNode:
    def __init__(self, model):
        self.llm = model

    def review_code(self, state: State) -> dict:
        """Review the provided code and return feedback"""
        code = state["code_input"]
        review = self.llm.invoke(
            [
                SystemMessage(content="Review the following code and provide feedback in markdown format."),
                HumanMessage(content=code),
            ]
        )
        return {
            "messages": [SystemMessage(content="Code review completed")],
            "review_output": review.content
        }