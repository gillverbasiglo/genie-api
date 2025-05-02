from typing import Dict, List

def find_common_archetypes(
    archetypes1: List[Dict[str, str]],
    archetypes2: List[Dict[str, str]]
) -> List[str]:
    """Find common archetypes between two users."""
    archetypes1_keys = [archetype["name"] for archetype in archetypes1] 
    archetypes2_keys = [archetype["name"] for archetype in archetypes2]
    common_archetypes = set(archetypes1_keys).intersection(set(archetypes2_keys))

    return list(common_archetypes)
