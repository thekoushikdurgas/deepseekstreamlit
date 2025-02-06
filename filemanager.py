import utils.transport
import utils.session
import os
import asyncio
import logging
import streamlit as st
from components.ui_components import analyze_directory
from components.ai_client import AIClient
from components.project_explorer import ProjectExplorer
from components.utils import save_analysis_results

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

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

async def main():
    try:
        # Configure page settings
        st.set_page_config(layout="wide", page_title="Flutter AI Explorer")
        logger.info("Initializing Flutter AI Explorer...")

        # Input for directory path
        directory_path = st.text_input("Enter Directory Path", value=os.getcwd())

        # Initialize components with caching
        explorer, ai_client = await initialize_components(directory_path)

        # Render title and model selection
        st.title("Flutter AI Explorer")
        selected_model = st.selectbox(
            "Select AI Model",
            [model["name"] for model in ai_client.available_models],
            index=0,
            key="model_selection"
        )
        ai_client.model_map["default"] = selected_model

        # Optional: Add model-specific configuration options
        temperature = st.slider("Temperature", min_value=0.0, max_value=1.0, value=0.5, step=0.1)
        ai_client.options["temperature"] = temperature

        # Handle directory analysis button with a progress indicator
        if st.button("Analyze Directory with Selected Model", key="analyze_button"):
            with st.spinner("Analyzing directory..."):
                await analyze_directory(explorer, ai_client, selected_model)
                # Save analysis results securely
                save_analysis_results({"directory": directory_path, "model": selected_model}, "analysis_summary.json")
            st.success("Directory analysis completed!")

    except Exception as e:
        logger.error(f"An error occurred: {e}")
        st.error(f"An error occurred: {e}")

if __name__ == "__main__":
    try:
        # Use asyncio.run only at the top level
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Cleaning up resources...")
        st.info("Goodbye!")