"""Contains PythonBehaveTestPackage class"""
import ast

from .test import PythonTestPackage


class PythonBehaveTestPackage(PythonTestPackage):
    """Represents a Python test package build target in Pants that uses behave"""

    def _generate_python_binary_behave_wrapper_node(self) -> ast.Expr:
        """Generate an AST node for a python_binary Pants target that wraps behave"""
        node = ast.Expr(
            value=ast.Call(
                func=ast.Name(id="python_binary"),
                args=[],
                keywords=[
                    ast.keyword(
                        arg="sources", value=ast.List(elts=[ast.Str("behave_cli.py")])
                    ),
                    ast.keyword(
                        arg="dependencies", value=ast.List(elts=[ast.Str(":lib")])
                    ),
                    self._tags_keyword,
                ],
            )
        )
        return node

    def generate_build_file_ast_node(self) -> ast.Module:
        """Generate a Pants BUILD file as an AST module node"""
        node = ast.Module(
            body=[
                self._generate_python_library_ast_node(name="lib"),
                self._generate_python_binary_behave_wrapper_node(),
                self._generate_python_library_resources_ast_node(),
            ]
        )
        return node
