import re
from typing import Optional
from rapidfuzz import fuzz
from ..config.settings import settings


def clean_company_name(name: str) -> str:
    """Cleans common corporate suffixes and punctuation to improve matching accuracy.

    Args:
        name: Raw company name.

    Returns:
        Cleaned lowercase company name string.
    """
    if not name:
        return ""
    
    name = name.lower().strip()
    
    # Remove punctuation
    name = re.sub(r"[^\w\s]", "", name)
    
    # Suffixes to filter out
    suffixes = {
        "llc", "inc", "corp", "corporation", "co", "ltd", "limited", 
        "india", "technologies", "tech", "solutions", "group", "services"
    }
    
    words = name.split()
    cleaned_words = [w for w in words if w not in suffixes]
    
    # If stripping all words leaves it empty, return original lowercased string
    if not cleaned_words:
        return name
        
    return " ".join(cleaned_words).strip()


def clean_role_name(role: str) -> str:
    """Cleans role strings by stripping common level indicators for cleaner comparisons."""
    if not role:
        return ""
    role = role.lower().strip()
    # Remove punctuation
    role = re.sub(r"[^\w\s/]", "", role)
    return role


def is_duplicate_application(
    comp_a: str,
    role_a: str,
    comp_b: str,
    role_b: str,
    threshold: Optional[float] = None
) -> bool:
    """Uses fuzzy logic to determine if two application company/role combinations are duplicates.

    Args:
        comp_a: First company name.
        role_a: First role name.
        comp_b: Second company name.
        role_b: Second role name.
        threshold: Matching similarity score threshold (0-100). Defaults to settings.

    Returns:
        True if company and role exceed matching threshold, False otherwise.
    """
    if threshold is None:
        # Pydantic settings loads config
        threshold = settings.fuzzy_match_threshold

    clean_c_a = clean_company_name(comp_a)
    clean_c_b = clean_company_name(comp_b)
    
    clean_r_a = clean_role_name(role_a)
    clean_r_b = clean_role_name(role_b)
    
    # token_set_ratio is highly resilient to extra words/suffixes in company names
    company_score = fuzz.token_set_ratio(clean_c_a, clean_c_b)
    
    # token_sort_ratio handles word order swaps (e.g. "Software Engineer, AI" vs "AI Software Engineer")
    role_score = fuzz.token_sort_ratio(clean_r_a, clean_r_b)
    
    # Log comparison matching details
    return company_score >= threshold and role_score >= threshold
