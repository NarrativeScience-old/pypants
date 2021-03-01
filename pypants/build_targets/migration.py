"""Contains AlembicMigrationPackage class"""
import ast

from .python_package import PythonPackage


class AlembicMigrationPackage(PythonPackage):
    """Represents an Alembic database migration bundle target in Pants"""

    def _generate_bundle_item(self, glob: str) -> ast.Call:
        """Generate an AST node for a bundle item for use in a python_app target"""
        return ast.Call(
            func=ast.Name(id="bundle"),
            args=[],
            keywords=[ast.keyword(arg="fileset", value=ast.List(elts=[ast.Str(glob)]))],
        )

    def _generate_migrations_python_app_ast_node(self) -> ast.Expr:
        """Generate an AST node for a python_app Pants target that bundles migrations"""
        node = ast.Expr(
            value=ast.Call(
                func=ast.Name(id="python_app"),
                args=[],
                keywords=[
                    ast.keyword(arg="name", value=ast.Str(self.package_name)),
                    ast.keyword(arg="archive", value=ast.Str("tar")),
                    ast.keyword(arg="binary", value=ast.Str(":alembic")),
                    ast.keyword(
                        arg="bundles",
                        value=ast.List(
                            elts=[
                                self._generate_bundle_item(glob)
                                for glob in ["alembic.ini", "env.py", "versions/*.py"]
                            ]
                        ),
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
                self._generate_python_binary_wrapper_node(
                    "alembic", entry_point="alembic.config", dependencies=[":lib"]
                ),
                self._generate_migrations_python_app_ast_node(),
            ]
        )
        return node
