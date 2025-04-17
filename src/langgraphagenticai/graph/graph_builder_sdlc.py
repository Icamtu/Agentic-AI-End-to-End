# src/langgraphagenticai/graph/graph_builder_blog.py
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
        Focuses on reliable checkpointing by adjusting interrupt timing.
        """
        try:
            if not self.llm:
                raise ValueError("LLM model not initialized")
            pass
            # graph_builder = StateGraph(state_schema=State)
            # blog_node = BlogGenerationNode(self.llm)

            # Add nodes

          
            return  # Changed from interrupt_after
        except Exception as e:
            logger.error(f"Error building graph: {e}")
            raise