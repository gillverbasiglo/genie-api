from typing import Dict, List

def find_common_archetypes(
    archetypes1: List[str],
    archetypes2: List[str]
) -> Dict[str, float]:
    """Find common archetypes between two users."""

    common_archetypes = archetypes1.intersection(archetypes2)

    return common_archetypes
