import os
import logging
import json
import hmac
import hashlib
from streamlit.runtime.caching import cache_data

# Configure logging for debugging and monitoring
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def truncate_content(content, max_length=2000):
    """
    Truncate content to a maximum length while ensuring it ends at a word boundary.
    """
    if len(content) <= max_length:
        return content
    truncated = content[:max_length]
    last_space = truncated.rfind(" ", 0, max_length)
    return truncated[:last_space] + "..." if last_space > 0 else truncated + "..."

def _create_analysis_prompt(path, content, depth, model=None, custom_focus_areas=None):
    """
    Generate an analysis prompt for the AI model based on file content and user inputs.
    """
    try:
        if not content.strip():
            raise ValueError("File content is empty or contains only whitespace.")
        
        # Truncate content to avoid exceeding token limits
        truncated_content = truncate_content(content)

        # Default focus areas for analysis
        default_focus_areas = [
            "Architectural role in the project",
            "Cross-file dependencies",
            "Platform-specific implementations",
            "Performance considerations",
            "Maintenance recommendations"
        ]

        # Combine default and custom focus areas
        focus_areas = default_focus_areas + (custom_focus_areas or [])
        focus_text = "\n".join([f"{i+1}. {area}" for i, area in enumerate(focus_areas)])

        # Depth-specific instructions
        depth_specific_instructions = {
            "Normal": "Provide a concise summary.",
            "Brief": "Highlight key points only.",
            "Detailed": "Include comprehensive details.",
            "Technical Deep Dive": "Perform an in-depth technical analysis."
        }
        instructions = depth_specific_instructions.get(depth, "Provide a general analysis.")

        # Construct the final prompt
        prompt = f"""
        Analyze this Flutter project file using model '{model}':
        Path: {os.path.basename(path)}
        Partial Content:
        {truncated_content}
        Instructions: {instructions}
        Focus on:
        {focus_text}
        """
        return prompt.strip()
    except Exception as e:
        logger.error(f"Error creating analysis prompt: {str(e)}")
        raise ValueError(f"Failed to create analysis prompt: {str(e)}")

@cache_data(ttl=3600)  # Cache results for 1 hour
def save_analysis_results(results, file_path):
    """
    Serialize and save analysis results to a file using JSON for safety.
    """
    try:
        with open(file_path, "w") as f:
            json.dump(results, f, indent=4)
        return True
    except Exception as e:
        logger.error(f"Failed to save analysis results: {str(e)}")
        return False

@cache_data(ttl=3600)  # Cache results for 1 hour
def load_analysis_results(file_path):
    """
    Load and deserialize analysis results from a file using JSON for safety.
    """
    if not os.path.exists(file_path):
        logger.warning(f"File not found: {file_path}")
        return None
    try:
        with open(file_path, "r") as f:
            results = json.load(f)
        return results
    except Exception as e:
        logger.error(f"Failed to load analysis results: {str(e)}")
        return None

def save_securely(data, file_path, secret_key):
    """
    Save data securely using HMAC for integrity checks.
    """
    try:
        serialized = json.dumps(data).encode('utf-8')
        digest = hmac.new(secret_key.encode(), serialized, hashlib.sha256).hexdigest()
        with open(file_path, "wb") as f:
            f.write(digest.encode() + b"\n" + serialized)
        return True
    except Exception as e:
        logger.error(f"Failed to save data securely: {str(e)}")
        return False

def load_securely(file_path, secret_key):
    """
    Load data securely using HMAC for integrity checks.
    """
    try:
        with open(file_path, "rb") as f:
            stored_digest, serialized = f.readline().strip(), f.read()
        computed_digest = hmac.new(secret_key.encode(), serialized, hashlib.sha256).hexdigest()
        if not hmac.compare_digest(stored_digest.decode(), computed_digest):
            raise ValueError("Data integrity check failed.")
        return json.loads(serialized.decode('utf-8'))
    except Exception as e:
        logger.error(f"Failed to load data securely: {str(e)}")
        return None

def generate_report(data, filename, format="Markdown"):
    """Generate analysis report."""
    if format == "Markdown":
        with open(filename, 'w') as f:
            f.write("# Code Analysis Report\n\n")
            for item in data:
                f.write(f"## {item['file_path']}\n\n{item['analysis']}\n\n")
    elif format == "JSON":
        with open(filename, 'w') as f:
            json.dump({"analysis": data}, f, indent=2)