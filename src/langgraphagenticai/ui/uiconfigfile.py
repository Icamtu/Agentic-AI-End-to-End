from configparser import ConfigParser
import os
from src.langgraphagenticai.utils.model_utils import fetch_groq_models
import logging

logger = logging.getLogger(__name__)

class Config:
    def __init__(self, config_file=os.path.join(os.path.dirname(__file__), 'uiconfigfile.ini')):
        self.config_file = config_file
        self.config = ConfigParser()
        self.config.read(config_file)
        
    def update_groq_models(self, api_key: str = None) -> None:
        """Update Groq models in the config file."""
        try:
            models = fetch_groq_models(api_key)
            if models:
                # Keep some default models as fallback
                default_models = ["mistral-saba-24b", "llama3-8b-8192"]
                all_models = list(set(models + default_models))
                self.config["DEFAULT"]["GROQ_MODEL_OPTIONS"] = ", ".join(all_models)
                
                with open(self.config_file, 'w') as f:
                    self.config.write(f)
                logger.info("Successfully updated Groq models in config")
            
        except Exception as e:
            logger.error(f"Failed to update Groq models in config: {e}")

    def get_llm_options(self):
        return self.config["DEFAULT"].get("LLM_OPTIONS").split(", ")
    
    def get_usecase_options(self):
        return self.config["DEFAULT"].get("USECASE_OPTIONS").split(", ")

    def get_groq_model_options(self):
        return self.config["DEFAULT"].get("GROQ_MODEL_OPTIONS").split(", ")
    
    def get_google_model_options(self):
        return self.config["DEFAULT"].get("Google_MODEL_OPTIONS").split(", ")
    
    def get_openai_model_options(self):
        return self.config["DEFAULT"].get("OPENAI_MODEL_OPTIONS").split(", ")

    def get_page_title(self):
        return self.config["DEFAULT"].get("PAGE_TITLE")