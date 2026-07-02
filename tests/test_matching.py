from job_tracker.utils.matching import is_duplicate_application, clean_company_name, clean_role_name


def test_clean_company_name():
    """Verifies corporate suffixes and punctuation are stripped correctly."""
    assert clean_company_name("Google LLC") == "google"
    assert clean_company_name("Microsoft Corporation") == "microsoft"
    assert clean_company_name("Netflix, Inc.") == "netflix"
    assert clean_company_name("Uber Technologies") == "uber"
    assert clean_company_name("Stripe India") == "stripe"
    assert clean_company_name("Apple") == "apple"
    assert clean_company_name("") == ""


def test_clean_role_name():
    """Verifies role names are normalized to lowercase and whitespace-stripped."""
    assert clean_role_name("Senior Software Engineer") == "senior software engineer"
    assert clean_role_name("AI Engineer / Researcher") == "ai engineer / researcher"
    assert clean_role_name("") == ""


def test_is_duplicate_application_matches():
    """Verifies that fuzzy matching correctly identifies duplicates."""
    assert is_duplicate_application("Google", "Software Engineer", "Google", "Software Engineer")
    assert is_duplicate_application("Microsoft Corporation", "Software Engineer", "Microsoft", "Software Engineer")
    assert is_duplicate_application("Google LLC", "AI Architect", "Google", "AI Architect")
    assert is_duplicate_application("Apple Inc", "Staff Software Engineer", "Apple", "Software Engineer, Staff")
    assert is_duplicate_application("Amazon India", "Developer", "Amazon", "Developer")


def test_is_duplicate_application_non_matches():
    """Verifies that fuzzy matching correctly rejects non-duplicates."""
    assert not is_duplicate_application("Google", "Software Engineer", "Microsoft", "Software Engineer")
    assert not is_duplicate_application("Google", "Software Engineer", "Google", "Product Manager")
    assert not is_duplicate_application("Apple", "Designer", "Meta", "Recruiter")
