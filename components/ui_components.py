import os
import hashlib
import asyncio
import logging
import streamlit as st
from components.local_ai_client import analyze_code_chunk_local, load_local_model
from components.utils import truncate_content, _create_analysis_prompt, save_analysis_results, load_analysis_results
from components.ai_client import FileAnalysis

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@st.cache_resource(ttl=3600)  # Use st.cache_resource for unserializable objects
async def render_main_content(explorer, ai_client, path):
    """
    Render the main content for analyzing a single file.
    """
    try:
        if not os.path.isfile(path):
            logger.warning(f"File not found: {path}")
            st.error(f"File not found: {path}")
            return

        # Read and truncate file content
        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            content = f.read()
            truncated_content = truncate_content(content)

        # Map file extensions to programming languages for syntax highlighting
        language_map = {
            ".py": "python", ".dart": "dart", ".yaml": "yaml", ".yml": "yaml",
            ".json": "json", ".md": "markdown", ".txt": "plaintext", ".xml": "xml",
            ".gradle": "groovy", ".kt": "kotlin", ".swift": "swift", ".js": "javascript",
            ".ts": "typescript", ".html": "html", ".css": "css", ".java": "java",
            ".c": "c", ".cpp": "cpp", ".h": "c", ".hpp": "cpp", ".sh": "bash",
            ".rs": "rust", ".go": "go", ".rb": "ruby", ".php": "php"
        }
        language = language_map.get(os.path.splitext(path)[1].lower(), None)

        # Display file content with syntax highlighting
        code_text = f"# 📄 File: {os.path.relpath(path, explorer.root_dir)}\n" + content
        st.code(code_text, language=language, line_numbers=True)

        # Display truncated content in a text area
        st.subheader("File Content")
        st.text_area("Content", value=truncated_content, height=300, key=f"content_{path}")

        # User inputs for analysis depth and custom focus areas
        analysis_depth = st.selectbox(
            "Select Analysis Depth",
            ["Normal", "Brief", "Detailed", "Technical Deep Dive"],
            index=0,
            key=f"depth_{path}",
            help="Choose the level of detail for the analysis."
        )
        custom_focus_areas = st.text_area(
            "Custom Focus Areas (comma-separated)",
            value="",
            key=f"focus_{path}",
            help="Provide additional areas to focus on during analysis."
        )
        custom_focus_areas = (
            [area.strip() for area in custom_focus_areas.split(",") if area.strip()]
            if custom_focus_areas
            else None
        )

        # Generate analysis prompt
        analysis_prompt = _create_analysis_prompt(
            path=path,
            content=content,
            depth=analysis_depth,
            model=ai_client.model_map.get(os.path.splitext(path)[1], "default"),
            custom_focus_areas=custom_focus_areas,
        )

        # Analyze file button
        if st.button("Analyze File", key=f"analyze_{path}"):
            with st.spinner("Analyzing file..."):
                context = hashlib.md5(content.encode()).hexdigest()[:8]
                analysis = await ai_client.analyze_file(
                    model=ai_client.model_map.get(os.path.splitext(path)[1], "default"),
                    context=context,
                    prompt=analysis_prompt,
                    depth=analysis_depth,
                    file_path=path,
                    stream=False,
                )
                try:
                    validated_response = FileAnalysis.model_validate_json(analysis)
                    st.json(validated_response.model_dump())
                except Exception as e:
                    logger.error(f"Failed to validate structured output: {str(e)}")
                    st.error(f"Failed to validate structured output: {str(e)}")
                    st.markdown(analysis)

    except PermissionError as e:
        logger.warning(f"Permission denied for file: {path}. Skipping...")
        st.error(f"Permission denied for file: {path}")
    except Exception as e:
        logger.error(f"Error reading file: {str(e)}")
        st.error(f"Error reading file: {str(e)}")

@st.cache_resource(ttl=3600)  # Use st.cache_resource for unserializable objects
async def analyze_directory(explorer, ai_client, model):
    """
    Analyze all text files in a directory recursively.
    """
    st.info(f"Analyzing directory with model: {model}")
    tree = explorer.get_directory_tree()

    # Count total text files
    total_files = sum(
        1 for node in tree["__children__"]
        if node.get("__is_file__", False) and node.get("__is_text_file__", False)
    )
    if total_files == 0:
        st.warning("No text files found in the directory.")
        return

    results = {}
    progress_bar = st.progress(0)
    processed_files = 0

    async def analyze_node(node):
        nonlocal processed_files
        if "__children__" in node:
            tasks = [analyze_node(child) for child in node["__children__"]]
            await asyncio.gather(*tasks)
        elif node.get("__is_file__", False) and node.get("__is_text_file__", False):
            try:
                with open(node["__path__"], "r", encoding="utf-8", errors="ignore") as f:
                    content = f.read()
                    context = hashlib.md5(content.encode()).hexdigest()[:8]
                    prompt = _create_analysis_prompt(
                        node["__path__"], content, "Detailed", model
                    )
                    analysis = await ai_client.analyze_file(
                        model=model,
                        context=context,
                        prompt=prompt,
                        depth="Detailed",
                        file_path=node["__path__"],
                        stream=False,
                    )
                    results[node["__path__"]] = analysis
                    # Save analysis results securely
                    save_analysis_results(results, "analysis_results.json")
            except PermissionError as e:
                results[node["__path__"]] = f"Permission denied: {str(e)}"
                logger.warning(f"Permission denied for file: {node['__path__']}")
            except Exception as e:
                results[node["__path__"]] = f"Error analyzing file: {str(e)}"
                logger.error(f"Error analyzing file: {node['__path__']}: {str(e)}")
            finally:
                processed_files += 1
                progress_value = min(processed_files / total_files, 1.0)
                progress_bar.progress(progress_value)

    await analyze_node(tree)

    # Load cached analysis results
    cached_results = load_analysis_results("analysis_results.json")
    if cached_results:
        results.update(cached_results)

    # Display directory analysis results
    st.subheader("Directory Analysis Results")
    for path, analysis in results.items():
        with st.expander(f"📄 {os.path.relpath(path, explorer.root_dir)}"):
            st.markdown(analysis)
            await render_main_content(explorer, ai_client, path)
