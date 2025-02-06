# local_ai_client.py
import os
import logging
from transformers import AutoModelForCausalLM, AutoTokenizer
import torch

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

MODEL_NAME = "deepseek-ai/deepseek-coder-6.7b-instruct"
MODEL_CACHE_DIR = "./model_cache"
DEVICE = "cuda" if torch.cuda.is_available() else "cpu"

@st.cache_resource
def load_local_model():
    """Load the local LLM model and tokenizer."""
    try:
        logger.info(f"Loading model {MODEL_NAME}...")
        tokenizer = AutoTokenizer.from_pretrained(
            MODEL_NAME,
            cache_dir=MODEL_CACHE_DIR,
            trust_remote_code=True
        )
        model = AutoModelForCausalLM.from_pretrained(
            MODEL_NAME,
            cache_dir=MODEL_CACHE_DIR,
            trust_remote_code=True,
            torch_dtype=torch.float16 if DEVICE == "cuda" else torch.float32,
            device_map="auto" if DEVICE == "cuda" else None
        )
        if DEVICE == "cpu":
            model = model.to(DEVICE)
        logger.info("Model loaded successfully")
        return model, tokenizer
    except Exception as e:
        logger.error(f"Model loading failed: {str(e)}")
        raise

def analyze_code_chunk_local(model, tokenizer, chunk: str) -> str:
    """Analyze a code chunk using the local model."""
    try:
        prompt = (
            "You are an expert code analyst. Analyze this code and provide:\n"
            "1. Potential bugs\n2. Code smells\n3. Optimization opportunities\n"
            "4. Security issues\n5. Architectural improvements\n\n"
            f"Code:\n```\n{chunk}\n```\n\nAnalysis:"
        )
        inputs = tokenizer(
            prompt,
            return_tensors="pt",
            max_length=4096,
            truncation=True
        ).to(DEVICE)
        outputs = model.generate(
            inputs.input_ids,
            max_new_tokens=512,
            temperature=0.3,
            top_p=0.95,
            do_sample=True
        )
        return tokenizer.decode(outputs[0], skip_special_tokens=True)
    except Exception as e:
        logger.error(f"Analysis failed: {str(e)}")
        return f"Analysis error: {str(e)}"