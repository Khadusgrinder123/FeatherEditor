"""Lightweight Python import/member completion without an external language server."""
import ast
import importlib
import os
import re
import sys


_MEMBER_RE = re.compile(r"(?P<owner>[A-Za-z_]\w*(?:\.[A-Za-z_]\w*)*)\.(?P<prefix>[A-Za-z_]\w*)?$")


def _context(source, line, column):
    lines = source.splitlines(keepends=True)
    if line < 0 or line >= len(lines):
        return None
    before_line = lines[line][:column]
    match = _MEMBER_RE.search(before_line)
    if not match:
        return None
    return lines, match


def _parse_source(lines, line_index, current_line, match):
    prefix = "".join(lines[:line_index])
    line = lines[line_index]
    indent = re.match(r"[ \t]*", line).group(0)
    replaced = indent + "pass" + ("\n" if line.endswith("\n") else "")
    # Preserve preceding code on the same line where practical (e.g. semicolon-separated imports).
    before_expression = line[:match.start("owner")]
    if before_expression.strip():
        replaced = before_expression + "pass" + ("\n" if line.endswith("\n") else "")
    suffix = "".join(lines[line_index + 1:])
    try:
        return ast.parse(prefix + replaced + suffix)
    except SyntaxError:
        try:
            return ast.parse(prefix)
        except SyntaxError:
            return ast.Module(body=[], type_ignores=[])


def _load_import(module_name, workspace_root):
    if workspace_root and workspace_root not in sys.path:
        sys.path.insert(0, workspace_root)
        inserted = True
    else:
        inserted = False
    try:
        return importlib.import_module(module_name)
    except Exception:
        return None
    finally:
        if inserted:
            try:
                sys.path.remove(workspace_root)
            except ValueError:
                pass


def _imports(tree, workspace_root):
    names = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                module_name = alias.name if alias.asname else alias.name.split(".", 1)[0]
                value = _load_import(module_name, workspace_root)
                if value is not None:
                    names[alias.asname or alias.name.split(".", 1)[0]] = value
        elif isinstance(node, ast.ImportFrom) and node.module:
            module = _load_import(node.module, workspace_root)
            if module is None:
                continue
            for alias in node.names:
                if alias.name == "*":
                    for member in dir(module):
                        if not member.startswith("_"):
                            try:
                                names[member] = getattr(module, member)
                            except Exception:
                                continue
                else:
                    try:
                        names[alias.asname or alias.name] = getattr(module, alias.name)
                    except Exception:
                        submodule = _load_import(f"{node.module}.{alias.name}", workspace_root)
                        if submodule is not None:
                            names[alias.asname or alias.name] = submodule
    return names


def _resolve(node, names):
    if isinstance(node, ast.Name):
        if node.id in names:
            return names[node.id]
        builtin = getattr(__builtins__, node.id, None) if not isinstance(__builtins__, dict) else __builtins__.get(node.id)
        return builtin
    if isinstance(node, ast.Attribute):
        owner = _resolve(node.value, names)
        if owner is not None:
            try:
                return getattr(owner, node.attr)
            except Exception:
                return None
    if isinstance(node, ast.List):
        return []
    if isinstance(node, ast.Dict):
        return {}
    if isinstance(node, ast.Set):
        return set()
    if isinstance(node, ast.Tuple):
        return ()
    if isinstance(node, ast.Constant):
        return node.value
    if isinstance(node, ast.Call):
        constructor = _resolve(node.func, names)
        if constructor in (list, dict, set, tuple, str, bytes, int, float, bool):
            try:
                return constructor()
            except Exception:
                return constructor
        return constructor
    return None


def _member_names(tree, owner_expression, workspace_root):
    names = _imports(tree, workspace_root)
    inferred = {}
    for node in ast.walk(tree):
        if isinstance(node, (ast.Assign, ast.AnnAssign)):
            value_node = node.value
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            value = _resolve(value_node, {**names, **inferred}) if value_node else None
            if value is None and isinstance(node, ast.AnnAssign):
                value = _resolve(node.annotation, {**names, **inferred})
            for target in targets:
                if isinstance(target, ast.Name) and value is not None:
                    inferred[target.id] = value
    bindings = {**names, **inferred}
    try:
        expression = ast.parse(owner_expression, mode="eval").body
    except SyntaxError:
        return []
    value = _resolve(expression, bindings)
    if value is None:
        return []
    try:
        return [name for name in dir(value) if not name.startswith("__")]
    except Exception:
        return []


def complete_members(source, line, column, workspace_root=None):
    """Return members for an imported module/object or locally inferred variable."""
    context = _context(source, line, column)
    if context is None:
        return []
    lines, match = context
    tree = _parse_source(lines, line, lines[line], match)
    candidates = _member_names(tree, match.group("owner"), os.path.abspath(workspace_root) if workspace_root else None)
    prefix = match.group("prefix") or ""
    return [name for name in candidates if name.lower().startswith(prefix.lower())][:100]
