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
        try:
            if not self.llm:
                raise ValueError("LLM model not initialized")

            graph_builder = StateGraph(state_schema=State)
            sldc_node = SdlcNode(self.llm)

            # Add nodes
            graph_builder.add_node("Requirement", sldc_node.user_input)
            graph_builder.add_node("GenerateRequirements", sldc_node.generate_requirements)
            graph_builder.add_node("GenerateUserStories", sldc_node.generate_user_stories)
            graph_builder.add_node("ProcessFeedback", sldc_node.process_feedback)
            graph_builder.add_node("DesignDocuments", sldc_node.design_documents)
            graph_builder.add_node("DesignFeedback", sldc_node.process_feedback)
            graph_builder.add_node("DevelopmentArtifact", sldc_node.development_artifact)
            graph_builder.add_node("DevelopmentFeedback", sldc_node.process_feedback)
            graph_builder.add_node("TestingArtifact", sldc_node.testing_artifact)
            graph_builder.add_node("TestingFeedback", sldc_node.process_feedback)
            graph_builder.add_node("DeploymentArtifact", sldc_node.deployment_artifact)
            graph_builder.add_node("DeploymentFeedback", sldc_node.process_feedback)


            # Define Edges
            graph_builder.add_edge(START, "Requirement")
            graph_builder.add_edge("Requirement", "GenerateRequirements")
            graph_builder.add_edge("GenerateRequirements", "GenerateUserStories")
            graph_builder.add_edge("GenerateUserStories", "ProcessFeedback")

            # Conditional edge after feedback processing
            graph_builder.add_conditional_edges(
                "ProcessFeedback",
                sldc_node.feedback_route,
                {
                    "accept": "DesignDocuments",
                    "reject": "GenerateUserStories"
                }
            )

            graph_builder.add_edge("DesignDocuments", "DesignFeedback")

             # Conditional edge after feedback processing
            graph_builder.add_conditional_edges(
                "DesignFeedback",
                sldc_node.feedback_route,
                {
                    "accept": "DevelopmentArtifact",
                    "reject": "DesignDocuments"
                }
            )
            graph_builder.add_edge("DevelopmentArtifact", "DevelopmentFeedback")

             # Conditional edge after feedback processing
            graph_builder.add_conditional_edges(
                "DevelopmentFeedback",
                sldc_node.feedback_route,
                {
                    "accept": "TestingArtifact",
                    "reject": "DevelopmentArtifact"
                }
            )
            graph_builder.add_edge("TestingArtifact", "TestingFeedback")

             # Conditional edge after feedback processing
            graph_builder.add_conditional_edges(
                "TestingFeedback",
                sldc_node.feedback_route,
                {
                    "accept": "DeploymentArtifact",
                    "reject": "TestingArtifact"
                }
            )
            graph_builder.add_edge("DeploymentArtifact", "DeploymentFeedback")
            # Conditional edge after feedback processing
            graph_builder.add_conditional_edges(
                "DeploymentFeedback",
                sldc_node.feedback_route,
                {
                    "accept": END,
                    "reject": "DeploymentArtifact"
                }
            )

            

            # Compile with interrupt
            graph = graph_builder.compile(
                interrupt_after=["GenerateUserStories", "DesignDocuments", "DevelopmentArtifact", "TestingArtifact", "DeploymentArtifact"],
                checkpointer=self.memory
            )
            logger.info("Graph compiled with checkpointer: %s", self.memory)
            return graph
        except Exception as e:
            logger.error(f"Error building graph: {e}")
            raise