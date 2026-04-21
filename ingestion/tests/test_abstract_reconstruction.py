"""Unit tests for abstract reconstruction from OpenAlex inverted index.

No live network or database required.
"""

import sys
import os

# Allow import from src/ without pip install
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from thrn_ingest.ingest_works import reconstruct_abstract


class TestReconstructAbstract:
    def test_none_input(self) -> None:
        assert reconstruct_abstract(None) is None

    def test_empty_dict(self) -> None:
        assert reconstruct_abstract({}) is None

    def test_single_word(self) -> None:
        result = reconstruct_abstract({"Hello": [0]})
        assert result == "Hello"

    def test_two_words_in_order(self) -> None:
        result = reconstruct_abstract({"Hello": [0], "World": [1]})
        assert result == "Hello World"

    def test_two_words_reverse_order(self) -> None:
        """Positions should be used to order, not iteration order."""
        result = reconstruct_abstract({"World": [1], "Hello": [0]})
        assert result == "Hello World"

    def test_multi_position_word(self) -> None:
        """A word appearing at multiple positions."""
        result = reconstruct_abstract({"the": [0, 3], "cat": [1], "sat": [2]})
        assert result == "the cat sat the"

    def test_realistic_abstract(self) -> None:
        inverted = {
            "Tourism": [0],
            "is": [1],
            "a": [2],
            "major": [3],
            "industry": [4],
        }
        result = reconstruct_abstract(inverted)
        assert result == "Tourism is a major industry"

    def test_long_abstract_preserves_word_count(self) -> None:
        words = ["word"] * 50
        inverted = {f"w{i}": [i] for i in range(50)}
        result = reconstruct_abstract(inverted)
        assert result is not None
        assert len(result.split()) == 50

    def test_non_sequential_positions(self) -> None:
        """Positions need not start at 0 — all that matters is relative order."""
        result = reconstruct_abstract({"beta": [5], "alpha": [2]})
        assert result == "alpha beta"
