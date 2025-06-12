import streamlit as st
from typing import Optional, Callable
import json
import os

try:
    from streamlit_js_eval import streamlit_js_eval
except ImportError:
    st.error("Please install streamlit-js-eval: pip install streamlit-js-eval")
from datetime import datetime

def save_markdown_content(content: str, filename: str, save_dir: str = "markdown_files") -> bool:
    """
    Save markdown content to a file.
    
    Args:
        content (str): Content to save
        filename (str): Name of the file
        save_dir (str): Directory to save the file in
        
    Returns:
        bool: True if save was successful, False otherwise
    """
    try:
        # Ensure directory exists
        os.makedirs(save_dir, exist_ok=True)
        
        # Add .md extension if not present
        if not filename.endswith('.md'):
            filename += '.md'
            
        filepath = os.path.join(save_dir, filename)
        
        # Save the content
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(content)
            
        return True
    except Exception as e:
        st.error(f"Error saving file: {str(e)}")
        return False

def render_markdown_editor(
    value: str = "",
    key: Optional[str] = None,
    height: int = 200,
    on_change: Optional[Callable] = None,
    placeholder: str = "Write your markdown here...",
    help_text: str = "You can use Markdown syntax.",
    preview: bool = True,
    show_submit_button: bool = False,
    submit_button_label: str = "Submit"
) -> tuple[str, bool]:
    """
    A reusable Markdown editor component with live preview.
    
    Args:
        value (str): Initial text value for the editor
        key (str, optional): Unique key for the component
        height (int): Height of the editor in pixels
        on_change (Callable, optional): Callback function when content changes
        placeholder (str): Placeholder text when editor is empty
        help_text (str): Help text shown below the editor
        preview (bool): Whether to show live preview
        show_submit_button (bool): Whether to show a submit button below the editor.
        submit_button_label (str): Label for the submit button.
        
    Returns:
        tuple[str, bool]: The current content of the editor and a boolean indicating if the submit button was clicked.
    """
    # Initialize session state for the editor if not exists
    if key is None:
        key = "markdown_editor"
        
    state_key = f"{key}_content"
    if state_key not in st.session_state:
        st.session_state[state_key] = value

    editor_area_container = st.container()

    with editor_area_container:
        # Create columns for editor and preview if preview is enabled
        if preview:
            # Adjust the ratios to create a gap.
            # For example, 47.5% for editor, 5% for gap, 47.5% for preview
            # The middle column (gap_col) will create the space.
            col1, gap_col, col2 = st.columns((0.49, 0.02, 0.49))
        else:
            col1 = st    # Markdown Editor

        with col1:
            content = st.text_area(
                "Editor",
                value=st.session_state[state_key],
                height=height,
                key=key, # Key for the text_area widget
                help=help_text,
                placeholder=placeholder,
                on_change=on_change if on_change else None
            )
            st.session_state[state_key] = content

        # Live Preview
        if preview:
            with col2:
                st.caption("Preview")
                st.markdown(content)

    submit_clicked = False
    if show_submit_button:
        # Place submit button below the editor_area_container
        submit_clicked = st.button(submit_button_label, key=f"{key}_submit", use_container_width=True)

    return content, submit_clicked


