"""Contains base BuildTarget class"""
from functools import total_ordering


@total_ordering
class BuildTarget:
    """Represents a Python build target in Pants.

    This should be used as a mixin to provide common attributes and methods.
    """

    # This string will be used as an identifier for the build target
    key: str = None

    def __str__(self) -> str:
        """String representation"""
        return self.key

    def __eq__(self, other: "BuildTarget") -> bool:
        """Equality check"""
        return self.key == other.key

    def __hash__(self) -> int:
        """Object hash"""
        return hash((self.key,))

    def __repr__(self) -> str:
        """Object representation for debugging"""
        return self.key

    def __lt__(self, other: "BuildTarget") -> bool:
        """Less than comparator"""
        return self.key < other.key

    @property
    def dependency_target(self) -> str:
        """Returns the representation of this target in another target's dependencies"""
        return self.key
