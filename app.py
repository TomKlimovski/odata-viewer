import streamlit as st
import xml.etree.ElementTree as ET
from odata_to_mermaid import parse_odata_file, generate_mermaid_diagram
import pandas as pd
from typing import Dict, List, Tuple

def parse_odata_metadata(xml_content: bytes) -> Tuple[Dict, Dict]:
    """Parse OData metadata and return both diagram data and detailed metadata."""
    # Parse the XML content
    root = ET.fromstring(xml_content)
    
    # Define namespaces
    ns = {
        'edmx': 'http://schemas.microsoft.com/ado/2007/06/edmx',
        'edm': 'http://schemas.microsoft.com/ado/2009/11/edm'
    }
    
    # Find the Schema element
    schema = root.find('.//edm:Schema', ns)
    if schema is None:
        raise ValueError("No Schema element found in the OData file")
    
    # Extract detailed metadata
    metadata = {
        'entities': [],
        'relationships': [],
        'keys': [],
        'navigation_properties': []
    }
    
    # Extract entity types with detailed information
    for entity_type in schema.findall('.//edm:EntityType', ns):
        entity_name = entity_type.get('Name')
        
        # Get keys
        keys = []
        key_element = entity_type.find('.//edm:Key', ns)
        if key_element is not None:
            for key_ref in key_element.findall('.//edm:PropertyRef', ns):
                keys.append(key_ref.get('Name'))
                metadata['keys'].append({
                    'Entity': entity_name,
                    'KeyProperty': key_ref.get('Name')
                })
        
        # Get properties
        properties = []
        for prop in entity_type.findall('.//edm:Property', ns):
            properties.append({
                'Entity': entity_name,
                'Name': prop.get('Name'),
                'Type': prop.get('Type'),
                'Nullable': prop.get('Nullable', 'true'),
                'MaxLength': prop.get('MaxLength'),
                'IsKey': prop.get('Name') in keys
            })
        metadata['entities'].append({
            'Name': entity_name,
            'Properties': properties
        })
        
        # Get navigation properties
        for nav_prop in entity_type.findall('.//edm:NavigationProperty', ns):
            metadata['navigation_properties'].append({
                'Entity': entity_name,
                'Name': nav_prop.get('Name'),
                'Relationship': nav_prop.get('Relationship'),
                'FromRole': nav_prop.get('FromRole'),
                'ToRole': nav_prop.get('ToRole')
            })
    
    # Extract relationships
    for assoc in schema.findall('.//edm:Association', ns):
        name = assoc.get('Name')
        ends = assoc.findall('.//edm:End', ns)
        if len(ends) == 2:
            metadata['relationships'].append({
                'Name': name,
                'FromEntity': ends[0].get('Type').split('.')[-1],
                'ToEntity': ends[1].get('Type').split('.')[-1],
                'FromMultiplicity': ends[0].get('Multiplicity', '1'),
                'ToMultiplicity': ends[1].get('Multiplicity', '1')
            })
    
    return metadata

def render_metadata_explorer(metadata: Dict):
    """Render the metadata explorer interface."""
    st.header("OData Metadata Explorer")
    
    # Create tabs for different aspects of metadata
    tabs = st.tabs(["Entities", "Keys", "Relationships", "Navigation Properties"])
    
    # Entities tab
    with tabs[0]:
        st.subheader("Entities and Properties")
        # Create a searchable dropdown for entities
        entity_names = [entity['Name'] for entity in metadata['entities']]
        selected_entity = st.selectbox("Select Entity", entity_names)
        
        # Show properties for selected entity
        for entity in metadata['entities']:
            if entity['Name'] == selected_entity:
                df = pd.DataFrame(entity['Properties'])
                st.dataframe(df)
    
    # Keys tab
    with tabs[1]:
        st.subheader("Primary Keys")
        df_keys = pd.DataFrame(metadata['keys'])
        st.dataframe(df_keys)
    
    # Relationships tab
    with tabs[2]:
        st.subheader("Relationships")
        df_relationships = pd.DataFrame(metadata['relationships'])
        st.dataframe(df_relationships)
    
    # Navigation Properties tab
    with tabs[3]:
        st.subheader("Navigation Properties")
        df_nav = pd.DataFrame(metadata['navigation_properties'])
        st.dataframe(df_nav)

