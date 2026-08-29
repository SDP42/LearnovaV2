"""
Tests for Learnova Day 7 — Educational Content Enhancement Engine.
Run with: pytest tests/test_enhancement.py -v
"""

from __future__ import annotations

import os
import sys
from typing import Any, Dict, List, Optional
from unittest.mock import MagicMock

import pytest


from learnova.parsers.schema import SlidePageEntity, TextBlockElement, EquationElement
from learnova.intelligence.engine import SlideIntelligenceEngine
from learnova.intelligence.schema import SlideIntelligence
from learnova.intelligence.transformation import SlideTransformationEngine, TransformationPlan
from learnova.providers.base import LLMProvider
from learnova.enhancement.schema import EnhancedSlide
from learnova.enhancement.engine import ContentEnhancementEngine


# ═══════════════════════════════════════════════════════════════════════════════
# Shared fixtures
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.fixture
def sample_slide() -> SlidePageEntity:
    """Photosynthesis slide reused from previous day tests."""
    return SlidePageEntity(
        id=1,
        unit_number=1,
        title="Photosynthesis Mechanism & Energy Production",
        text_blocks=[
            TextBlockElement(
                id="tb_title",
                text="Photosynthesis Mechanism & Energy Production",
                is_heading=True,
                heading_level=1,
                font_size=24.0,
                reading_order=0,
            ),
            TextBlockElement(
                id="tb_obj",
                text="Students will understand how plants convert light energy into chemical energy.",
                is_heading=False,
                bullet_level=0,
                reading_order=1,
            ),
            TextBlockElement(
                id="tb_def",
                text="Photosynthesis is defined as the biological process of converting solar energy into glucose.",
                is_heading=False,
                is_bold=True,
                bullet_level=0,
                reading_order=2,
            ),
            TextBlockElement(
                id="tb_step1",
                text="Step 1: Light absorption by chlorophyll pigment in thylakoid membranes.",
                is_heading=False,
                bullet_level=1,
                reading_order=3,
            ),
            TextBlockElement(
                id="tb_step2",
                text="Step 2: Water photolysis splits H2O molecules into hydrogen ions and oxygen gas.",
                is_heading=False,
                bullet_level=1,
                reading_order=4,
            ),
            TextBlockElement(
                id="tb_step3",
                text="Step 3: Carbon fixation in Calvin cycle produces glucose with 84% conversion efficiency.",
                is_heading=False,
                bullet_level=1,
                reading_order=5,
            ),
            TextBlockElement(
                id="tb_stat",
                text="Research shows 84% efficiency under optimal 25°C temperature.",
                is_heading=False,
                bullet_level=0,
                reading_order=6,
            ),
            TextBlockElement(
                id="tb_footer",
                text="Page 1 / 10 | Confidential",
                is_heading=False,
                reading_order=7,
            ),
        ],
        equations=[
            EquationElement(
                id="eq_1",
                latex_expression="6CO2 + 6H2O -> C6H12O6 + 6O2",
                ascii_fallback="6CO2 + 6H2O -> C6H12O6 + 6O2",
            )
        ],
    )


@pytest.fixture
def slide_intel(sample_slide) -> SlideIntelligence:
    engine = SlideIntelligenceEngine()
    return engine.analyze_slide(sample_slide)


@pytest.fixture
def transformation_plan(sample_slide, slide_intel) -> TransformationPlan:
    engine = SlideTransformationEngine()
    return engine.plan_transformation(slide_intel, sample_slide)


# ─────────────────────────────────────────────────────────────────────────────
# Offline mock LLM that returns valid JSON payloads
# ─────────────────────────────────────────────────────────────────────────────

