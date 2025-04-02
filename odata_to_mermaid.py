#!/usr/bin/env python3
import xml.etree.ElementTree as ET
import sys
from typing import Dict, List, Tuple

def parse_odata_file(file_path: str) -> Tuple[Dict, List]:
    """Parse OData XML file and extract entity types and relationships."""
    tree = ET.parse(file_path)
    root = tree.getroot()
    
    # Define namespaces - include SAP specific ones
    ns = {
        'edmx': 'http://schemas.microsoft.com/ado/2007/06/edmx',
        'edm': 'http://schemas.microsoft.com/ado/2009/11/edm',
        'm': 'http://schemas.microsoft.com/ado/2007/08/dataservices/metadata',
        'sap': 'http://www.successfactors.com/edm/sap',
        'sf': 'http://www.successfactors.com/edm/sf',
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
    
    # Extract entity types
    entities = {}
    
    # Initialize a list to collect all entity types from all schemas
    all_entity_type_elements = []
    
    # Initialize a list to collect all association elements from all schemas
    all_assoc_elements = []
    
    # Process each schema element
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
    
    # Find all EntitySet elements across the entire document
    entity_set_elements = []
    entity_set_elements.extend(root.findall('.//EntitySet'))
    entity_set_elements.extend(root.findall('.//{http://schemas.microsoft.com/ado/2008/09/edm}EntitySet'))
    entity_set_elements.extend(root.findall('.//edm:EntitySet', ns))
    entity_set_elements.extend(root.findall('.//edm2008:EntitySet', ns))
    
    # Create a map of entity types to their entity sets
    entity_set_map = {}
    for entity_set in entity_set_elements:
        entity_type_attr = entity_set.get('EntityType', '')
        if entity_type_attr:
            entity_name = entity_type_attr.split('.')[-1]
            # Try different ways to get SAP label
            sap_label = entity_set.get('{http://www.successfactors.com/edm/sap}label')
            if sap_label is None:
                sap_label = entity_set.get('sap:label')
            
            entity_set_map[entity_name] = {
                'label': sap_label,
                'entity_set': entity_set
            }
    
    # Process all entity types from all schemas
    for entity_type in all_entity_type_elements:
        name = entity_type.get('Name')
        if not name:
            continue
            
        properties = []
        
        # Get label for entity if available
        entity_label = None
        if name in entity_set_map:
            entity_label = entity_set_map[name].get('label')
        
        # Get keys using multiple approaches
        key_props = set()
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
                    key_props.add(key_name)
        
        # Get properties using multiple approaches
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
            prop_type = prop_type_full.split('.')[-1]  # Just use the type name without Edm prefix
            nullable = prop.get('Nullable', 'true')
            
            # Get additional SAP metadata
            sap_label = prop.get('{http://www.successfactors.com/edm/sap}label')
            if sap_label is None:
                sap_label = prop.get('sap:label')
            display_name = sap_label if sap_label else prop_name
            
            # Mark key properties
            is_key = prop_name in key_props
            
            # Add extra indicator for key fields
            if is_key:
                prop_name = f"{prop_name} (PK)"
                
            properties.append((prop_name, prop_type, nullable))
        
        # Only add this entity if it has properties
        if properties:
            entities[name] = properties
    
    # Create a map of association names to their association elements for faster lookup
    assoc_map = {}
    for assoc in all_assoc_elements:
        name = assoc.get('Name')
        if name:
            # Store the association by its name
            assoc_map[name] = assoc
            
            # Also try to find the schema namespace
            schema_namespace = None
            # Check if parent has a namespace attribute
            parent = assoc.getparent() if hasattr(assoc, 'getparent') else None
            if parent is not None and parent.get('Namespace'):
                schema_namespace = parent.get('Namespace')
            
            # If we have a namespace, store with fully qualified name too
            if schema_namespace:
                full_name = f"{schema_namespace}.{name}"
                assoc_map[full_name] = assoc
    
    # Extract relationships
    relationships = []
    
    # Method 1: From Association elements
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
            from_entity_full = end_elements[0].get('Type', '')
            to_entity_full = end_elements[1].get('Type', '')
            from_entity = from_entity_full.split('.')[-1] if from_entity_full else ''
            to_entity = to_entity_full.split('.')[-1] if to_entity_full else ''
            from_mult = end_elements[0].get('Multiplicity', '1')
            to_mult = end_elements[1].get('Multiplicity', '1')
            
            # Only add relationships if both entities exist in our entities dictionary
            if from_entity and to_entity and from_entity in entities and to_entity in entities:
                relationships.append((from_entity, to_entity, from_mult, to_mult))
    
    # Method 2: From NavigationProperty elements - improved to handle various relationship formats
    for entity_type in all_entity_type_elements:
        entity_name = entity_type.get('Name')
        if not entity_name or entity_name not in entities:
            continue
            
        # Get navigation properties using multiple approaches
        nav_prop_elements = []
        nav_prop_elements.extend(entity_type.findall('./NavigationProperty'))
        nav_prop_elements.extend(entity_type.findall('.//NavigationProperty'))
        nav_prop_elements.extend(entity_type.findall('.//{http://schemas.microsoft.com/ado/2008/09/edm}NavigationProperty'))
        nav_prop_elements.extend(entity_type.findall('.//edm:NavigationProperty', ns))
        nav_prop_elements.extend(entity_type.findall('.//edm2008:NavigationProperty', ns))
        
        for nav_prop in nav_prop_elements:
            nav_name = nav_prop.get('Name')
            relationship = nav_prop.get('Relationship', '')
            
            # Skip if no relationship defined
            if not relationship:
                continue
                
            from_role = nav_prop.get('FromRole', '')
            to_role = nav_prop.get('ToRole', '')
            
            # ---------------
            # Standard approach: using FromRole/ToRole with Association lookup
            # ---------------
            if from_role and to_role:
                # Try to get the association by its name (with or without namespace)
                assoc_name = relationship.split('.')[-1] if '.' in relationship else relationship
                assoc = None
                
                # Look up in our association map
                if relationship in assoc_map:
                    assoc = assoc_map[relationship]
                elif assoc_name in assoc_map:
                    assoc = assoc_map[assoc_name]
                
                if assoc is not None:
                    # Get the end elements
                    end_elements = []
                    end_elements.extend(assoc.findall('./End'))
                    end_elements.extend(assoc.findall('.//End'))
                    end_elements.extend(assoc.findall('.//{http://schemas.microsoft.com/ado/2008/09/edm}End'))
                    end_elements.extend(assoc.findall('.//edm:End', ns))
                    end_elements.extend(assoc.findall('.//edm2008:End', ns))
                    
                    if len(end_elements) == 2:
                        # Match the roles to find source and target
                        source_end = None
                        target_end = None
                        
                        for end in end_elements:
                            role = end.get('Role', '')
                            if role == from_role:
                                source_end = end
                            elif role == to_role:
                                target_end = end
                        
                        if source_end is not None and target_end is not None:
                            # Get the target entity
                            target_type = target_end.get('Type', '')
                            target_entity = target_type.split('.')[-1] if target_type else ''
                            
                            # Get multiplicities
                            source_mult = source_end.get('Multiplicity', '1')
                            target_mult = target_end.get('Multiplicity', '1')
                            
                            # Add the relationship if target entity exists
                            if target_entity and target_entity in entities:
                                rel_tuple = (entity_name, target_entity, source_mult, target_mult)
                                if rel_tuple not in relationships:
                                    relationships.append(rel_tuple)
                
            # ---------------
            # SAP-specific approach: Relationship name format indicates the connected entities
            # ---------------
            
            # Special case for SAP: handle format like "SFOData.PerPhone_Person"
            # Split the relationship name to extract entity names
            rel_parts = relationship.split('.')[-1].split('_')
            if len(rel_parts) == 2:
                # Try to match entity names based on the relationship format
                source_entity = entity_name
                
                # Check if the first or second part matches an existing entity
                first_part, second_part = rel_parts[0], rel_parts[1]
                target_entity = None
                
                # First try direct match
                if second_part in entities:
                    target_entity = second_part
                # Sometimes the target entity name is in a different format
                elif "Per" + second_part in entities:
                    target_entity = "Per" + second_part
                
                # If we found a target entity, add the relationship
                if target_entity:
                    rel_tuple = (source_entity, target_entity, '1', '*')  # Default multiplicity 
                    if rel_tuple not in relationships:
                        relationships.append(rel_tuple)
    
    return entities, relationships

def generate_mermaid_diagram(entities: Dict, relationships: List) -> str:
    """Generate Mermaid ER diagram from entities and relationships."""
    mermaid = ["erDiagram"]
    
    # Map of OData types to simpler types for Mermaid
    type_map = {
        "Edm.String": "String",
        "Edm.Int32": "Int",
        "Edm.Int64": "Int64",
        "Edm.Boolean": "Boolean",
        "Edm.DateTime": "DateTime",
        "Edm.DateTimeOffset": "DateTime",
        "Edm.Time": "Time",
        "Edm.Decimal": "Decimal",
        "Edm.Double": "Float",
        "Edm.Single": "Float",
        "Edm.Guid": "String",
        "Edm.Binary": "Binary"
    }
    
    # Add entities with simplified syntax
    for entity_name, properties in entities.items():
        # Clean entity name - replace any characters that might cause issues in Mermaid
        safe_entity_name = entity_name.replace("-", "_").replace(" ", "_")
        
        mermaid.append(f"    {safe_entity_name} {{")
        
        # Use a set to track properties we've already added to avoid duplicates
        added_props = set()
        
        for prop_name, prop_type, nullable in properties:
            # Extract the base name without any markers like (PK)
            base_prop_name = prop_name.split(' ')[0] if ' ' in prop_name else prop_name
            
            # Skip duplicate properties
            prop_key = f"{base_prop_name}_{prop_type}"
            if prop_key in added_props:
                continue
                
            added_props.add(prop_key)
            
            # Make sure the property type is valid by mapping it to a simpler type
            # First check if it's a full EDM type
            if prop_type in type_map:
                safe_prop_type = type_map[prop_type]
            else:
                # If not found, use a default type based on the suffix
                safe_prop_type = "String"  # Default type
                for edm_type, mermaid_type in type_map.items():
                    if prop_type.endswith(edm_type.split('.')[-1]):
                        safe_prop_type = mermaid_type
                        break
            
            # Clean property name and handle special characters
            safe_prop_name = prop_name.replace("-", "_").replace(" ", "_").replace("(", "_").replace(")", "_")
            
            # Keep the PK marker in a more Mermaid-friendly format
            if "(PK)" in prop_name:
                safe_prop_name = safe_prop_name.replace("_PK_", "")
                safe_prop_name = f"{safe_prop_name} PK"
            
            mermaid.append(f"        {safe_prop_type} {safe_prop_name}")
        
        mermaid.append("    }")
    
    # Add relationships with simplified syntax
    for from_entity, to_entity, from_mult, to_mult in relationships:
        # Clean entity names
        safe_from_entity = from_entity.replace("-", "_").replace(" ", "_")
        safe_to_entity = to_entity.replace("-", "_").replace(" ", "_")
        
        # Convert multiplicity to Mermaid format
        # Use simple relationship notation
        if from_mult == "1" and to_mult == "1":
            rel = "||--||"
        elif from_mult == "1" and to_mult in ["*", "0..*"]:
            rel = "||--|{"
        elif from_mult in ["*", "0..*"] and to_mult == "1":
            rel = "}|--||"
        else:
            rel = "}|--|{"
        
        # Add a simple label
        mermaid.append(f"    {safe_from_entity} {rel} {safe_to_entity} : relates")
    
    return "\n".join(mermaid)

def main():
    if len(sys.argv) != 2:
        print("Usage: python odata_to_mermaid.py <odata_file.xml>")
        sys.exit(1)
    
    try:
        entities, relationships = parse_odata_file(sys.argv[1])
        mermaid_diagram = generate_mermaid_diagram(entities, relationships)
        # Change the output filename to use .md extension
        output_file = "diagram.md"
        with open(output_file, 'w') as f:
            f.write(mermaid_diagram)
        print(f"Diagram written to {output_file}")
    except Exception as e:
        print(f"Error: {str(e)}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main() 