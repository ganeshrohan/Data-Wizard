import streamlit as st
import uuid
from graph_rag.search.templet import mermaid_system_propmpt
import re

def render_mermaid(code: str) -> str:
    unique_id = f"mermaid_{uuid.uuid4().hex}"
    return f"""
    <style>
        body {{
            background-color: #0f111a;
            color: #e6edf3;
            font-family: 'Segoe UI', Tahoma, sans-serif;
        }}
        .mermaid-container {{
            border: 1px solid #2e3b4e;
            border-radius: 12px;
            background-color: #10151f;
            padding: 12px;
            overflow: hidden;
            box-shadow: 0 0 12px rgba(90,160,255,0.1);
        }}
        .diagram-title {{
            text-align: center;
            font-size: 2rem;
            font-weight: 500;
            margin-bottom: 1rem;
            color: #7ab3ff;
            letter-spacing: 1px;
        }}
    </style>

    <div class="diagram-title">Code Lineage</div>
    <div id="zoom-wrapper" class="mermaid-container">
        <div id="{unique_id}" class="mermaid">
{code}
        </div>
    </div>

    <script src="https://cdn.jsdelivr.net/npm/mermaid@10/dist/mermaid.min.js"></script>
    <script src="https://cdn.jsdelivr.net/npm/panzoom@9.4.0/dist/panzoom.min.js"></script>

    <script>
        mermaid.initialize({{
            startOnLoad: true,
            theme: "dark"
        }});

        setTimeout(() => {{
            const elem = document.getElementById("{unique_id}");
            if (elem) {{
                const zoomArea = panzoom(elem, {{
                    zoomSpeed: 0.065,
                    maxZoom: 5,
                    minZoom: 0.5,
                    bounds: true,
                    boundsPadding: 0.1,
                }});
                // Enable wheel-to-zoom
                elem.addEventListener("wheel", e => {{
                    if (e.ctrlKey) {{
                        e.preventDefault();
                        zoomArea.zoomWithWheel(e);
                    }}
                }});
            }}
        }}, 500);
    </script>
    """

def extract_mermaid_code(text):
    """
    Extracts the first Mermaid code block from the given text.
    
    Args:
        text (str): Input text containing Mermaid code block.
    
    Returns:
        str or None: Mermaid code (without the ```mermaid delimiters), or None if not found.
    """
    pattern = r"```mermaid\s+([\s\S]+?)```"
    match = re.search(pattern, text)
    if match:
        return match.group(1).strip()
    return None

# def code_lineage_response(code: str) -> str:
#     """
#     Generates a Mermaid diagram code from the provided code snippet.
#     Retries model_response with error message if rendering fails.
#     """
#     max_attempts = 2
#     lineage = None
#     error_message = None

#     for attempt in range(max_attempts):
#         if attempt == 0:
#             lineage_response = model_response(llm_only=False, system_context=mermaid_system_propmpt, context=code)
#         else:
#             # Add error message to context for LLM to fix the diagram
#             retry_context = f"{code}\n\n# Previous Mermaid diagram failed to render with error: {error_message or 'Unknown error'}\n# Please fix the Mermaid code."
#             lineage_response = model_response(llm_only=False, system_context=mermaid_system_propmpt, context=retry_context)
#         lineage = extract_mermaid_code(lineage_response)

#         try:
#             st.components.v1.html(render_mermaid(lineage), height=600, scrolling=False)
#             return  # Success, exit the function
#         except Exception as e:
#             error_message = str(e)
#             if attempt == max_attempts - 1:
#                 st.error("❌ There was an internal issue rendering the diagram after multiple attempts.")
