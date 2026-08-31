import ast
import os
import sys

def check_file(path):
    with open(path, "r", encoding="utf-8") as f:
        content = f.read()
    try:
        tree = ast.parse(content, filename=path)
    except SyntaxError as e:
        return [f"SyntaxError in {path}: {e}"]

    # Collect all top-level imported names
    imported_names = set()
    for node in tree.body:
        if isinstance(node, ast.Import):
            for alias in node.names:
                imported_names.add(alias.asname or alias.name)
        elif isinstance(node, ast.ImportFrom):
            for alias in node.names:
                imported_names.add(alias.asname or alias.name)

    issues = []
    # Check typing names used in annotations
    common_typing = {"Any", "Dict", "List", "Optional", "Set", "Tuple", "Union", "Callable", "Iterable", "Sequence"}
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            # Check return type annotation
            if node.returns:
                for sub in ast.walk(node.returns):
                    if isinstance(sub, ast.Name) and sub.id in common_typing:
                        if sub.id not in imported_names:
                            issues.append(f"{path}:{node.lineno} in {node.name} return type: '{sub.id}' is used but not imported!")
            # Check arg annotations
            for arg in node.args.args + node.args.kwonlyargs:
                if arg.annotation:
                    for sub in ast.walk(arg.annotation):
                        if isinstance(sub, ast.Name) and sub.id in common_typing:
                            if sub.id not in imported_names:
                                issues.append(f"{path}:{arg.lineno} in {node.name} arg '{arg.arg}': '{sub.id}' is used but not imported!")
        elif isinstance(node, ast.AnnAssign):
            if node.annotation:
                for sub in ast.walk(node.annotation):
                    if isinstance(sub, ast.Name) and sub.id in common_typing:
                        if sub.id not in imported_names:
                            issues.append(f"{path}:{node.lineno} in var annotation: '{sub.id}' is used but not imported!")

    return issues

all_issues = []
for root, _, files in os.walk("saleha"):
    for f in files:
        if f.endswith(".py"):
            p = os.path.join(root, f)
            iss = check_file(p)
            all_issues.extend(iss)

for root, _, files in os.walk("scripts"):
    for f in files:
        if f.endswith(".py"):
            p = os.path.join(root, f)
            iss = check_file(p)
            all_issues.extend(iss)

if all_issues:
    print(f"FOUND {len(all_issues)} TYPE ANNOTATION ISSUES:")
    for i in all_issues:
        print("  -", i)
else:
    print("NO TYPE ANNOTATION ISSUES FOUND IN ANY FILE!")
