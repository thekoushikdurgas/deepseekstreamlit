import asyncio
import logging
import streamlit as st
from ollama import AsyncClient
from pydantic import BaseModel
from components.utils import save_analysis_results, load_analysis_results
from components.project_explorer import ProjectExplorer

# Configure logging for debugging and monitoring
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Configuration constants
OLLAMA_HOST = "http://localhost:11434"
CACHE_TTL = 3600  # Cache time-to-live in seconds (1 hour)
@st.cache_resource(ttl=3600)  # Use st.cache_resource for unserializable objects
async def initialize_components(directory_path):
    """
    Initialize ProjectExplorer and AIClient with caching.
    """
    async def async_initialize():
        # Initialize ProjectExplorer
        explorer = ProjectExplorer(directory_path)
        # Initialize AIClient asynchronously
        ai_client = await initialize_ai_client()
        return explorer, ai_client

    # Await the async function directly
    return await async_initialize()

@st.cache_resource  # Use st.cache_resource for unserializable objects like AIClient
async def initialize_ai_client():
    """
    Initialize AIClient with caching.
    """
    ai_client = AIClient()
    if not ai_client.available_models:
        ai_client.available_models = await ai_client.fetch_available_models()
        logger.info(f"Fetched {len(ai_client.available_models)} models.")
    return ai_client
# Pydantic model for structured outputs
class FileAnalysis(BaseModel):
    file_path: str
    summary: str
    dependencies: list = []
    recommendations: list = []

class AIClient:
    def __init__(self):
        """
        Initialize the AI client with default settings.
        """
        self.client = AsyncClient(host=OLLAMA_HOST)
        self.model_map = {
            ".dart": "codellama",
            ".yaml": "llama3",
            ".yml": "llama3",
            ".gradle": "phi3",
            ".xml": "phi3",
            ".plist": "phi3",
            ".kt": "codellama",
            ".swift": "codellama",
        }
        self.available_models = None
        self.chat_history = {}  # Store chat history per file
        self.options = {"temperature": 0.5}  # Default options

    @st.cache_resource(ttl=CACHE_TTL)  # Use st.cache_resource for unserializable objects
    async def fetch_available_models(self):
        """
        Fetch available AI models asynchronously from the Ollama service.
        """
        try:
            response = await self.client.list()
            if "models" in response and isinstance(response["models"], list):
                models = [
                    {
                        "name": model.get("model", "Unknown Model"),
                        "size_mb": f"{(model.get('size', 0) / 1024 / 1024):.2f}",
                        "format": model.get("details", {}).get("format", "Unknown Format"),
                        "family": model.get("details", {}).get("family", "Unknown Family"),
                        "parameter_size": model.get("details", {}).get("parameter_size", "Unknown Size"),
                        "quantization_level": model.get("details", {}).get("quantization_level", "Unknown Level"),
                    }
                    for model in response["models"]
                ]
                # Save fetched models securely
                save_analysis_results(models, "available_models.json")
                return models
            else:
                logger.error("Unexpected response format from Ollama service: %s", response)
                st.error("Unexpected response format from Ollama service.")
                return []
        except Exception as e:
            logger.error("Failed to fetch models: %s", str(e))
            st.error(f"Failed to fetch models: {str(e)}")
            return []

    @st.cache_resource(ttl=CACHE_TTL, show_spinner=False)  # Use st.cache_resource for unserializable objects
    async def analyze_file(self, model, context, prompt, depth, file_path, stream=False):
        """
        Analyze a file using the specified AI model.
        """
        try:
            messages = self.chat_history.get(file_path, [])
            messages.append({"role": "user", "content": prompt})
            if stream:
                return await self._stream_response(model, messages, file_path)
            else:
                return await self._process_response(model, messages, file_path, depth)
        except Exception as e:
            logger.error(f"Analysis failed: {str(e)}")
            return {"error": f"Analysis failed: {str(e)}"}

    async def _stream_response(self, model, messages, file_path):
        """
        Handle streaming responses from the AI model.
        """
        response_placeholder = st.empty()
        full_response = ""
        progress_bar = st.progress(0)
        async for i, part in enumerate(self.client.chat(model=model, messages=messages, stream=True)):
            content = part['message']['content']
            full_response += content
            response_placeholder.markdown(full_response)
            progress_bar.progress((i + 1) / 100)  # Simulate progress
        messages.append({"role": "assistant", "content": full_response})
        self.chat_history[file_path] = messages
        # Save streaming response securely
        save_analysis_results(full_response, f"stream_response_{file_path}.json")
        return full_response

    async def _process_response(self, model, messages, file_path, depth):
        """
        Process non-streaming responses from the AI model.
        """
        response = await self.client.chat(
            model=model,
            messages=messages,
            options={"temperature": 0.7 if depth == "Technical Deep Dive" else 0.3},
        )
        messages.append({"role": "assistant", "content": response['message']['content']})
        self.chat_history[file_path] = messages
        try:
            validated_response = FileAnalysis.model_validate_json(response['message']['content'])
            # Save processed response securely
            save_analysis_results(validated_response.model_dump(), f"processed_response_{file_path}.json")
            return validated_response.model_dump()
        except Exception as e:
            logger.error(f"Invalid JSON response: {response['message']['content']}")
            return {"error": "Invalid JSON response", "raw_response": response['message']['content']}

    def update_model_map(self, extension, model_name):
        """
        Update the model map with a new extension-model pair.
        """
        self.model_map[extension] = model_name

    @st.cache_resource(ttl=CACHE_TTL)  # Use st.cache_resource for unserializable objects
    def load_cached_models(_self):
        """
        Load cached AI models from a JSON file.
        """
        cached_models = load_analysis_results("available_models.json")
        if cached_models:
            return cached_models
        return _self.fetch_available_models()