import importlib

from src import config as config_module


def test_supabase_project_ref_is_derived_from_supabase_url(monkeypatch):
    monkeypatch.delenv("SUPABASE_PROJECT_REF", raising=False)
    monkeypatch.setenv("SUPABASE_URL", "https://hnawojlnfoaccinlgjyn.supabase.co")

    config = importlib.reload(config_module)

    assert config.SUPABASE_PROJECT_REF == "hnawojlnfoaccinlgjyn"
    assert config.SUPABASE_STORAGE_URL == "https://hnawojlnfoaccinlgjyn.supabase.co/storage/v1"


def test_supabase_project_ref_has_no_hardcoded_fallback(monkeypatch):
    monkeypatch.delenv("SUPABASE_PROJECT_REF", raising=False)
    monkeypatch.delenv("SUPABASE_URL", raising=False)

    config = importlib.reload(config_module)

    assert config.SUPABASE_PROJECT_REF == ""
    assert config.SUPABASE_STORAGE_URL == ""
