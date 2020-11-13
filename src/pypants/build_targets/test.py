"""Contains PythonTestPackage class"""
import ast

from .python_package import PythonPackage


class PythonTestPackage(PythonPackage):
    """Represents a Python test package build target in Pants"""

    def __init__(self, *args, code_target_package_name: str = None, **kwargs) -> None:
        """
        Args:
            code_target_package_name: Package name for the code package that this test
                package is testing
        """
        super().__init__(*args, **kwargs)
        self.code_target_package_name = code_target_package_name

    def _generate_python_tests_ast_node(self) -> ast.Expr:
        """Generate an AST node for a python_tests Pants target"""
        keywords = [
            ast.keyword(
                arg="dependencies",
                value=ast.List(elts=[ast.Str(f":{self.rendered_package_name}")]),
            ),
            ast.keyword(arg="sources", value=ast.List(elts=[ast.Str("**/*.py")])),
            self._tags_keyword,
        ]
        node = ast.Expr(
            value=ast.Call(func=ast.Name(id="python_tests"), args=[], keywords=keywords)
        )
        return node

    def generate_build_file_ast_node(self) -> ast.Module:
        """Generate a Pants BUILD file as an AST module node"""
        body = [
            self._generate_python_library_ast_node(
                name=self.rendered_package_name, include_extra_dependencies=True
            ),
            self._generate_python_tests_ast_node(),
            self._generate_pex_binary_wrapper_node(
                "unittest", dependencies=[f":{self.rendered_package_name}"]
            ),
        ]
        if self.config.generate_pytest_binary:
            body.append(
                self._generate_pex_binary_wrapper_node(
                    "pytest", dependencies=[f":{self.rendered_package_name}"]
                )
            )
        if self.config.resource_glob_path:
            body.append(self._generate_python_library_resources_ast_node())
        node = ast.Module(body=body)
        return node