class _MockLLMProvider(LLMProvider):
    """Deterministic mock that returns valid JSON without any API call."""

    def generate(self, prompt: str, system_prompt: Optional[str] = None, **kwargs: Any) -> str:
        # Detect which generator is calling based on system_prompt content
        sp = (system_prompt or "").lower()
        p = prompt.lower()
        if "revision" in sp or "revision_points" in sp:
            return (
                '{"improved_explanation": "Enhanced explanation here.",'
                ' "simplified_explanation": "Simple explanation here.",'
                ' "revision_points": ["Point 1.", "Point 2.", "Point 3."],'
                ' "common_mistakes": ["Mistake 1.", "Mistake 2."]}'
            )
        if "interview" in sp or "discussion" in sp or "assessment" in sp:
            return (
                '{"interview_questions": ["Q1?", "Q2?", "Q3?"],'
                ' "discussion_questions": ["Why X?", "How Y?", "What if Z?"]}'
            )
        if "mnemonic" in sp or "memory aid" in sp or "cognitive" in sp:
            return (
                '{"mnemonic": "LIGHT: L=Light absorption, I=Ion splitting, G=Glucose synthesis, H=H2O photolysis, T=Temperature effects.",'
                ' "learning_tips": ["Use spaced repetition for the 3 steps.", "Draw the Calvin cycle diagram."]}'
            )
        if "analogies" in sp or "analogies" in p:
            return '["Analogy 1.", "Analogy 2."]'
        if "application" in sp or "applications" in p:
            return '["In healthcare: app 1.", "In finance: app 2.", "In agriculture: app 3."]'
        if "examples" in sp or "real-world examples" in p:
            return '["Example A.", "Example B.", "Example C."]'
        # Fallback
        return '[]'

    def chat(self, messages: List[Dict[str, str]], **kwargs: Any) -> str:
        return self.generate(messages[-1]["content"] if messages else "", **kwargs)

    def rewrite(self, text: str, instructions: str, **kwargs: Any) -> str:
        return text


# ═══════════════════════════════════════════════════════════════════════════════
# Schema Tests
# ═══════════════════════════════════════════════════════════════════════════════

class TestEnhancedSlideSchema:
    def test_all_fields_present(self):
        """EnhancedSlide must expose all 14 required fields."""
        slide = EnhancedSlide(slide_id=1, slide_title="Test")
        required_fields = [
            "slide_id", "slide_title", "improved_explanation",
            "simplified_explanation", "examples", "analogies",
            "real_world_applications", "common_mistakes",
            "interview_questions", "revision_points", "mnemonic",
            "discussion_questions", "learning_tips", "confidence",
        ]
        for field_name in required_fields:
            assert hasattr(slide, field_name), f"Missing field: {field_name}"

    def test_default_types(self):
        slide = EnhancedSlide(slide_id=42, slide_title="Test Slide")
        assert isinstance(slide.examples, list)
        assert isinstance(slide.analogies, list)
        assert isinstance(slide.real_world_applications, list)
        assert isinstance(slide.common_mistakes, list)
        assert isinstance(slide.interview_questions, list)
        assert isinstance(slide.revision_points, list)
        assert isinstance(slide.discussion_questions, list)
        assert isinstance(slide.learning_tips, list)
        assert isinstance(slide.mnemonic, str)
        assert isinstance(slide.confidence, float)

    def test_to_dict_has_all_keys(self):
        slide = EnhancedSlide(slide_id=5, slide_title="Dict Test")
        d = slide.to_dict()
        for field_name in [
            "slide_id", "slide_title", "improved_explanation",
            "simplified_explanation", "examples", "analogies",
            "real_world_applications", "common_mistakes", "interview_questions",
            "revision_points", "mnemonic", "discussion_questions",
            "learning_tips", "confidence",
        ]:
            assert field_name in d, f"to_dict() missing: {field_name}"

    def test_to_json_is_valid(self):
        import json
        slide = EnhancedSlide(
            slide_id=7,
            slide_title="JSON Test",
            examples=["example 1"],
            confidence=0.75,
        )
        json_str = slide.to_json()
        parsed = json.loads(json_str)
        assert parsed["slide_id"] == 7
        assert parsed["confidence"] == 0.75

    def test_summary_line(self):
        slide = EnhancedSlide(
            slide_id=3,
            slide_title="Summary Test",
            improved_explanation="Good explanation",
            examples=["e1", "e2"],
            confidence=0.6,
        )
        summary = slide.summary_line()
        assert "EnhancedSlide 3" in summary
        assert "Summary Test" in summary
        assert "0.60" in summary


# ═══════════════════════════════════════════════════════════════════════════════
# Engine — Offline (Mock LLM) Tests
# ═══════════════════════════════════════════════════════════════════════════════

