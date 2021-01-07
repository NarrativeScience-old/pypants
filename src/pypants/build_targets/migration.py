"""Contains AlembicMigrationPackage class"""
import ast
from typing import List

from .python_package import PythonPackage


class AlembicMigrationPackage(PythonPackage):
    """Represents an Alembic database migration bundle target in Pants"""

    def _generate_migrations_archive_ast_node(self) -> ast.Expr:
        """Generate an AST node for a archive Pants target that bundles migrations"""
        node = ast.Expr(
            value=ast.Call(
                func=ast.Name(id="archive"),
                args=[],
                keywords=[
                    ast.keyword(arg="name", value=ast.Str(self.package_name)),
                    ast.keyword(arg="format", value=ast.Str("tar")),
                    ast.keyword(
                        arg="packages", value=ast.List(elts=[ast.Str(":alembic")])
                    ),
                    ast.keyword(arg="files", value=ast.List(elts=[ast.Str(":files")])),
                    self._tags_keyword,
                ],
            )
        )
        return node

    def _generate_migrations_files_ast_node(self, sources: List[str]) -> ast.Expr:
        """Generate an AST node for a files Pants target that bundles migration files"""
        # Turn our list of sources into an ast list of ast strings
        ast_sources = []
        for source in sources:
            ast_sources.append(ast.Str(source))
        node = ast.Expr(
            value=ast.Call(
                func=ast.Name(id="files"),
                args=[],
                keywords=[
                    ast.keyword(arg="name", value=ast.Str("files")),
                    ast.keyword(arg="sources", value=ast.List(elts=ast_sources)),
                ],
            )
        )
        return node

    def generate_build_file_ast_node(self) -> ast.Module:
        """Generate a Pants BUILD file as an AST module node"""
        node = ast.Module(
            body=[
                self._generate_python_library_ast_node(name="lib"),
                self._generate_pex_binary_wrapper_node(
                    "alembic", entry_point="alembic.config", dependencies=[":lib"]
                ),
                self._generate_migrations_archive_ast_node(),
                self._generate_migrations_files_ast_node(
                    sources=["alembic.ini", "env.py", "versions/*.py"]
                ),
            ]
        )
        return node