def render_markdown_editor_with_toolbar(
    value: str = "",
    key: Optional[str] = None,
    height: int = 200,
    on_change: Optional[Callable] = None,
    save_enabled: bool = True,
    filename: str = "",
    save_dir: str = "markdown_files",
    show_submit_button: bool = False,
    submit_button_label: str = "Submit"
) -> tuple[str, bool]:
    """
    Markdown editor with a formatting toolbar.
    
    Args:
        value (str): Initial text value for the editor
        key (str, optional): Unique key for the component
        height (int): Height of the editor in pixels
        on_change (Callable, optional): Callback function when content changes
        save_enabled (bool): Whether to enable save functionality.
        filename (str): Default filename for saving.
        save_dir (str): Directory to save markdown files.
        show_submit_button (bool): Whether to show a submit button below the editor.
        submit_button_label (str): Label for the submit button.
        
    Returns:
        tuple[str, bool]: The current content of the editor and a boolean indicating if the submit button was clicked.
    """
    # Initialize unique key
    if key is None:
        key = "markdown_editor_toolbar"
        
    state_key = f"{key}_content"
    if state_key not in st.session_state:
        st.session_state[state_key] = value

    # Markdown Syntax Help Expander
    with st.container():
        with st.expander("📝 Markdown Syntax Help", expanded=False):
            st.markdown("""
                - **Bold:** `**bold text**` or `__bold text__`
                - *Italic:* `*italic text*` or `_italic text_`
                - Strikethrough: `~~strikethrough~~`
                - `Code`: `` `inline code` ``
                - Link: `title`
                - Image: `!alt text`
                - Heading 1: `# H1`
                - Heading 2: `## H2`
                - Heading 3: `### H3`
                - Unordered List:
                    ```
                    - Item 1
                    - Item 2
                      - Sub-item
                    ```
                - Ordered List:
                    ```
                    1. First item
                    2. Second item
                    ```
                - Task List:
                    ```
                    - [x] Completed task
                    - [ ] Incomplete task
                    ```
                - Blockquote: `> blockquote`
                - Code Block:
                    ```
                    ```python
                    s = "Python code block"
                    print(s)
                    ```
                    ```
                - Table:
                    ```
                    | Header 1 | Header 2 |
                    |----------|----------|
                    | Cell 1   | Cell 2   |
                    ```
                - Horizontal Rule: `---` or `***`
            """)

    # Initialize submit_clicked status for the toolbar editor
    toolbar_submit_clicked = False

    # Editor and Preview
    # The submit button for the main editor area will NOT be rendered by the call below.
    # We are passing show_submit_button=False.
    content_after_action, _ = render_markdown_editor( # Inner submit_clicked is ignored
        value=st.session_state[state_key],
        key=f"{key}_main", # Unique key for the internal editor
        height=height,
        on_change=on_change,
        help_text="Write Markdown directly or see syntax help above.",
        show_submit_button=False, # Toolbar editor handles its own submit button
        # submit_button_label is not needed here
    )

    # Submit button for the toolbar editor (if enabled)
    # This button will be below the editor area and full-width.
    if show_submit_button:
        toolbar_submit_clicked = st.button(
            submit_button_label,
            key=f"{key}_toolbar_submit",
            use_container_width=True  # Make the button full-width
        )

    # Save functionality (if enabled) - appears below the submit button
    if save_enabled:
        st.markdown("---") # Visual separator
        save_col1, save_col2 = st.columns([3, 1]) # Layout for filename input and save button
        with save_col1:
            filename_input = st.text_input(
                "📄 Filename for Save",
                value=filename if filename else datetime.now().strftime("markdown_%Y%m%d_%H%M%S"),
                placeholder="Enter filename (e.g., my_document)",
                key=f"{key}_filename_input"
            )
        with save_col2:
            st.write("") # Spacer for vertical alignment
            st.write("") # Spacer for vertical alignment
            if st.button("💾 Save Markdown", key=f"{key}_save_button", help="Save current content to a .md file"):
                if filename_input:
                    if save_markdown_content(st.session_state[state_key], filename_input, save_dir):
                        st.success(f"✅ Content saved to '{os.path.join(save_dir, filename_input)}.md'")
                    else:
                        st.error("Save failed. Check logs.")
                else:
                    st.warning("Please enter a filename to save.")

    return content_after_action, toolbar_submit_clicked

# Example usage:
if __name__ == "__main__":
    st.set_page_config(page_title="Markdown Editor", page_icon="📝", layout="wide")
    
    st.title("📝 Markdown Editor Demo")
    
    # Only show the editor with toolbar in the demo
    with st.container(): # Using a container for the single "tab" content
        st.info("💡 Markdown editor with syntax help, save functionality, and a submit button.")
        content2, submitted2 = render_markdown_editor_with_toolbar(
            value="# Welcome\nThis editor has Markdown syntax help and save options.",
            key="demo_toolbar",
            save_enabled=True,
            filename="demo_document",
            height=300,
            show_submit_button=True,
            submit_button_label="Submit Formatted Content"
        )
        if submitted2:
            st.success(f"Toolbar editor content submitted: \n```markdown\n{content2}\n```")
            st.snow()

    st.markdown("---")
    st.subheader("Current Content (Toolbar Editor):")
    st.code(content2, language="markdown")
