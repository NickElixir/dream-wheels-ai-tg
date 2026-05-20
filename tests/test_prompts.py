"""Тесты на промпт-билдер и RimDescription."""

from __future__ import annotations

import pytest

from src.prompts import BASE_PROMPT_TEMPLATE, NEGATIVE_PROMPT, build_prompt
from src.rim import RimDescription, extract_rim_description


def test_rim_default_values():
    rim = RimDescription()
    assert rim.spoke_count == 5
    assert rim.profile == "flat"
    assert rim.finish == "silver"
    assert rim.centre_cap is True


def test_rim_to_prompt_fragment_includes_all_fields():
    rim = RimDescription(spoke_count=7, profile="mesh", finish="bronze", centre_cap=False)
    fragment = rim.to_prompt_fragment()
    assert "7-spoke" in fragment
    assert "mesh" in fragment
    assert "bronze" in fragment
    assert "without a centre cap" in fragment


def test_rim_validates_spoke_count_range():
    with pytest.raises(ValueError):
        RimDescription(spoke_count=2)
    with pytest.raises(ValueError):
        RimDescription(spoke_count=21)


def test_rim_validates_profile_literal():
    with pytest.raises(ValueError):
        RimDescription(profile="random-style")  # type: ignore[arg-type]


def test_extract_rim_description_returns_defaults():
    rim = extract_rim_description("any-base64-stub")
    assert rim == RimDescription()


def test_build_prompt_default_uses_default_rim():
    prompt = build_prompt()
    assert "<img>0</img>" in prompt
    assert "<img>1</img>" in prompt
    assert "exact wheel design, color, finish" in prompt
    assert "Preserve original scene lighting" in prompt
    assert "5-spoke flat design" in prompt
    assert "Avoid:" in prompt
    assert "blurry" in prompt  # из NEGATIVE_PROMPT
    assert "studio lighting" not in prompt.lower()


def test_build_prompt_includes_rim_description():
    rim = RimDescription(spoke_count=10, profile="split", finish="matte-black")
    prompt = build_prompt(rim)
    assert "10-spoke split" in prompt
    assert "matte-black" in prompt


def test_negative_section_appended_at_end():
    prompt = build_prompt()
    assert prompt.rstrip(".").endswith(NEGATIVE_PROMPT)


def test_base_template_has_replacement_marker():
    """Защита от регрессии формата: build_prompt полагается на {rim_fragment}."""
    assert "{rim_fragment}" in BASE_PROMPT_TEMPLATE
