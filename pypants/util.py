"""Utility functions"""

import ast
from pathlib import Path
import subprocess
from typing import Set

import astor
import black


class ModuleImportVisitor(ast.NodeVisitor):
    """AST visitor for collecting imports from a module"""

    def __init__(self) -> None:
        self.imports = set()

    def visit_ImportFrom(self, node) -> None:
        """Collect an import when specified as `from foo import bar`"""
        if node.module is not None:
            self.imports.add(node.module.split(".")[0])

    def visit_Import(self, node) -> None:
        """Collect an import when specified as `import foo`"""
        self.imports.add(node.names[0].name.split(".")[0])


def gather_dependencies_from_module(path: str) -> Set[str]:
    """Gather a set of other build targets from a single Python module

    Args:
        path: Python module path

    Returns:
        set of package names that were imported in the module

    """
    with open(path) as f:
        contents = f.read()
    tree = ast.parse(contents)
    visitor = ModuleImportVisitor()
    visitor.visit(tree)
    return visitor.imports


def write_build_file(tree: ast.Module, build_file_path: str) -> None:
    """Format and write a BUILD file from an AST module tree.

    The final output is auto-formatted using Black.

    Args:
        tree: AST module for the BUILD file
        build_file_path: Output path to write the BUILD file

    """
    build_text = black.format_str(
        astor.to_source(tree), mode=black.FileMode(line_length=88)
    )
    with open(build_file_path, "w") as f:
        f.write(build_text)


def get_git_top_level_path() -> Path:
    """Get the path of the git repository where this CLI is running"""
    proc = subprocess.run(
        ["git", "rev-parse", "--show-toplevel"], check=True, stdout=subprocess.PIPE
    )
    output = proc.stdout.decode("utf-8").strip()
    return Path(output)
