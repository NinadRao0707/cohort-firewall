"""Minimal JSON-schema subset checker, for offline tests. The official check is format/validate.py."""
import re


def check(doc, schema, root=None, path="(top)"):
    root = root or schema
    if "$ref" in schema:
        name = schema["$ref"].split("/")[-1]
        return check(doc, root["$defs"][name], root, path)
    errs = []
    t = schema.get("type")
    types = {"object": dict, "array": list, "string": str, "boolean": bool}
    if t in types and not isinstance(doc, types[t]):
        return [f"{path}: expected {t}"]
    if "const" in schema and doc != schema["const"]:
        errs.append(f"{path}: must be {schema['const']!r}")
    if "enum" in schema and doc not in schema["enum"]:
        errs.append(f"{path}: {doc!r} not in {schema['enum']}")
    if "pattern" in schema and isinstance(doc, str) and not re.search(schema["pattern"], doc):
        errs.append(f"{path}: does not match {schema['pattern']}")
    if isinstance(doc, dict):
        for k in schema.get("required", []):
            if k not in doc:
                errs.append(f"{path}: missing {k}")
        for k, sub in schema.get("properties", {}).items():
            if k in doc:
                errs += check(doc[k], sub, root, f"{path}/{k}")
    if isinstance(doc, list):
        if len(doc) < schema.get("minItems", 0):
            errs.append(f"{path}: fewer than {schema['minItems']} items")
        if "items" in schema:
            for i, item in enumerate(doc):
                errs += check(item, schema["items"], root, f"{path}/{i}")
    return errs
