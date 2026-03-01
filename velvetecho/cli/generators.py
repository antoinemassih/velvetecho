"""
Code Generators

Generate models, schemas, routers, and complete resources.
"""

from pathlib import Path
from typing import List, Dict, Any, Optional
from datetime import datetime
from velvetecho.cli.templates import (
    MODEL_TEMPLATE,
    SCHEMAS_TEMPLATE,
    ROUTER_TEMPLATE,
    MIGRATION_TEMPLATE,
)


class ResourceGenerator:
    """Generate complete resources or individual components"""

    def __init__(self, output_dir: Path):
        self.output_dir = Path(output_dir)

    def generate_resource(
        self,
        name: str,
        fields: List[str],
        timestamps: bool = False,
        soft_delete: bool = False,
    ) -> Dict[str, Any]:
        """
        Generate complete resource (model + schemas + router + migration)

        Args:
            name: Resource name (e.g., "Agent", "Workspace")
            fields: List of fields (e.g., ["name:str", "description:text"])
            timestamps: Add created_at/updated_at
            soft_delete: Add deleted_at

        Returns:
            Dictionary with created files and metadata
        """
        # Parse fields
        parsed_fields = self._parse_fields(fields)

        # Generate all components
        model_result = self.generate_model(name, fields, timestamps, soft_delete)
        schemas_result = self.generate_schemas(name, fields)
        router_result = self.generate_router(name, include_crud=True)
        migration_result = self.generate_migration(name, parsed_fields, timestamps, soft_delete)

        # Collect results
        files = [
            model_result["file"],
            schemas_result["file"],
            router_result["file"],
            migration_result["file"],
        ]

        endpoints = self._generate_endpoint_list(name.lower() + "s")

        return {
            "name": name,
            "files": files,
            "endpoints": endpoints,
            "model": model_result,
            "schemas": schemas_result,
            "router": router_result,
            "migration": migration_result,
        }

    def generate_model(
        self,
        name: str,
        fields: List[str],
        timestamps: bool = False,
        soft_delete: bool = False,
    ) -> Dict[str, Any]:
        """Generate database model"""
        parsed_fields = self._parse_fields(fields)

        # Build mixins
        mixins = []
        if timestamps:
            mixins.append("TimestampMixin")
        if soft_delete:
            mixins.append("SoftDeleteMixin")

        # Render template
        content = MODEL_TEMPLATE.format(
            name=name,
            table_name=self._to_table_name(name),
            mixins=", " + ", ".join(mixins) if mixins else "",
            fields=self._render_model_fields(parsed_fields),
        )

        # Write file
        file_path = self.output_dir / "velvetecho" / "database" / "models" / f"{name.lower()}.py"
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_text(content)

        return {"file": str(file_path), "name": name}

    def generate_schemas(self, name: str, fields: List[str]) -> Dict[str, Any]:
        """Generate Pydantic schemas (Create/Update/Response)"""
        parsed_fields = self._parse_fields(fields)

        content = SCHEMAS_TEMPLATE.format(
            name=name,
            create_fields=self._render_schema_fields(parsed_fields, for_create=True),
            update_fields=self._render_schema_fields(parsed_fields, for_update=True),
            response_fields=self._render_schema_fields(parsed_fields, for_response=True),
        )

        file_path = self.output_dir / "velvetecho" / "models" / f"{name.lower()}.py"
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_text(content)

        return {"file": str(file_path), "name": name}

    def generate_router(self, name: str, include_crud: bool = True) -> Dict[str, Any]:
        """Generate API router"""
        plural = name.lower() + "s"

        content = ROUTER_TEMPLATE.format(
            name=name,
            plural=plural,
            prefix=f"/api/{plural}",
            tags=name + "s",
        )

        file_path = self.output_dir / "velvetecho" / "api" / "routers" / f"{plural}.py"
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_text(content)

        return {"file": str(file_path), "name": name, "prefix": f"/api/{plural}"}

    def generate_migration(
        self,
        name: str,
        fields: List[Dict],
        timestamps: bool,
        soft_delete: bool,
    ) -> Dict[str, Any]:
        """Generate Alembic migration"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        table_name = self._to_table_name(name)

        content = MIGRATION_TEMPLATE.format(
            timestamp=timestamp,
            name=name,
            table_name=table_name,
            columns=self._render_migration_columns(fields, timestamps, soft_delete),
        )

        migrations_dir = self.output_dir / "migrations" / "versions"
        migrations_dir.mkdir(parents=True, exist_ok=True)

        file_path = migrations_dir / f"{timestamp}_create_{table_name}.py"
        file_path.write_text(content)

        return {"file": str(file_path), "table": table_name}

    # ========================================================================
    # Helper Methods
    # ========================================================================

    def _parse_fields(self, fields: List[str]) -> List[Dict[str, Any]]:
        """
        Parse field definitions like 'name:str' or 'description:text?'

        Returns:
            List of dicts with field metadata
        """
        parsed = []

        for field_def in fields:
            # Split name:type
            if ":" not in field_def:
                raise ValueError(f"Invalid field format: {field_def}. Expected 'name:type'")

            name, type_str = field_def.split(":", 1)
            optional = type_str.endswith("?")
            type_str = type_str.rstrip("?")

            parsed.append(
                {
                    "name": name,
                    "type": type_str,
                    "optional": optional,
                    "python_type": self._sql_to_python_type(type_str),
                    "sql_type": self._to_sql_type(type_str),
                }
            )

        return parsed

    def _to_sql_type(self, type_str: str) -> str:
        """Convert simple type to SQLAlchemy type"""
        mapping = {
            "str": "String",
            "text": "Text",
            "int": "Integer",
            "float": "Float",
            "bool": "Boolean",
            "uuid": "PGUUID(as_uuid=True)",
            "datetime": "DateTime",
            "json": "JSON",
        }
        return mapping.get(type_str, "String")

    def _sql_to_python_type(self, type_str: str) -> str:
        """Convert SQL type to Python type annotation"""
        mapping = {
            "str": "str",
            "text": "str",
            "int": "int",
            "float": "float",
            "bool": "bool",
            "uuid": "UUID",
            "datetime": "datetime",
            "json": "dict",
        }
        return mapping.get(type_str, "str")

    def _to_table_name(self, name: str) -> str:
        """Convert CamelCase to snake_case plural"""
        # Simple pluralization (add 's')
        snake_case = "".join(["_" + c.lower() if c.isupper() else c for c in name]).lstrip("_")
        return snake_case + "s"

    def _render_model_fields(self, fields: List[Dict]) -> str:
        """Render SQLAlchemy model fields"""
        lines = []
        for field in fields:
            nullable = "nullable=True" if field["optional"] else "nullable=False"
            lines.append(f'    {field["name"]} = Column({field["sql_type"]}, {nullable})')
        return "\n".join(lines)

    def _render_schema_fields(self, fields: List[Dict], for_create=False, for_update=False, for_response=False) -> str:
        """Render Pydantic schema fields"""
        lines = []

        for field in fields:
            python_type = field["python_type"]

            if for_update:
                # All fields optional in Update schema
                lines.append(f'    {field["name"]}: Optional[{python_type}] = None')
            elif field["optional"]:
                lines.append(f'    {field["name"]}: Optional[{python_type}] = None')
            else:
                lines.append(f'    {field["name"]}: {python_type}')

        if for_response:
            # Response schema always includes id + timestamps
            lines.insert(0, "    id: UUID")
            lines.append("    created_at: datetime")
            lines.append("    updated_at: datetime")

        return "\n".join(lines)

    def _render_migration_columns(self, fields: List[Dict], timestamps: bool, soft_delete: bool) -> str:
        """Render Alembic migration columns"""
        lines = []

        # ID column (always present)
        lines.append('        sa.Column("id", sa_uuid.UUID(), primary_key=True),')

        # User fields
        for field in fields:
            nullable = field["optional"]
            lines.append(f'        sa.Column("{field["name"]}", sa.{field["sql_type"]}, nullable={nullable}),')

        # Timestamp fields
        if timestamps:
            lines.append('        sa.Column("created_at", sa.DateTime(), nullable=False),')
            lines.append('        sa.Column("updated_at", sa.DateTime(), nullable=False),')

        # Soft delete
        if soft_delete:
            lines.append('        sa.Column("deleted_at", sa.DateTime(), nullable=True),')

        return "\n".join(lines)

    def _generate_endpoint_list(self, resource_plural: str) -> List[str]:
        """Generate list of available endpoints"""
        prefix = f"/api/{resource_plural}"
        return [
            f"GET    {prefix}           # List all {resource_plural}",
            f"GET    {prefix}/{{id}}      # Get {resource_plural[:-1]} by ID",
            f"POST   {prefix}           # Create {resource_plural[:-1]}",
            f"PUT    {prefix}/{{id}}      # Update {resource_plural[:-1]}",
            f"DELETE {prefix}/{{id}}      # Delete {resource_plural[:-1]}",
        ]
