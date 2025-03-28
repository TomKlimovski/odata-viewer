# OData Viewer

A tool to visualize OData metadata files using Mermaid ER diagrams. This tool helps business analysts understand the data model by converting OData XML files into clear, visual entity-relationship diagrams.

## Features

- Converts OData XML metadata files to Mermaid ER diagrams
- Shows entity types with their properties and data types
- Visualizes relationships between entities with proper cardinality
- Supports all standard OData data types
- Easy to use command-line interface

## Requirements

- Python 3.6 or higher
- No additional dependencies required (uses built-in XML parser)

## Usage

1. Clone this repository
2. Make the script executable:
   ```bash
   chmod +x odata_to_mermaid.py
   ```
3. Run the script with your OData XML file:
   ```bash
   ./odata_to_mermaid.py sample-files/northwind.xml > diagram.mmd
   ```
4. The generated Mermaid diagram can be viewed using:
   - [Mermaid Live Editor](https://mermaid.live)
   - GitHub (which natively supports Mermaid diagrams)
   - VS Code with Mermaid extension

## Example Output

The script will generate a Mermaid ER diagram that looks like this:

```mermaid
erDiagram
    Category {
        CategoryID Edm.Int32 NOT NULL
        CategoryName Edm.String NOT NULL
        Description Edm.String NULL
        Picture Edm.Binary NULL
    }
    Product {
        ProductID Edm.Int32 NOT NULL
        ProductName Edm.String NOT NULL
        SupplierID Edm.Int32 NULL
        CategoryID Edm.Int32 NULL
        QuantityPerUnit Edm.String NULL
        UnitPrice Edm.Decimal NULL
        UnitsInStock Edm.Int16 NULL
        UnitsOnOrder Edm.Int16 NULL
        ReorderLevel Edm.Int16 NULL
        Discontinued Edm.Boolean NOT NULL
    }
    Category ||--o| Product
```

## License

Apache License 2.0