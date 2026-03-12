#!/usr/bin/env python3
"""ValidateTemplate - Template Syntax Validator using Jinja2."""
from __future__ import annotations
import argparse, json, re, sys
from dataclasses import dataclass, field
from pathlib import Path
try:
    import jinja2
except ImportError:
    print("Install jinja2: pip install Jinja2", file=sys.stderr); sys.exit(1)
try:
    import yaml
except ImportError:
    yaml = None

@dataclass
class ValidationResult:
    valid: bool = True
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    variables: list[str] = field(default_factory=list)

def _resolve_path(p: str) -> Path:
    path = Path(p)
    if path.is_absolute(): return path
    return Path(__file__).parent.parent.parent / p

def _extract_variables(source: str) -> list[str]:
    variables = set()
    for m in re.finditer(r"\{\{([a-zA-Z_][a-zA-Z0-9_.]*)\}\}", source): variables.add(m.group(1))
    for m in re.finditer(r"\{%\s*(?:for|if)\s+([a-zA-Z_][a-zA-Z0-9_.]*)", source): variables.add(m.group(1))
    return sorted(variables)

def validate_template(template_path: str, data_path: str = None, strict: bool = False) -> ValidationResult:
    result = ValidationResult()
    full = _resolve_path(template_path)
    if not full.exists():
        result.valid = False; result.errors.append(f"Template not found: {full}"); return result
    source = full.read_text(encoding="utf-8")
    result.variables = _extract_variables(source)
    try:
        env = jinja2.Environment(loader=jinja2.FileSystemLoader(str(full.parent)))
        env.parse(source)
    except jinja2.TemplateSyntaxError as e:
        result.valid = False; result.errors.append(f"Syntax error: {e}")
    return result

def main():
    parser = argparse.ArgumentParser(description="PAI Template Validator")
    parser.add_argument("-t", "--template", required=True)
    parser.add_argument("-d", "--data")
    parser.add_argument("-s", "--strict", action="store_true")
    args = parser.parse_args()
    result = validate_template(args.template, args.data, args.strict)
    print(f"\n=== Template Validation ===\nTemplate: {args.template}\nStatus: {'Valid' if result.valid else 'Invalid'}")
    if result.variables: print(f"\nVariables ({len(result.variables)}):" + "".join(f"\n  - {v}" for v in result.variables))
    if result.errors: print(f"\nErrors ({len(result.errors)}):" + "".join(f"\n  - {e}" for e in result.errors))
    if result.warnings: print(f"\nWarnings ({len(result.warnings)}):" + "".join(f"\n  - {w}" for w in result.warnings))
    sys.exit(0 if result.valid else 1)

if __name__ == "__main__": main()
