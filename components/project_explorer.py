import os
import mimetypes
from pathspec import PathSpec
from pathspec.patterns import GitWildMatchPattern
import logging
import streamlit as st
from components.utils import save_analysis_results, load_analysis_results

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Predefined set of text file extensions
TEXT_EXTENSIONS = {
    ".dart", ".yaml", ".yml", ".json", ".lock",
    ".md", ".txt", ".xml", ".plist", ".gradle",
    ".properties", ".podspec", ".pbxproj", ".kt", ".swift"
}

class ProjectExplorer:
    def __init__(self, root_dir):
        """
        Initialize the ProjectExplorer with the root directory.
        """
        self.root_dir = root_dir
        self.gitignore_spec = self._load_gitignore()
        self.text_extensions = TEXT_EXTENSIONS.copy()

    def _load_gitignore(self):
        """
        Load .gitignore rules into a PathSpec object for exclusion.
        """
        gitignore_path = os.path.join(self.root_dir, ".gitignore")
        if os.path.exists(gitignore_path):
            try:
                with open(gitignore_path, "r") as f:
                    lines = [l.strip() for l in f if l.strip() and not l.startswith("#")]
                return PathSpec.from_lines(GitWildMatchPattern, lines)
            except Exception as e:
                logger.warning(f"Failed to load .gitignore: {str(e)}")
        return None

    def update_text_extensions(self, new_extensions):
        """
        Update the set of recognized text file extensions.
        """
        self.text_extensions.update(new_extensions)

    def is_text_file(self, file_path):
        """
        Determine whether a file is a text file based on MIME type or extension.
        """
        mime_type = mimetypes.guess_type(file_path)[0]
        return (mime_type and mime_type.startswith("text")) or os.path.splitext(file_path)[1].lower() in self.text_extensions

    @st.cache_data(ttl=3600)  # Cache results for 1 hour
    def get_directory_tree(_self):
        """
        Build a hierarchical directory tree as a nested dictionary.
        """
        tree = {"__name__": os.path.basename(_self.root_dir), "__path__": _self.root_dir, "__children__": []}
        total_items = sum(len(files) for _, _, files in os.walk(_self.root_dir))
        progress_bar = st.progress(0)
        processed_items = _self._build_tree_with_progress(_self.root_dir, tree, progress_bar, total_items, 0)
        # Save directory tree securely
        save_analysis_results(tree, "directory_tree.json")
        return tree

    def _build_tree_with_progress(self, directory, parent_node, progress_bar, total_items, processed_items):
        """
        Recursively build the directory tree while updating the progress bar.
        """
        try:
            items = os.listdir(directory)
            for item in items:
                path = os.path.join(directory, item)
                rel_path = os.path.relpath(path, self.root_dir)
                if self.gitignore_spec and self.gitignore_spec.match_file(rel_path):
                    continue
                if os.path.isdir(path):
                    node = {"__name__": item, "__path__": path, "__is_directory__": True, "__children__": []}
                    processed_items = self._build_tree_with_progress(path, node, progress_bar, total_items, processed_items)
                    parent_node["__children__"].append(node)
                else:
                    parent_node["__children__"].append({
                        "__name__": item,
                        "__path__": path,
                        "__is_file__": True,
                        "__is_text_file__": self.is_text_file(path)
                    })
                processed_items += 1
                progress_value = min(processed_items / total_items, 1.0)
                progress_bar.progress(progress_value)
            return processed_items
        except PermissionError as e:
            logger.warning(f"Permission denied for directory: {directory}. Skipping...")
        except Exception as e:
            logger.error(f"An unexpected error occurred while processing directory: {directory}. Error: {str(e)}")
        return processed_items

    def render_tree(self, tree):
        """
        Render the directory tree in the Streamlit UI using expanders.
        """
        for child in tree["__children__"]:
            if "__is_file__" not in child or "__is_directory__" not in child:
                logger.warning(f"Invalid node encountered: {child}")
                continue
            if child.get("__is_directory__", False):
                with st.expander(child["__name__"]):
                    self.render_tree(child)
            elif child.get("__is_file__", False):
                if child["__is_text_file__"]:
                    st.write(f"📄 {child['__name__']}")
                else:
                    st.write(f"📁 {child['__name__']}")

    @st.cache_data(ttl=3600)  # Cache results for 1 hour
    def load_cached_directory_tree(_self):
        """
        Load a cached directory tree from a JSON file.
        """
        cached_tree = load_analysis_results("directory_tree.json")
        if cached_tree:
            return cached_tree
        return _self.get_directory_tree()