"""
Utilities for JSON schema manipulation.
"""

def inline_refs(schema: dict) -> dict:
    """
    Recursively inline all $ref references in a JSON schema.
    Converts schemas with $defs and $ref to fully inlined schemas for Claude.

    Args:
        schema: The schema dict to process

    Returns:
        A new schema dict with all $ref references inlined
    """
    # Extract and remove $defs from schema copy
    schema = schema.copy()
    defs = schema.pop("$defs", {})

    def resolve_refs(node, defs):
        if isinstance(node, dict):
            if "$ref" in node:
                # Extract ref name (e.g., "#/$defs/MyModel" -> "MyModel")
                ref_name = node["$ref"].split("/")[-1]
                return resolve_refs(defs[ref_name], defs)
            return {k: resolve_refs(v, defs) for k, v in node.items()}
        elif isinstance(node, list):
            return [resolve_refs(i, defs) for i in node]
        return node

    return resolve_refs(schema, defs)