class TestContentEnhancementEngineOffline:
    def test_engine_requires_llm_provider(self):
        with pytest.raises(TypeError):
            ContentEnhancementEngine("not_a_provider")

    def test_engine_accepts_llm_provider(self):
        engine = ContentEnhancementEngine(_MockLLMProvider())
        assert engine is not None

    def test_enhance_returns_enhanced_slide(self, slide_intel, transformation_plan):
        engine = ContentEnhancementEngine(_MockLLMProvider(), delay=0.0)
        result = engine.enhance(transformation_plan, slide_intel)
        assert isinstance(result, EnhancedSlide)

    def test_enhanced_slide_has_correct_identity(self, slide_intel, transformation_plan):
        engine = ContentEnhancementEngine(_MockLLMProvider(), delay=0.0)
        result = engine.enhance(transformation_plan, slide_intel)
        assert result.slide_id == slide_intel.slide_id
        assert result.slide_title == slide_intel.slide_title

    def test_all_generator_fields_populated(self, slide_intel, transformation_plan):
        engine = ContentEnhancementEngine(_MockLLMProvider(), delay=0.0)
        result = engine.enhance(transformation_plan, slide_intel)
        assert len(result.examples) > 0, "examples should be populated"
        assert len(result.analogies) > 0, "analogies should be populated"
        assert len(result.real_world_applications) > 0, "applications should be populated"
        assert len(result.revision_points) > 0, "revision_points should be populated"
        assert len(result.common_mistakes) > 0, "common_mistakes should be populated"
        assert len(result.interview_questions) > 0, "interview_questions should be populated"
        assert len(result.discussion_questions) > 0, "discussion_questions should be populated"
        assert result.mnemonic != "", "mnemonic should be populated"
        assert len(result.learning_tips) > 0, "learning_tips should be populated"
        assert result.improved_explanation != "", "improved_explanation should be populated"
        assert result.simplified_explanation != "", "simplified_explanation should be populated"

    def test_confidence_in_valid_range(self, slide_intel, transformation_plan):
        engine = ContentEnhancementEngine(_MockLLMProvider(), delay=0.0)
        result = engine.enhance(transformation_plan, slide_intel)
        assert 0.0 <= result.confidence <= 1.0, (
            f"confidence out of range: {result.confidence}"
        )

    def test_graceful_fallback_when_generator_fails(self, slide_intel, transformation_plan):
        """Engine must not raise when a generator throws an exception."""
        failing_llm = _MockLLMProvider()
        # Make generate raise an error
        failing_llm.generate = MagicMock(side_effect=RuntimeError("Simulated API failure"))
        engine = ContentEnhancementEngine(failing_llm, delay=0.0)
        result = engine.enhance(transformation_plan, slide_intel)
        # Should still return a valid EnhancedSlide (all fields empty)
        assert isinstance(result, EnhancedSlide)
        assert 0.0 <= result.confidence <= 1.0

    def test_to_dict_is_serializable(self, slide_intel, transformation_plan):
        import json
        engine = ContentEnhancementEngine(_MockLLMProvider(), delay=0.0)
        result = engine.enhance(transformation_plan, slide_intel)
        json_str = result.to_json()
        parsed = json.loads(json_str)
        assert "slide_id" in parsed
        assert "confidence" in parsed


# ═══════════════════════════════════════════════════════════════════════════════
# Engine — Live API Tests (Groq key required)
# ═══════════════════════════════════════════════════════════════════════════════

class TestContentEnhancementEngineLive:
    @pytest.mark.skipif(
        not os.getenv("GROQ_API_KEY"),
        reason="GROQ_API_KEY not set",
    )
    def test_live_enhance_photosynthesis(self, slide_intel, transformation_plan):
        # Go through the router, not a bare GroqProvider, so the test exercises
        # the real failover chain (Groq -> Gemini -> NVIDIA) instead of dying on
        # a single provider's daily quota.
        from learnova.providers.router import get_router

        router = get_router()
        if not router.available:
            pytest.skip("no LLM provider configured")

        engine = ContentEnhancementEngine(router, delay=0.5)
        result = engine.enhance(
            transformation_plan, slide_intel, temperature=0.4, max_tokens=500,
        )
        assert isinstance(result, EnhancedSlide)
        assert result.slide_id == slide_intel.slide_id
        assert 0.0 <= result.confidence <= 1.0

        total_filled = sum([
            bool(result.improved_explanation),
            bool(result.simplified_explanation),
            bool(result.examples),
            bool(result.revision_points),
            bool(result.interview_questions),
        ])
        if total_filled == 0:
            pytest.skip("every provider rate-limited / unavailable right now")
        assert total_filled >= 3, (
            f"Live test: only {total_filled}/5 core fields populated"
        )
        print(f"\n✅ Live EnhancedSlide:\n{result.to_json()}")
