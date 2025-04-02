import streamlit as st
import xml.etree.ElementTree as ET
from odata_to_mermaid import parse_odata_file, generate_mermaid_diagram
import pandas as pd
from typing import Dict, List, Tuple

def parse_odata_metadata(xml_content: bytes) -> Tuple[Dict, Dict]:
    """Parse OData metadata and return both diagram data and detailed metadata."""
    # Parse the XML content
    root = ET.fromstring(xml_content)
    
    # Define namespaces - including SAP specific ones
    ns = {
        'edmx': 'http://schemas.microsoft.com/ado/2007/06/edmx',
        'edm': 'http://schemas.microsoft.com/ado/2009/11/edm',
        'm': 'http://schemas.microsoft.com/ado/2007/08/dataservices/metadata',
        'sap': 'http://www.successfactors.com/edm/sap',
        'sf': 'http://www.successfactors.com/edm/sf',
        # Add the namespace used in the SAP SF metadata XML
        'edm2008': 'http://schemas.microsoft.com/ado/2008/09/edm'
    }
    
    # Find all Schema elements - SAP files may have multiple Schema elements
    schema_elements = []
    
    # Try multiple approaches to find Schema elements
    # Approach 1: Find Schema with namespaces
    schema_elements.extend(root.findall('.//edm:Schema', ns))
    
    # Approach 2: Try the 2008 EDM namespace
    schema_elements.extend(root.findall('.//edm2008:Schema', ns))
    
    # Approach 3: Try with direct namespace URI
    schema_elements.extend(root.findall('.//{http://schemas.microsoft.com/ado/2008/09/edm}Schema'))
    
    # Approach 4: Try without namespace
    schema_elements.extend(root.findall('.//Schema'))
    
    # Approach 5: Try using XPath to search for Schema anywhere
    if not schema_elements:
        for elem in root.findall('.//*'):
            if elem.tag.endswith('Schema'):
                schema_elements.append(elem)
    
    if not schema_elements:
        raise ValueError("No Schema element found in the OData file")
    
    # Extract detailed metadata
    metadata = {
        'entities': [],
        'relationships': [],
        'keys': [],
        'navigation_properties': [],
        'tags': {}  # Add a new dictionary to store tag information
    }
    
    # First, extract entity sets to get labels and other SAP-specific metadata
    entity_sets = {}
    
    # Try with different approaches to find EntitySet
    entity_set_elements = []
    entity_set_elements.extend(root.findall('.//EntitySet'))
    entity_set_elements.extend(root.findall('.//{http://schemas.microsoft.com/ado/2008/09/edm}EntitySet'))
    entity_set_elements.extend(root.findall('.//edm:EntitySet', ns))
    entity_set_elements.extend(root.findall('.//edm2008:EntitySet', ns))
    
    for entity_set in entity_set_elements:
        entity_type = entity_set.get('EntityType', '')
        entity_name = entity_type.split('.')[-1] if entity_type else ''
        if entity_name:
            # Try different ways to get SAP label
            sap_label = entity_set.get('{http://www.successfactors.com/edm/sap}label')
            if sap_label is None:
                sap_label = entity_set.get('sap:label')
            
            # Extract tag collections - different approaches to find the tag collection
            entity_tags = []
            
            # Approach 1: Find sap:tagcollection with namespace
            tag_collection = entity_set.find('.//sap:tagcollection', ns)
            if tag_collection is not None:
                for tag_element in tag_collection.findall('.//sap:tag', ns):
                    if tag_element.text:
                        entity_tags.append(tag_element.text)
            
            # Approach 2: Try finding Documentation element first, then tagcollection
            doc_element = entity_set.find('.//Documentation')
            if doc_element is not None:
                tag_collection = doc_element.find('.//sap:tagcollection', ns)
                if tag_collection is not None:
                    for tag_element in tag_collection.findall('.//sap:tag', ns):
                        if tag_element.text and tag_element.text not in entity_tags:
                            entity_tags.append(tag_element.text)
            
            # Approach 3: Try without namespace
            doc_element = entity_set.find('.//Documentation')
            if doc_element is not None:
                tag_collection = doc_element.find('.//tagcollection')
                if tag_collection is not None:
                    for tag_element in tag_collection.findall('.//tag'):
                        if tag_element.text and tag_element.text not in entity_tags:
                            entity_tags.append(tag_element.text)
            
            entity_sets[entity_name] = {
                'Name': entity_set.get('Name'),
                'Label': sap_label,
                'Creatable': entity_set.get('{http://www.successfactors.com/edm/sap}creatable') or entity_set.get('sap:creatable'),
                'Updatable': entity_set.get('{http://www.successfactors.com/edm/sap}updatable') or entity_set.get('sap:updatable'),
                'Deletable': entity_set.get('{http://www.successfactors.com/edm/sap}deletable') or entity_set.get('sap:deletable'),
                'Tags': entity_tags  # Add the tags to the entity set metadata
            }
            
            # Update the tags dictionary to track entities by tag
            for tag in entity_tags:
                if tag not in metadata['tags']:
                    metadata['tags'][tag] = []
                if entity_name not in metadata['tags'][tag]:
                    metadata['tags'][tag].append(entity_name)
    
    # Collect all entity types and associations from all schemas
    all_entity_type_elements = []
    all_assoc_elements = []
    
    # Process each schema to collect entity types and associations
    for schema in schema_elements:
        # Find EntityType elements using multiple approaches
        entity_type_elements = []
        entity_type_elements.extend(schema.findall('./EntityType'))
        entity_type_elements.extend(schema.findall('.//EntityType'))
        entity_type_elements.extend(schema.findall('.//{http://schemas.microsoft.com/ado/2008/09/edm}EntityType'))
        entity_type_elements.extend(schema.findall('.//edm:EntityType', ns))
        entity_type_elements.extend(schema.findall('.//edm2008:EntityType', ns))
        
        # Add to our collection
        all_entity_type_elements.extend(entity_type_elements)
        
        # Find Association elements for this schema
        assoc_elements = []
        assoc_elements.extend(schema.findall('./Association'))
        assoc_elements.extend(schema.findall('.//Association'))
        assoc_elements.extend(schema.findall('.//{http://schemas.microsoft.com/ado/2008/09/edm}Association'))
        assoc_elements.extend(schema.findall('.//edm:Association', ns))
        assoc_elements.extend(schema.findall('.//edm2008:Association', ns))
        
        # Add to our collection
        all_assoc_elements.extend(assoc_elements)
    
    # Extract entity types with detailed information
    for entity_type in all_entity_type_elements:
        entity_name = entity_type.get('Name')
        if not entity_name:
            continue
            
        # Get entity label and other metadata if available
        entity_label = None
        entity_metadata = {}
        entity_tags = []
        if entity_name in entity_sets:
            entity_label = entity_sets[entity_name].get('Label')
            entity_metadata = entity_sets[entity_name]
            entity_tags = entity_sets[entity_name].get('Tags', [])
        
        # Get keys using multiple approaches
        keys = []
        key_elements = []
        key_elements.extend(entity_type.findall('./Key'))
        key_elements.extend(entity_type.findall('.//Key'))
        key_elements.extend(entity_type.findall('.//{http://schemas.microsoft.com/ado/2008/09/edm}Key'))
        key_elements.extend(entity_type.findall('.//edm:Key', ns))
        key_elements.extend(entity_type.findall('.//edm2008:Key', ns))
        
        key_element = key_elements[0] if key_elements else None
        
        if key_element is not None:
            prop_ref_elements = []
            prop_ref_elements.extend(key_element.findall('./PropertyRef'))
            prop_ref_elements.extend(key_element.findall('.//PropertyRef'))
            prop_ref_elements.extend(key_element.findall('.//{http://schemas.microsoft.com/ado/2008/09/edm}PropertyRef'))
            prop_ref_elements.extend(key_element.findall('.//edm:PropertyRef', ns))
            prop_ref_elements.extend(key_element.findall('.//edm2008:PropertyRef', ns))
            
            for key_ref in prop_ref_elements:
                key_name = key_ref.get('Name')
                if key_name:
                    keys.append(key_name)
                    metadata['keys'].append({
                        'Entity': entity_name,
                        'EntityLabel': entity_label,
                        'KeyProperty': key_name
                    })
        
        # Get properties using multiple approaches
        properties = []
        prop_elements = []
        prop_elements.extend(entity_type.findall('./Property'))
        prop_elements.extend(entity_type.findall('.//Property'))
        prop_elements.extend(entity_type.findall('.//{http://schemas.microsoft.com/ado/2008/09/edm}Property'))
        prop_elements.extend(entity_type.findall('.//edm:Property', ns))
        prop_elements.extend(entity_type.findall('.//edm2008:Property', ns))
        
        for prop in prop_elements:
            prop_name = prop.get('Name')
            if not prop_name:
                continue
                
            prop_type_full = prop.get('Type', 'Edm.String')
            
            # Extract SAP-specific attributes using different approaches
            sap_label = prop.get('{http://www.successfactors.com/edm/sap}label')
            if sap_label is None:
                sap_label = prop.get('sap:label')
                
            sap_required = prop.get('{http://www.successfactors.com/edm/sap}required', 'false')
            if sap_required is None:
                sap_required = prop.get('sap:required', 'false')
                
            sap_creatable = prop.get('{http://www.successfactors.com/edm/sap}creatable', 'true')
            if sap_creatable is None:
                sap_creatable = prop.get('sap:creatable', 'true')
                
            sap_updatable = prop.get('{http://www.successfactors.com/edm/sap}updatable', 'true')
            if sap_updatable is None:
                sap_updatable = prop.get('sap:updatable', 'true')
                
            sap_filterable = prop.get('{http://www.successfactors.com/edm/sap}filterable', 'true')
            if sap_filterable is None:
                sap_filterable = prop.get('sap:filterable', 'true')
            
            properties.append({
                'Entity': entity_name,
                'Name': prop_name,
                'Type': prop_type_full,
                'Nullable': prop.get('Nullable', 'true'),
                'MaxLength': prop.get('MaxLength'),
                'Label': sap_label if sap_label else prop_name,
                'Required': sap_required,
                'Creatable': sap_creatable,
                'Updatable': sap_updatable,
                'Filterable': sap_filterable,
                'IsKey': prop_name in keys
            })
        
        # Only add entity if it has properties
        if properties:
            # Create entity entry with additional SAP metadata
            entity_entry = {
                'Name': entity_name,
                'Label': entity_label,
                'Properties': properties,
                'Tags': entity_tags  # Add tags to the entity entry
            }
            # Add additional SAP metadata if available
            if entity_metadata:
                entity_entry.update({
                    'SetName': entity_metadata.get('Name'),
                    'Creatable': entity_metadata.get('Creatable'),
                    'Updatable': entity_metadata.get('Updatable'),
                    'Deletable': entity_metadata.get('Deletable')
                })
            
            metadata['entities'].append(entity_entry)
        
        # Get navigation properties using multiple approaches
        nav_prop_elements = []
        nav_prop_elements.extend(entity_type.findall('./NavigationProperty'))
        nav_prop_elements.extend(entity_type.findall('.//NavigationProperty'))
        nav_prop_elements.extend(entity_type.findall('.//{http://schemas.microsoft.com/ado/2008/09/edm}NavigationProperty'))
        nav_prop_elements.extend(entity_type.findall('.//edm:NavigationProperty', ns))
        nav_prop_elements.extend(entity_type.findall('.//edm2008:NavigationProperty', ns))
        
        for nav_prop in nav_prop_elements:
            nav_name = nav_prop.get('Name')
            if not nav_name:
                continue
                
            relationship = nav_prop.get('Relationship', '')
            from_role = nav_prop.get('FromRole', '')
            to_role = nav_prop.get('ToRole', '')
            
            # Extract SAP-specific attributes
            sap_label = nav_prop.get('{http://www.successfactors.com/edm/sap}label')
            if sap_label is None:
                sap_label = nav_prop.get('sap:label')
            
            metadata['navigation_properties'].append({
                'Entity': entity_name,
                'Name': nav_name,
                'Relationship': relationship,
                'FromRole': from_role,
                'ToRole': to_role,
                'Label': sap_label if sap_label else nav_name
            })
    
    # Extract relationships using multiple approaches
    for assoc in all_assoc_elements:
        name = assoc.get('Name')
        if not name:
            continue
            
        # Find End elements using multiple approaches
        end_elements = []
        end_elements.extend(assoc.findall('./End'))
        end_elements.extend(assoc.findall('.//End'))
        end_elements.extend(assoc.findall('.//{http://schemas.microsoft.com/ado/2008/09/edm}End'))
        end_elements.extend(assoc.findall('.//edm:End', ns))
        end_elements.extend(assoc.findall('.//edm2008:End', ns))
        
        if len(end_elements) == 2:
            # Extract entity names from type
            from_entity_full = end_elements[0].get('Type', '')
            to_entity_full = end_elements[1].get('Type', '')
            from_entity = from_entity_full.split('.')[-1] if from_entity_full else ''
            to_entity = to_entity_full.split('.')[-1] if to_entity_full else ''
            
            if not from_entity or not to_entity:
                continue
            
            # Check if these entities exist in our metadata
            entity_names = [e['Name'] for e in metadata['entities']]
            if from_entity not in entity_names or to_entity not in entity_names:
                continue
                
            # Get labels if available
            from_label = entity_sets.get(from_entity, {}).get('Label', from_entity)
            to_label = entity_sets.get(to_entity, {}).get('Label', to_entity)
            
            metadata['relationships'].append({
                'Name': name,
                'FromEntity': from_entity,
                'ToEntity': to_entity,
                'FromLabel': from_label,
                'ToLabel': to_label,
                'FromMultiplicity': end_elements[0].get('Multiplicity', '1'),
                'ToMultiplicity': end_elements[1].get('Multiplicity', '1')
            })
    
    return metadata

