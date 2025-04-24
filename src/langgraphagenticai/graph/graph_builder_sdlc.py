# src/langgraphagenticai/graph/graph_builder_sdlc.py
from langgraph.graph import StateGraph, START, END
from src.langgraphagenticai.nodes.sdlc_node import SdlcNode
from src.langgraphagenticai.state.state import SDLCStages, SDLCState as State
from langgraph.checkpoint.memory import MemorySaver
from pydantic import BaseModel, Field
from langchain_core.messages import SystemMessage, HumanMessage
import logging
import json
import logging
import functools
import time
from src.langgraphagenticai.logging.logging_utils import logger, log_entry_exit

class SdlcGraphBuilder:
    def __init__(self, llm, memory: MemorySaver=None):
        self.llm = llm
        self.memory = memory if memory is not None else MemorySaver()

    @log_entry_exit
    def build_graph(self):
        """
        Builds a graph for the Software Development Life Cycle (SDLC) process.
        Interrupts *after* user story generation to allow feedback processing on resume.
        """
        try:
            if not self.llm:
                raise ValueError("LLM model not initialized")

            graph_builder = StateGraph(state_schema=State)
            sldc_node = SdlcNode(self.llm)

            # Add nodes
            graph_builder.add_node("Requirement", sldc_node.user_input)
            graph_builder.add_node("GenerateRequirements", sldc_node.generate_requirements)
            graph_builder.add_node("GenerateUserStories", sldc_node.generate_user_stories)
            graph_builder.add_node("ProcessFeedback", sldc_node.process_feedback) # Keep explicit feedback node

            # --- Define Edges ---
            graph_builder.add_edge(START, "Requirement")
            graph_builder.add_edge("Requirement", "GenerateRequirements")
            graph_builder.add_edge("GenerateRequirements", "GenerateUserStories")
            # Edge from User Stories to the Feedback node
            graph_builder.add_edge("GenerateUserStories", "ProcessFeedback") # This runs *after* interrupt

            # Conditional edge *after* feedback processing
            graph_builder.add_conditional_edges(
                "ProcessFeedback",
                # Reads the decision placed into the state by ProcessFeedback node
                lambda state: state.get("feedback_decision", "accept"),
                {
                    "accept": END,
                    "reject": "Requirement" # Loop back if rejected
                }
            )

            # --- Compile with interrupt AFTER user story generation ---
            return graph_builder.compile(
                interrupt_after=["GenerateUserStories"], # Interrupt AFTER this node runs
                checkpointer=self.memory
            )
        except Exception as e:
            logger.error(f"Error building graph: {e}")
            raise

