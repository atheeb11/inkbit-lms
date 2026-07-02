import ast
import builtins
import sys

def check_file(filename):
    print(f"Checking {filename} for undefined names...")
    with open(filename, 'r', encoding='utf-8') as f:
        tree = ast.parse(f.read())
        
    global_names = set(dir(builtins))
    # Collect imports and global definitions
    for node in tree.body:
        if isinstance(node, ast.Import):
            for name in node.names:
                global_names.add(name.asname or name.name)
        elif isinstance(node, ast.ImportFrom):
            for name in node.names:
                global_names.add(name.asname or name.name)
        elif isinstance(node, ast.FunctionDef):
            global_names.add(node.name)
        elif isinstance(node, ast.ClassDef):
            global_names.add(node.name)
        elif isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name):
                    global_names.add(target.id)
                elif isinstance(target, ast.Tuple):
                    for elt in target.elts:
                        if isinstance(elt, ast.Name):
                            global_names.add(elt.id)
                    
    # Now inspect inside functions
    errors_found = 0
    top_level_functions = {n for n in tree.body if isinstance(n, ast.FunctionDef)}
    
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node in top_level_functions:
            local_names = set()
            for arg in node.args.posonlyargs + node.args.args + node.args.kwonlyargs:
                local_names.add(arg.arg)
            if node.args.vararg:
                local_names.add(node.args.vararg.arg)
            if node.args.kwarg:
                local_names.add(node.args.kwarg.arg)
                
            # Collect local assigns and loop variables
            for child in ast.walk(node):
                if isinstance(child, ast.Assign):
                    for target in child.targets:
                        if isinstance(target, ast.Name):
                            local_names.add(target.id)
                        elif isinstance(target, ast.Tuple):
                            for elt in target.elts:
                                if isinstance(elt, ast.Name):
                                    local_names.add(elt.id)
                elif isinstance(child, ast.For):
                    if isinstance(child.target, ast.Name):
                        local_names.add(child.target.id)
                    elif isinstance(child.target, ast.Tuple):
                        for elt in child.target.elts:
                            if isinstance(elt, ast.Name):
                                local_names.add(elt.id)
                elif isinstance(child, ast.comprehension):
                    if isinstance(child.target, ast.Name):
                        local_names.add(child.target.id)
                elif isinstance(child, ast.Import):
                    for name in child.names:
                        local_names.add(name.asname or name.name)
                elif isinstance(child, ast.ImportFrom):
                    for name in child.names:
                        local_names.add(name.asname or name.name)
                elif isinstance(child, ast.ExceptHandler):
                    if child.name:
                        local_names.add(child.name)
                elif isinstance(child, ast.With):
                    for item in child.items:
                        if item.optional_vars and isinstance(item.optional_vars, ast.Name):
                            local_names.add(item.optional_vars.id)
                elif isinstance(child, ast.Lambda):
                    for arg in child.args.posonlyargs + child.args.args + child.args.kwonlyargs:
                        local_names.add(arg.arg)
                elif isinstance(child, ast.FunctionDef) and child != node:
                    local_names.add(child.name)
                    for arg in child.args.posonlyargs + child.args.args + child.args.kwonlyargs:
                        local_names.add(arg.arg)
                        
            # Check used names
            for child in ast.walk(node):
                if isinstance(child, ast.Name) and isinstance(child.ctx, ast.Load):
                    name = child.id
                    # Ignore common flask config or variables
                    if name in ["app", "db", "current_user", "request", "session", "g", "flash", "redirect", "url_for", "render_template", "send_from_directory"]:
                        continue
                    if name not in global_names and name not in local_names:
                        print(f"ERROR: Function '{node.name}' uses undefined name: '{name}' at line {child.lineno}")
                        errors_found += 1
                        
    if errors_found == 0:
        print("Success: No undefined names found!")
    else:
        print(f"Done: Found {errors_found} undefined name errors.")
        sys.exit(1)

if __name__ == "__main__":
    check_file('app.py')
