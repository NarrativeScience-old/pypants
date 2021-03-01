"""Contains PythonBinaryPackage class"""
import ast
import logging
import os
from typing import Tuple

import astor

from ..exceptions import NoConsoleScriptFound  # noqa
from .python_package import PythonPackage  # noqa

logger = logging.getLogger(__name__)


class GetConsoleScript(ast.NodeVisitor):
    """AST node visitor for finding the console_script string in setup.py"""

    def __init__(self) -> None:
        super(GetConsoleScript).__init__()
        # Example specifier: ``mybinary = my_package.cli:main``
        self.console_script_specifier = None

    def visit_keyword(self, node) -> None:
        """Visitor for keyword nodes"""
        if node.arg == "entry_points":
            for key, value in zip(node.value.keys, node.value.values):
                if key.s == "console_scripts":
                    self.console_script_specifier = value.elts[0].s
                    break


class PythonBinaryPackage(PythonPackage):
    """Represents a Python CLI or server package build target in Pants

    CLIs and servers have an entry point, meaning they are meant to be executed
    directly.
    """

    @property
    def dependency_target(self) -> str:
        """Returns the representation of this target in another target's dependencies

        It's not good practice to depend on a server/binary package (apart from
        tests), but if that happens we need to set the dependency target to
        `:lib` so it correctly references the `python_library` target.
        """
        return f"{self.key}:lib"

    def _parse_entry_point(self) -> Tuple[str, str]:
        """Get the CLI binary name and source module path from setup.py

        Returns:
            Tuple of:
                * **binary name**
                * **source module path**

        """
        setup_py_path = os.path.join(self.package_dir_path, "setup.py")
        tree = astor.code_to_ast.parse_file(setup_py_path)
        visitor = GetConsoleScript()
        visitor.visit(tree)
        if visitor.console_script_specifier is None:
            raise NoConsoleScriptFound(
                f"Could not generate BUILD file for {self.key} because no"
                f" console_scripts found in {setup_py_path}"
            )

        logger.debug(
            f"Found console_script in {setup_py_path}:"
            f" {visitor.console_script_specifier}"
        )
        # Example specifier: ``mybinary = my_package.cli:main``
        # Final binary name: ``mybinary``
        # Final source module path: ``my_package/cli.py``
        binary_name, entry_point = visitor.console_script_specifier.split("=")
        binary_name = binary_name.strip()
        entry_point_parts = entry_point.strip().split(":")[0].split(".")
        entry_point_parts[-1] += ".py"
        source_module_path = "/".join(entry_point_parts)

        logger.debug(
            f"Using binary_name={binary_name} source_module_path={source_module_path}"
        )
        return binary_name, source_module_path

    def _generate_python_binary_cli_ast_node(self) -> ast.Expr:
        """Generate an AST node for a python_binary Pants target"""
        binary_name, source_module_path = self._parse_entry_point()
        node = ast.Expr(
            value=ast.Call(
                func=ast.Name(id="python_binary"),
                args=[],
                keywords=[
                    ast.keyword(arg="name", value=ast.Str(binary_name)),
                    ast.keyword(
                        arg="dependencies", value=ast.List(elts=[ast.Str(":lib")])
                    ),
                    ast.keyword(
                        arg="sources",
                        value=ast.List(elts=[ast.Str(source_module_path)]),
                    ),
                    ast.keyword(
                        arg="zip_safe", value=ast.NameConstant(self.config.zip_safe)
                    ),
                    self._tags_keyword,
                ],
            )
        )
        return node

    def _generate_python_binary_local_ast_node(self) -> ast.Expr:
        """Generate an AST node for a python_binary Pants target that runs local.py"""
        node = ast.Expr(
            value=ast.Call(
                func=ast.Name(id="python_binary"),
                args=[],
                keywords=[
                    ast.keyword(arg="name", value=ast.Str("local")),
                    ast.keyword(
                        arg="dependencies",
                        value=ast.List(
                            elts=[ast.Str("3rdparty/python:aiohttp"), ast.Str(":lib")]
                        ),
                    ),
                    ast.keyword(
                        arg="sources",
                        value=ast.List(elts=[ast.Str(f"{self.package_name}/local.py")]),
                    ),
                    self._tags_keyword,
                ],
            )
        )
        return node

    def generate_build_file_ast_node(self) -> ast.Module:
        """Generate a Pants BUILD file as an AST module node"""
        body = [
            self._generate_python_library_ast_node(
                name="lib", globs_path=f"{self.package_name}/**/*.py"
            ),
            self._generate_python_binary_cli_ast_node(),
        ]
        if self.config.generate_local_binary:
            body.append(self._generate_python_binary_local_ast_node())
        if self.config.resource_glob_path:
            body.append(self._generate_python_library_resources_ast_node())
        node = ast.Module(body=body)
        return node
