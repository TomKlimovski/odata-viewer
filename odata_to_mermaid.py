#!/usr/bin/env python3
import xml.etree.ElementTree as ET
import sys
from typing import Dict, List, Tuple

def parse_odata_file(file_path: str) -> Tuple[Dict, List]:
    """Parse OData XML file and extract entity types and relationships."""
    tree = ET.parse(file_path)
    root = tree.getroot()
    
    # Define namespaces
    ns = {
        'edmx': 'http://schemas.microsoft.com/ado/2007/06/edmx',
        'edm': 'http://schemas.microsoft.com/ado/2009/11/edm'
    }
    
    # Find the Schema element containing entity types
    schema = root.find('.//edm:Schema', ns)
    if schema is None:
        raise ValueError("No Schema element found in the OData file")
    
    # Extract entity types
    entities = {}
    for entity_type in schema.findall('.//edm:EntityType', ns):
        name = entity_type.get('Name')
        properties = []
        for prop in entity_type.findall('.//edm:Property', ns):
            prop_name = prop.get('Name')
            prop_type = prop.get('Type').split('.')[-1]  # Just use the type name without Edm prefix
            nullable = prop.get('Nullable', 'true')
            properties.append((prop_name, prop_type, nullable))
        entities[name] = properties
    
    # Extract relationships
    relationships = []
    for assoc in schema.findall('.//edm:Association', ns):
        name = assoc.get('Name')
        ends = assoc.findall('.//edm:End', ns)
        if len(ends) == 2:
            from_entity = ends[0].get('Type').split('.')[-1]
            to_entity = ends[1].get('Type').split('.')[-1]
            from_mult = ends[0].get('Multiplicity', '1')
            to_mult = ends[1].get('Multiplicity', '1')
            relationships.append((from_entity, to_entity, from_mult, to_mult))
    
    return entities, relationships

def generate_mermaid_diagram(entities: Dict, relationships: List) -> str:
    """Generate Mermaid ER diagram from entities and relationships."""
    mermaid = ["```mermaid", "erDiagram"]
    
    # Add entities
    for entity_name, properties in entities.items():
        mermaid.append(f"    {entity_name} {{")
        # Add each property on a new line with correct Mermaid syntax
        for prop_name, prop_type, nullable in properties:
            # Format: propertyName type
            mermaid.append(f"        {prop_name} {prop_type}")
        mermaid.append("    }")
    
    # Add relationships with proper Mermaid syntax
    for from_entity, to_entity, from_mult, to_mult in relationships:
        # Convert multiplicity to Mermaid notation
        if from_mult == "1" and to_mult == "1":
            cardinality = "one-to-one"
        elif from_mult == "1" and to_mult in ["*", "0..*"]:
            cardinality = "one-to-many"
        elif from_mult in ["*", "0..*"] and to_mult == "1":
            cardinality = "many-to-one"
        else:
            cardinality = "many-to-many"
            
        # Add relationship with verb phrase
        mermaid.append(f"    {from_entity} |o--o| {to_entity} : \"{cardinality}\"")
    
    mermaid.append("```")
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