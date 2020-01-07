"""Defines BUILD_TARGET_MAP"""
from .base import BuildTarget
from .behave_ import PythonBehaveTestPackage
from .binary import PythonBinaryPackage
from .lambda_function import PythonLambdaPackage
from .library import PythonLibraryPackage
from .migration import AlembicMigrationPackage
from .py2sfn_project import PY2SFNProjectPackage
from .python_package import PythonPackage
from .requirement import PythonRequirement
from .test import PythonTestPackage

BUILD_TARGET_MAP = {
    "behave": PythonBehaveTestPackage,
    "binary": PythonBinaryPackage,
    "lambda": PythonLambdaPackage,
    "library": PythonLibraryPackage,
    "migration": AlembicMigrationPackage,
    "py2sfn_project": PY2SFNProjectPackage,
    "requirement": PythonRequirement,
    "test": PythonTestPackage,
}
