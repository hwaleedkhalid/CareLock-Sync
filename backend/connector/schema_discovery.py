"""
Schema Discovery Engine
Automatically discovers and analyzes database schemas
"""
from sqlalchemy import create_engine, inspect, MetaData
from sqlalchemy.engine import reflection
from typing import Dict, List, Optional, Any
import json
from datetime import datetime


class SchemaDiscovery:
    """
    Discovers database schema structure including tables, columns, 
    relationships, and constraints
    """
    
    def __init__(self, database_url: str):
        """
        Initialize schema discovery with database connection
        
        Args:
            database_url: SQLAlchemy database URL
        """
        self.database_url = database_url
        self.engine = create_engine(database_url)
        self.inspector = inspect(self.engine)
        self.metadata = MetaData()
        self.metadata.reflect(bind=self.engine)
    
    def get_all_tables(self) -> List[str]:
        """
        Get list of all table names in the database
        
        Returns:
            List of table names
        """
        return self.inspector.get_table_names()
    
    def get_table_columns(self, table_name: str) -> List[Dict[str, Any]]:
        """
        Get detailed column information for a table
        
        Args:
            table_name: Name of the table
            
        Returns:
            List of column dictionaries with details
        """
        columns = []
        for column in self.inspector.get_columns(table_name):
            column_info = {
                'name': column['name'],
                'type': str(column['type']),
                'nullable': column['nullable'],
                'default': str(column['default']) if column['default'] else None,
                'primary_key': column.get('primary_key', False)
            }
            columns.append(column_info)
        return columns
    
    def get_primary_keys(self, table_name: str) -> List[str]:
        """
        Get primary key columns for a table
        
        Args:
            table_name: Name of the table
            
        Returns:
            List of primary key column names
        """
        pk_constraint = self.inspector.get_pk_constraint(table_name)
        return pk_constraint.get('constrained_columns', [])
    
    def get_foreign_keys(self, table_name: str) -> List[Dict[str, Any]]:
        """
        Get foreign key relationships for a table
        
        Args:
            table_name: Name of the table
            
        Returns:
            List of foreign key dictionaries
        """
        fks = []
        for fk in self.inspector.get_foreign_keys(table_name):
            fk_info = {
                'name': fk.get('name'),
                'constrained_columns': fk['constrained_columns'],
                'referred_table': fk['referred_table'],
                'referred_columns': fk['referred_columns']
            }
            fks.append(fk_info)
        return fks
    
    def get_indexes(self, table_name: str) -> List[Dict[str, Any]]:
        """
        Get indexes for a table
        
        Args:
            table_name: Name of the table
            
        Returns:
            List of index dictionaries
        """
        indexes = []
        for index in self.inspector.get_indexes(table_name):
            index_info = {
                'name': index['name'],
                'columns': index['column_names'],
                'unique': index['unique']
            }
            indexes.append(index_info)
        return indexes
    
    def get_table_schema(self, table_name: str) -> Dict[str, Any]:
        """
        Get complete schema information for a single table
        
        Args:
            table_name: Name of the table
            
        Returns:
            Dictionary with complete table schema
        """
        return {
            'table_name': table_name,
            'columns': self.get_table_columns(table_name),
            'primary_keys': self.get_primary_keys(table_name),
            'foreign_keys': self.get_foreign_keys(table_name),
            'indexes': self.get_indexes(table_name)
        }
    
    def get_complete_schema(self) -> Dict[str, Any]:
        """
        Get complete database schema for all tables
        
        Returns:
            Dictionary with complete database schema
        """
        tables = self.get_all_tables()
        schema = {
            'database': 'hospital_db',  # Could be extracted from URL
            'discovered_at': datetime.utcnow().isoformat(),
            'total_tables': len(tables),
            'tables': {}
        }
        
        for table_name in tables:
            schema['tables'][table_name] = self.get_table_schema(table_name)
        
        return schema
    
    def get_table_relationships(self) -> Dict[str, List[Dict[str, str]]]:
        """
        Map all relationships between tables
        
        Returns:
            Dictionary mapping tables to their relationships
        """
        relationships = {}
        
        for table_name in self.get_all_tables():
            table_rels = []
            
            # Get foreign keys (outgoing relationships)
            for fk in self.get_foreign_keys(table_name):
                table_rels.append({
                    'type': 'foreign_key',
                    'from_table': table_name,
                    'from_columns': fk['constrained_columns'],
                    'to_table': fk['referred_table'],
                    'to_columns': fk['referred_columns']
                })
            
            relationships[table_name] = table_rels
        
        return relationships
    
    def export_schema_to_json(self, output_file: str) -> None:
        """
        Export complete schema to JSON file
        
        Args:
            output_file: Path to output JSON file
        """
        schema = self.get_complete_schema()
        with open(output_file, 'w') as f:
            json.dump(schema, f, indent=2)
        print(f"Schema exported to {output_file}")
    
    def print_schema_summary(self) -> None:
        """Print a summary of the database schema"""
        tables = self.get_all_tables()
        print("\n" + "=" * 60)
        print("Database Schema Summary")
        print("=" * 60)
        print(f"Total Tables: {len(tables)}\n")
        
        for table_name in tables:
            columns = self.get_table_columns(table_name)
            pks = self.get_primary_keys(table_name)
            fks = self.get_foreign_keys(table_name)
            
            print(f"\nTable: {table_name}")
            print(f"  Columns: {len(columns)}")
            print(f"  Primary Keys: {', '.join(pks) if pks else 'None'}")
            print(f"  Foreign Keys: {len(fks)}")
            
            # Show first few columns
            print(f"  Sample Columns:")
            for col in columns[:5]:
                pk_marker = " [PK]" if col['name'] in pks else ""
                print(f"    - {col['name']} ({col['type']}){pk_marker}")
            
            if len(columns) > 5:
                print(f"    ... and {len(columns) - 5} more")


def discover_hospital_schema(database_url: str, export_to_file: Optional[str] = None):
    """
    Convenience function to discover hospital database schema
    
    Args:
        database_url: Database connection URL
        export_to_file: Optional file path to export schema
        
    Returns:
        Complete schema dictionary
    """
    discovery = SchemaDiscovery(database_url)
    
    # Print summary
    discovery.print_schema_summary()
    
    # Get complete schema
    schema = discovery.get_complete_schema()
    
    # Export if requested
    if export_to_file:
        discovery.export_schema_to_json(export_to_file)
    
    return schema


if __name__ == "__main__":
    # Test schema discovery
    import sys
    import os
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    
    from common.config import settings
    
    print("Discovering hospital database schema...")
    schema = discover_hospital_schema(
        settings.hospital_db_url,
        export_to_file="hospital_schema.json"
    )
    
    print(f"\n[OK] Schema discovery complete!")
    print(f"Total tables discovered: {schema['total_tables']}")
