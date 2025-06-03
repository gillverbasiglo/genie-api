# app/utils/mem0_helpers.py


from app.core.mem0.memory_categories import MEM0_CATEGORIES


def build_metadata(category_key: str, extra: dict = None):
    if category_key not in MEM0_CATEGORIES:
        raise ValueError(f"Unknown Mem0 category: {category_key}")
    
    metadata = {
        "category": category_key,
        "category_description": MEM0_CATEGORIES[category_key]
    }
    if extra:
        metadata.update(extra)
    return metadata
