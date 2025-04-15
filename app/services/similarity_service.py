from typing import Dict, List

def find_common_archetypes(
    archetypes1: List[str],
    archetypes2: List[str]
) -> List[str]:
    """Find common archetypes between two users."""

    common_archetypes = set(archetypes1).intersection(set(archetypes2))

    return list(common_archetypes)