def main():
    st.set_page_config(page_title="OData Viewer", layout="wide")
    
    # Add custom CSS for zoom controls and diagram container
    st.markdown("""
        <style>
        .diagram-container {
            overflow: auto;
            background: #f5f5f5;
            border-radius: 5px;
            padding: 10px;
            margin: 10px 0;
        }
        .zoom-controls {
            position: sticky;
            top: 0;
            background: white;
            padding: 10px;
            border-bottom: 1px solid #ddd;
            z-index: 1000;
        }
        .zoom-controls button {
            margin: 0 5px;
            padding: 5px 10px;
            border: 1px solid #ddd;
            border-radius: 4px;
            background: white;
            cursor: pointer;
        }
        .zoom-controls button:hover {
            background: #f0f0f0;
        }
        </style>
    """, unsafe_allow_html=True)
    
    st.title("OData Metadata Viewer")
    
    # Create tabs for diagram and explorer
    diagram_tab, explorer_tab = st.tabs(["ER Diagram", "Metadata Explorer"])
    
    # File uploader in the sidebar
    uploaded_file = st.sidebar.file_uploader("Upload OData metadata file", type=['xml'])
    
    if uploaded_file is not None:
        try:
            # Read the file content
            xml_content = uploaded_file.read()
            
            # Create a temporary file for parse_odata_file function
            import tempfile
            import os
            
            with tempfile.NamedTemporaryFile(delete=False, suffix='.xml') as tmp_file:
                tmp_file.write(xml_content)
                tmp_file_path = tmp_file.name
            
            try:
                # Parse metadata for both diagram and explorer
                metadata = parse_odata_metadata(xml_content)
                
                # Generate and display diagram in the first tab
                with diagram_tab:
                    st.header("Entity Relationship Diagram")
                    entities, relationships = parse_odata_file(tmp_file_path)
                    mermaid_diagram = generate_mermaid_diagram(entities, relationships)
                    
                    # Create HTML with Mermaid and zoom controls
                    html = f"""
                    <div class="diagram-container">
                        <div class="zoom-controls">
                            <button onclick="zoomIn()">Zoom In (+)</button>
                            <button onclick="zoomOut()">Zoom Out (-)</button>
                            <button onclick="resetZoom()">Reset Zoom (100%)</button>
                            <span id="zoom-level">100%</span>
                        </div>
                        <div id="diagram-wrapper">
                            <pre class="mermaid">
                            {mermaid_diagram}
                            </pre>
                        </div>
                    </div>
                    
                    <script type="module">
                        import mermaid from 'https://cdn.jsdelivr.net/npm/mermaid@10/dist/mermaid.esm.min.mjs';
                        
                        mermaid.initialize({{
                            startOnLoad: true,
                            theme: 'default',
                            securityLevel: 'loose',
                            er: {{
                                diagramPadding: 20,
                                layoutDirection: 'TB',
                                minEntityWidth: 100,
                                minEntityHeight: 75,
                                entityPadding: 15,
                                stroke: 'gray',
                                fill: 'white',
                                fontSize: 12
                            }}
                        }});
                        
                        // Add zoom functionality
                        window.currentZoom = 1;
                        window.zoomStep = 0.1;
                        
                        window.zoomIn = function() {{
                            window.currentZoom += window.zoomStep;
                            applyZoom();
                        }};
                        
                        window.zoomOut = function() {{
                            if (window.currentZoom > window.zoomStep) {{
                                window.currentZoom -= window.zoomStep;
                                applyZoom();
                            }}
                        }};
                        
                        window.resetZoom = function() {{
                            window.currentZoom = 1;
                            applyZoom();
                        }};
                        
                        function applyZoom() {{
                            const diagram = document.querySelector('#diagram-wrapper');
                            diagram.style.transform = `scale(${{window.currentZoom}})`;
                            diagram.style.transformOrigin = 'top left';
                            document.querySelector('#zoom-level').textContent = 
                                `${{Math.round(window.currentZoom * 100)}}%`;
                        }}
                    </script>
                    """
                    st.components.v1.html(html, height=800, scrolling=True)
                    
                    # Also show the raw diagram code with a toggle
                    with st.expander("Show Diagram Code"):
                        st.code(mermaid_diagram, language="mermaid")
                
                # Show metadata explorer in the second tab
                with explorer_tab:
                    render_metadata_explorer(metadata)
            
            finally:
                # Clean up the temporary file
                if os.path.exists(tmp_file_path):
                    os.unlink(tmp_file_path)
                    
        except Exception as e:
            st.error(f"Error processing file: {str(e)}")
            import traceback
            st.error(f"Detailed error: {traceback.format_exc()}")
    else:
        st.sidebar.info("Please upload an OData metadata file to begin.")
        with diagram_tab:
            st.info("Upload a file to view the ER diagram.")
        with explorer_tab:
            st.info("Upload a file to explore the metadata.")

if __name__ == "__main__":
    main() 