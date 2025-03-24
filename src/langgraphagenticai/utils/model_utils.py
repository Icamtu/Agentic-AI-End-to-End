import requests
import os
import logging
from typing import List

logger = logging.getLogger(__name__)

def fetch_groq_models(api_key: str = None) -> List[str]:
    """
    Fetch available models from Groq API.
    
    Args:
        api_key (str, optional): Groq API key. Defaults to environment variable.
        
    Returns:
        List[str]: List of available model IDs
    """
    try:
        api_key = api_key or os.environ.get("GROQ_API_KEY")
        if not api_key:
            logger.warning("No Groq API key provided")
            return []

        url = "https://api.groq.com/openai/v1/models"
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }

        response = requests.get(url, headers=headers)
        response.raise_for_status()
        
        models = response.json().get("data", [])
        model_ids = [model["id"] for model in models]
        
        logger.info(f"Successfully fetched {len(model_ids)} Groq models")
        return model_ids

    except requests.exceptions.RequestException as e:
        logger.error(f"Failed to fetch Groq models: {e}")
        return []