def render_metadata_explorer(metadata: Dict):
    """Render the metadata explorer interface."""
    st.header("OData Metadata Explorer")
    
    # Create tabs for different aspects of metadata
    tabs = st.tabs(["Entities", "Tags", "Keys", "Relationships", "Navigation Properties"])
    
    # Entities tab
    with tabs[0]:
        st.subheader("Entities and Properties")
        
        # Get all entity names with labels for better display
        entity_options = []
        for entity in metadata['entities']:
            # Get display name with label if available
            display_name = entity.get('Label') if entity.get('Label') else entity['Name']
            
            # Create display option (without type prefix)
            prefixed_display = f"{display_name} ({entity['Name']})"
            
            entity_options.append({"name": entity['Name'], "display": prefixed_display})
        
        # Sort entities by display name
        entity_options.sort(key=lambda x: x['display'].lower())
        
        # Add Select All functionality
        col1, col2 = st.columns([1, 3])
        with col1:
            select_all = st.checkbox("Select All Entities")
        
        # Entity selection
        if select_all:
            selected_entities = [e['name'] for e in entity_options]
            with col2:
                st.multiselect(
                    "Select Entities", 
                    options=[e['display'] for e in entity_options], 
                    default=[e['display'] for e in entity_options], 
                    disabled=True, 
                    label_visibility="collapsed"
                )
        else:
            with col2:
                # Use the display values for the UI but track the actual entity names
                display_to_name = {e['display']: e['name'] for e in entity_options}
                selected_displays = st.multiselect(
                    "Select Entities", 
                    options=[e['display'] for e in entity_options],
                    label_visibility="collapsed"
                )
                selected_entities = [display_to_name[display] for display in selected_displays]
        
        # Display selected entities
        if not selected_entities:
            st.info("Please select at least one entity to view its properties")
        else:
            # For a single entity, don't use expanders
            if len(selected_entities) == 1:
                selected_entity = selected_entities[0]
                for entity in metadata['entities']:
                    if entity['Name'] == selected_entity:
                        # Show entity metadata
                        cols = st.columns([1, 1, 1, 1])
                        cols[0].metric("Entity Name", entity['Name'])
                        cols[1].metric("Label", entity.get('Label', 'N/A'))
                        cols[2].metric("Creatable", entity.get('Creatable', 'N/A'))
                        cols[3].metric("Updatable", entity.get('Updatable', 'N/A'))
                        
                        # Show tags if available
                        if entity.get('Tags') and len(entity['Tags']) > 0:
                            st.subheader("Tags")
                            tags_html = " ".join([f'<span class="tag">{tag}</span>' for tag in entity['Tags']])
                            st.markdown(f"""
                            <div class="tag-container">
                                {tags_html}
                            </div>
                            <style>
                            .tag-container {{ display: flex; flex-wrap: wrap; gap: 8px; margin-bottom: 16px; }}
                            .tag {{ background-color: #f0f2f6; border-radius: 16px; padding: 4px 12px; font-size: 0.9em; }}
                            </style>
                            """, unsafe_allow_html=True)
                        
                        # Show properties with enhanced columns
                        st.subheader("Properties")
                        df = pd.DataFrame(entity['Properties'])
                        # Reorder and select columns for better display
                        if not df.empty:
                            display_cols = ['Name', 'Label', 'Type', 'IsKey', 'Nullable', 'Required', 
                                           'Creatable', 'Updatable', 'Filterable', 'MaxLength']
                            display_cols = [col for col in display_cols if col in df.columns]
                            df = df[display_cols]
                        st.dataframe(df, use_container_width=True)
            else:
                # For multiple entities, use expanders
                for selected_entity in selected_entities:
                    entity_data = next((e for e in metadata['entities'] if e['Name'] == selected_entity), None)
                    if entity_data:
                        # Use label and name in the expander title
                        display_name = entity_data.get('Label', entity_data['Name'])
                        with st.expander(f"{display_name} ({entity_data['Name']})"):
                            # Show entity metadata
                            cols = st.columns([1, 1, 1, 1])
                            cols[0].metric("Entity Name", entity_data['Name'])
                            cols[1].metric("Label", entity_data.get('Label', 'N/A'))
                            cols[2].metric("Creatable", entity_data.get('Creatable', 'N/A'))
                            cols[3].metric("Updatable", entity_data.get('Updatable', 'N/A'))
                            
                            # Show tags if available
                            if entity_data.get('Tags') and len(entity_data['Tags']) > 0:
                                st.subheader("Tags")
                                tags_html = " ".join([f'<span class="tag">{tag}</span>' for tag in entity_data['Tags']])
                                st.markdown(f"""
                                <div class="tag-container">
                                    {tags_html}
                                </div>
                                <style>
                                .tag-container {{ display: flex; flex-wrap: wrap; gap: 8px; margin-bottom: 16px; }}
                                .tag {{ background-color: #f0f2f6; border-radius: 16px; padding: 4px 12px; font-size: 0.9em; }}
                                </style>
                                """, unsafe_allow_html=True)
                            
                            # Show properties
                            st.subheader("Properties")
                            df = pd.DataFrame(entity_data['Properties'])
                            # Reorder and select columns for better display
                            if not df.empty:
                                display_cols = ['Name', 'Label', 'Type', 'IsKey', 'Nullable', 'Required', 
                                               'Creatable', 'Updatable', 'Filterable', 'MaxLength']
                                display_cols = [col for col in display_cols if col in df.columns]
                                df = df[display_cols]
                            st.dataframe(df, use_container_width=True)
    
    # New Tags tab
    with tabs[1]:
        st.subheader("Entities by Tag")
        
        # Get all unique tags and sort them
        all_tags = list(metadata['tags'].keys())
        all_tags.sort()
        
        if not all_tags:
            st.info("No tags found in the metadata")
        else:
            # Tag selection
            selected_tag = st.selectbox("Select a tag to view entities", options=all_tags)
            
            if selected_tag:
                entities_with_tag = metadata['tags'][selected_tag]
                st.success(f"Found {len(entities_with_tag)} entities with tag '{selected_tag}'")
                
                # Create a dataframe with entities having this tag
                tag_entities_data = []
                for entity_name in entities_with_tag:
                    entity_data = next((e for e in metadata['entities'] if e['Name'] == entity_name), None)
                    if entity_data:
                        tag_entities_data.append({
                            'Name': entity_data['Name'],
                            'Label': entity_data.get('Label', 'N/A'),
                            'Creatable': entity_data.get('Creatable', 'N/A'),
                            'Updatable': entity_data.get('Updatable', 'N/A'),
                            'Deletable': entity_data.get('Deletable', 'N/A'),
                            'Properties Count': len(entity_data.get('Properties', [])),
                            'All Tags': ', '.join(entity_data.get('Tags', []))
                        })
                
                # Sort by name
                tag_entities_data.sort(key=lambda x: x['Name'])
                df_tag_entities = pd.DataFrame(tag_entities_data)
                st.dataframe(df_tag_entities, use_container_width=True)
                
                # Add ability to view details for a selected entity
                entity_options = [e['Name'] for e in tag_entities_data]
                if entity_options:
                    selected_entity = st.selectbox("Select an entity to view details", options=entity_options)
                    if selected_entity:
                        entity_data = next((e for e in metadata['entities'] if e['Name'] == selected_entity), None)
                        if entity_data:
                            st.subheader(f"Entity Details: {entity_data['Name']}")
                            
                            # Show entity metadata
                            cols = st.columns([1, 1, 1, 1])
                            cols[0].metric("Entity Name", entity_data['Name'])
                            cols[1].metric("Label", entity_data.get('Label', 'N/A'))
                            cols[2].metric("Creatable", entity_data.get('Creatable', 'N/A'))
                            cols[3].metric("Updatable", entity_data.get('Updatable', 'N/A'))
                            
                            # Show properties
                            st.subheader("Properties")
                            df = pd.DataFrame(entity_data['Properties'])
                            if not df.empty:
                                display_cols = ['Name', 'Label', 'Type', 'IsKey', 'Nullable', 'Required', 
                                               'Creatable', 'Updatable', 'Filterable', 'MaxLength']
                                display_cols = [col for col in display_cols if col in df.columns]
                                df = df[display_cols]
                            st.dataframe(df, use_container_width=True)
    
    # Keys tab
    with tabs[2]:
        st.subheader("Primary Keys")
        df_keys = pd.DataFrame(metadata['keys'])
        if not df_keys.empty:
            # Reorder columns for better display
            display_cols = ['Entity', 'EntityLabel', 'KeyProperty']
            display_cols = [col for col in display_cols if col in df_keys.columns]
            df_keys = df_keys[display_cols]
            
            # Sort by Entity and KeyProperty
            if 'Entity' in df_keys.columns:
                df_keys = df_keys.sort_values(by=['Entity', 'KeyProperty'])
                
        st.dataframe(df_keys, use_container_width=True)
    
    # Relationships tab
    with tabs[3]:
        st.subheader("Relationships")
        df_relationships = pd.DataFrame(metadata['relationships'])
        if not df_relationships.empty:
            # Reorder columns for better display
            display_cols = ['Name', 'FromEntity', 'FromLabel', 'ToEntity', 'ToLabel', 
                           'FromMultiplicity', 'ToMultiplicity']
            display_cols = [col for col in display_cols if col in df_relationships.columns]
            df_relationships = df_relationships[display_cols]
            
            # Sort by FromEntity and then ToEntity
            if 'FromEntity' in df_relationships.columns:
                df_relationships = df_relationships.sort_values(by=['FromEntity', 'ToEntity'])
        
        st.dataframe(df_relationships, use_container_width=True)
    
    # Navigation Properties tab
    with tabs[4]:
        st.subheader("Navigation Properties")
        df_nav = pd.DataFrame(metadata['navigation_properties'])
        if not df_nav.empty:
            # Reorder columns for better display
            display_cols = ['Entity', 'Name', 'Label', 'Relationship', 'FromRole', 'ToRole']
            display_cols = [col for col in display_cols if col in df_nav.columns]
            df_nav = df_nav[display_cols]
            
            # Sort by Entity and Name
            if 'Entity' in df_nav.columns:
                df_nav = df_nav.sort_values(by=['Entity', 'Name'])
                
        st.dataframe(df_nav, use_container_width=True)

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
        .sap-entity {
            color: #0066cc;
            font-weight: bold;
        }
        </style>
    """, unsafe_allow_html=True)
    
    st.title("OData Metadata Viewer")
    
    # Create tabs for diagram and explorer
    diagram_tab, explorer_tab = st.tabs(["ER Diagram", "Metadata Explorer"])
    
    # File uploader in the sidebar
    st.sidebar.title("Upload OData File")
    st.sidebar.info("📂 Upload your OData metadata XML file to visualize and explore it")
    uploaded_file = st.sidebar.file_uploader("Upload OData metadata file", type=['xml'])
    
    # Add info about supported formats
    with st.sidebar.expander("ℹ️ Supported Formats"):
        st.write("""
        This tool supports standard OData metadata XML files as well as SAP SuccessFactors specific OData metadata.
        
        For SAP SuccessFactors, the tool will extract:
        - Entity metadata with SAP labels
        - Property details with SAP annotations
        - Relationships defined via Associations and NavigationProperties
        """)
    
    if uploaded_file is not None:
        try:
            # Show file info
            file_size = len(uploaded_file.getvalue()) / (1024 * 1024)  # Size in MB
            st.sidebar.success(f"File uploaded: {uploaded_file.name} ({file_size:.2f} MB)")
            
            # Add a progress bar for large files
            if file_size > 1.0:
                progress_text = "Processing large file... This may take a minute."
                progress_bar = st.sidebar.progress(0)
                st.sidebar.warning(f"Large file detected ({file_size:.2f} MB). Processing may take longer.")
            
            # Read the file content
            xml_content = uploaded_file.read()
            
            # Update progress
            if file_size > 1.0:
                progress_bar.progress(20, text=f"{progress_text} (Reading file)")
            
            # Create a temporary file for parse_odata_file function
            import tempfile
            import os
            
            with tempfile.NamedTemporaryFile(delete=False, suffix='.xml') as tmp_file:
                tmp_file.write(xml_content)
                tmp_file_path = tmp_file.name
            
            try:
                # Update progress
                if file_size > 1.0:
                    progress_bar.progress(40, text=f"{progress_text} (Parsing metadata)")
                
                # Parse metadata for diagram
                try:
                    # First detect if it's an SAP-specific file
                    is_sap_format = b'successfactors.com' in xml_content
                    if is_sap_format:
                        st.sidebar.info("SAP SuccessFactors OData format detected")
                    
                    # Parse metadata
                    metadata = parse_odata_metadata(xml_content)
                    
                    # Update progress
                    if file_size > 1.0:
                        progress_bar.progress(70, text=f"{progress_text} (Generating diagram)")
                
                    # Generate and display diagram in the first tab
                    with diagram_tab:
                        st.header("Entity Relationship Diagram")
                        
                        # Add filter for large models
                        if len(metadata['entities']) > 50:
                            st.warning(f"Large model detected with {len(metadata['entities'])} entities. Consider filtering to improve diagram readability.")
                            
                            # For very large models, add a search box to find entities more easily
                            if len(metadata['entities']) > 200:
                                search_term = st.text_input("Search for entities to include:", 
                                                            help="Enter part of an entity name to filter the list below")
                                
                                # Create entity options without type prefixes
                                entity_options = []
                                for e in metadata['entities']:
                                    # Create a display name without the type prefix
                                    display_name = e['Name']
                                    
                                    # Add to options
                                    entity_options.append({
                                        "name": e['Name'],
                                        "display": display_name
                                    })
                                
                                # Sort options by display name
                                entity_options.sort(key=lambda x: x["display"])
                                
                                # Filter based on search term if provided
                                if search_term:
                                    entity_options = [opt for opt in entity_options 
                                                    if search_term.lower() in opt["name"].lower()]
                                
                                # Add a note about the search results
                                if search_term and entity_options:
                                    st.success(f"Found {len(entity_options)} entities matching '{search_term}'")
                                elif search_term:
                                    st.error(f"No entities found matching '{search_term}'")
                            else:
                                # Create entity options without type prefixes
                                entity_options = []
                                for e in metadata['entities']:
                                    # Create a display name without the type prefix
                                    display_name = e['Name']
                                    
                                    # Add to options
                                    entity_options.append({
                                        "name": e['Name'],
                                        "display": display_name
                                    })
                                
                                # Sort options by display name
                                entity_options.sort(key=lambda x: x["display"])
                            
                            # Create a mapping from display name to actual entity name
                            display_to_name = {opt["display"]: opt["name"] for opt in entity_options}
                            
                            # Add entity filter for diagram using display names
                            selected_displays = st.multiselect(
                                "Filter diagram to include only specific entities:",
                                options=[opt["display"] for opt in entity_options],
                                help="For large models, select specific entities to include in the diagram"
                            )
                            
                            # Convert selected display names back to actual entity names
                            entity_filter = [display_to_name[display] for display in selected_displays]
                            
                            # Add option to include related entities
                            include_related = False
                            if entity_filter:
                                include_related = st.checkbox(
                                    "Include directly related entities", 
                                    value=True,
                                    help="When checked, entities that have relationships with selected entities will also be included"
                                )
                        else:
                            entity_filter = None
                        
                        # Parse file and generate diagram
                        entities, relationships = parse_odata_file(tmp_file_path)
                        
                        # Apply entity filter if needed
                        if entity_filter and len(entity_filter) > 0:
                            # Start with selected entities
                            filtered_entities = {k: v for k, v in entities.items() if k in entity_filter}
                            
                            # If include_related is checked, add directly related entities
                            related_entities = set()
                            if include_related:
                                for rel in relationships:
                                    from_entity, to_entity = rel[0], rel[1]
                                    if from_entity in entity_filter and to_entity not in entity_filter:
                                        related_entities.add(to_entity)
                                    elif to_entity in entity_filter and from_entity not in entity_filter:
                                        related_entities.add(from_entity)
                                
                                # Add the related entities to the filtered set
                                for related in related_entities:
                                    if related in entities:
                                        filtered_entities[related] = entities[related]
                            
                            # Filter relationships to only include selected entities and their related ones
                            filtered_relationships = []
                            for rel in relationships:
                                from_entity, to_entity = rel[0], rel[1]
                                if from_entity in filtered_entities and to_entity in filtered_entities:
                                    filtered_relationships.append(rel)
                            
                            st.info(f"Showing {len(filtered_entities)} entities and {len(filtered_relationships)} relationships")
                            mermaid_diagram = generate_mermaid_diagram(filtered_entities, filtered_relationships)
                        else:
                            # For large models, default to a sample of entities if none selected
                            if len(entities) > 200 and not entity_filter:
                                st.warning("No entities selected. Showing a sample of entities for this large model.")
                                # Take a sample of the entities (first 25) to avoid rendering issues
                                sample_count = min(25, len(entities))
                                sample_entities = {k: entities[k] for k in list(entities.keys())[:sample_count]}
                                
                                # Only include relationships between sampled entities
                                sample_relationships = []
                                for rel in relationships:
                                    from_entity, to_entity = rel[0], rel[1]
                                    if from_entity in sample_entities and to_entity in sample_entities:
                                        sample_relationships.append(rel)
                                
                                mermaid_diagram = generate_mermaid_diagram(sample_entities, sample_relationships)
                                st.info(f"Showing a sample of {len(sample_entities)} entities and {len(sample_relationships)} relationships")
                            else:
                                mermaid_diagram = generate_mermaid_diagram(entities, relationships)
                                st.info(f"Showing all {len(entities)} entities and {len(relationships)} relationships")
                        
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
                                }},
                                maxTextSize: 150000 // Set max text size to handle large diagrams
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

                            // Add error handling for Mermaid rendering
                            window.addEventListener('error', function(e) {{
                                if (e.message.includes('Mermaid')) {{
                                    document.querySelector('#diagram-wrapper').innerHTML = 
                                        '<div class="alert alert-danger">Error rendering diagram. Try filtering to fewer entities.</div>';
                                }}
                            }});
                        </script>
                        """
                        st.components.v1.html(html, height=800, scrolling=True)
                        
                        # Show diagram stats
                        st.info(f"Diagram contains {len(entities)} entities and {len(relationships)} relationships")
                        
                        # Also show the raw diagram code with a toggle
                        with st.expander("Show Diagram Code"):
                            st.code(mermaid_diagram, language="mermaid")
                    
                    # Update progress
                    if file_size > 1.0:
                        progress_bar.progress(90, text=f"{progress_text} (Building explorer interface)")
                    
                    # Show metadata explorer in the second tab
                    with explorer_tab:
                        render_metadata_explorer(metadata)
                    
                    # Complete progress
                    if file_size > 1.0:
                        progress_bar.progress(100, text="Processing complete!")
                        
                except Exception as e:
                    st.error(f"Error processing OData metadata: {str(e)}")
                    raise e
            
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
            
            # Add sample visualization
            st.markdown("""
            ## Sample ER Diagram
            Once you upload an OData metadata file, you'll see a diagram like this:
            """)
            
            sample_mermaid = """
            erDiagram
                Employee {
                    String id
                    String firstName
                    String lastName
                    Date hireDate
                }
                Department {
                    String id
                    String name
                    String location
                }
                Employee ||--|| Department : belongsTo
            """
            
            # Display sample diagram
            st.markdown(f"```mermaid\n{sample_mermaid}\n```")
            
        with explorer_tab:
            st.info("Upload a file to explore the metadata.")
            st.markdown("""
            ## Metadata Explorer
            The explorer allows you to:
            - Browse entities and their properties
            - View relationships between entities
            - Examine navigation properties and keys
            - See SAP-specific metadata attributes
            """)

if __name__ == "__main__":
    main() 