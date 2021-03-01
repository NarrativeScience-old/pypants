"""Contains PythonLambdaPackage class"""
import ast
import logging

from ..exceptions import NoConsoleScriptFound  # noqa
from .binary import PythonBinaryPackage  # noqa

logger = logging.getLogger(__name__)


class PythonLambdaPackage(PythonBinaryPackage):
    """Represents a Python Lambda Function build target in Pants

    The Lambda build target is similar to a binary but has a python_awslambda target.
    """

    @property
    def dependency_target(self) -> str:
        """Returns the representation of this target in another target's dependencies

        It's not good practice to depend on a server/binary package (apart from
        tests), but if that happens we need to set the dependency target to
        `:lib` so it correctly references the `python_library` target.
        """
        return f"{self.key}:lib"

    def _generate_python_binary_cli_ast_node(self) -> ast.Expr:
        """Generate an AST node for a python_binary Pants target that runs lambda_handler.py"""  # noqa
        node = ast.Expr(
            value=ast.Call(
                func=ast.Name(id="python_binary"),
                args=[],
                keywords=[
                    ast.keyword(arg="name", value=ast.Str("bin")),
                    ast.keyword(
                        arg="dependencies", value=ast.List(elts=[ast.Str(":lib")])
                    ),
                    ast.keyword(
                        arg="sources",
                        value=ast.List(
                            elts=[ast.Str(f"{self.package_name}/lambda_handler.py")]
                        ),
                    ),
                    ast.keyword(
                        arg="zip_safe", value=ast.NameConstant(self.config.zip_safe)
                    ),
                    self._tags_keyword,
                ],
            )
        )
        return node

    def _generate_python_lambda_ast_node(self) -> ast.Expr:
        """Generate an AST node for a python_awslambda Pants target"""
        binary_name, _ = self._parse_entry_point()
        node = ast.Expr(
            value=ast.Call(
                func=ast.Name(id="python_awslambda"),
                args=[],
                keywords=[
                    ast.keyword(arg="name", value=ast.Str(binary_name)),
                    ast.keyword(
                        arg="dependencies", value=ast.List(elts=[ast.Str(":bin")])
                    ),
                    ast.keyword(
                        arg="handler",
                        value=ast.Str(
                            f"{self.package_name}.lambda_handler:lambda_handler"
                        ),
                    ),
                    ast.keyword(
                        arg="runtime", value=ast.Str(self.config.default_python_runtime)
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
            self._generate_python_lambda_ast_node(),
        ]
        if self.config.generate_local_binary:
            body.append(self._generate_python_binary_local_ast_node())
        node = ast.Module(body=body)
        return node
