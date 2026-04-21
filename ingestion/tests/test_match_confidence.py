"""Unit tests for the source-matching confidence scoring logic.

No live network or database required. Mocks the OpenAlexClient calls.
"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from thrn_ingest.match_sources import (
    _issn_from_source,
    _norm,
    _score_candidate,
    _trigram_score,
)
from thrn_ingest.models import Journal


# ---------------------------------------------------------------------------
# Helper builders
# ---------------------------------------------------------------------------

def _make_journal(
    display_name: str,
    issn_print: str | None = None,
    issn_online: str | None = None,
    manual_review_flag: bool = False,
) -> Journal:
    return Journal(
        display_name=display_name,
        normalized_name=display_name.lower(),
        issn_print=issn_print,
        issn_online=issn_online,
        manual_review_flag=manual_review_flag,
    )


def _make_source(
    oa_id: str,
    display_name: str,
    issns: list[str] | None = None,
    issn_l: str | None = None,
) -> dict:
    return {
        "id": f"https://openalex.org/{oa_id}",
        "display_name": display_name,
        "issns": issns or [],
        "issn_l": issn_l,
    }


# ---------------------------------------------------------------------------
# _norm
# ---------------------------------------------------------------------------

class TestNorm:
    def test_lowercases(self) -> None:
        assert _norm("Hello World") == "hello world"

    def test_strips_accents(self) -> None:
        result = _norm("Café")
        assert "cafe" in result

    def test_collapses_whitespace(self) -> None:
        assert _norm("  foo   bar  ") == "foo bar"

    def test_strips_punctuation(self) -> None:
        result = _norm("Annals of Tourism Research!")
        assert "!" not in result


# ---------------------------------------------------------------------------
# _issn_from_source
# ---------------------------------------------------------------------------

class TestIssnFromSource:
    def test_extracts_issn_list(self) -> None:
        source = {"issns": ["1234-5678", "9876-5432"], "issn_l": None}
        result = _issn_from_source(source)
        assert "1234-5678" in result
        assert "9876-5432" in result

    def test_includes_issn_l(self) -> None:
        source = {"issns": [], "issn_l": "1234-5678"}
        result = _issn_from_source(source)
        assert "1234-5678" in result

    def test_empty_source(self) -> None:
        assert _issn_from_source({}) == set()


# ---------------------------------------------------------------------------
# _trigram_score
# ---------------------------------------------------------------------------

class TestTrigramScore:
    def test_identical_strings(self) -> None:
        score = _trigram_score("Annals of Tourism Research", "Annals of Tourism Research")
        assert score == 1.0

    def test_completely_different(self) -> None:
        score = _trigram_score("Annals of Tourism Research", "Journal of Biochemistry")
        assert score < 0.5

    def test_close_but_not_identical(self) -> None:
        score = _trigram_score(
            "International Journal of Hospitality Management",
            "International Journal of Hospitality & Management",
        )
        assert score > 0.8


# ---------------------------------------------------------------------------
# _score_candidate
# ---------------------------------------------------------------------------

class TestScoreCandidate:
    def test_issn_print_exact_gives_1_0(self) -> None:
        journal = _make_journal("Annals of Tourism Research", issn_print="0160-7383")
        source = _make_source("S1234", "Annals of Tourism Research", issns=["0160-7383"])
        cand = _score_candidate(journal, source, issn_type="issn_print")
        assert cand is not None
        assert cand.confidence == 1.0
        assert cand.match_method == "issn_print"

    def test_issn_online_gives_0_98(self) -> None:
        journal = _make_journal("Tourism Mgmt", issn_online="1879-3193")
        source = _make_source("S5678", "Tourism Management", issns=["1879-3193"])
        cand = _score_candidate(journal, source, issn_type="issn_online")
        assert cand is not None
        assert cand.confidence == 0.98
        assert cand.match_method == "issn_online"

    def test_name_exact_gives_0_9(self) -> None:
        journal = _make_journal("Tourism Management")
        source = _make_source("S9012", "Tourism Management")
        cand = _score_candidate(journal, source)
        assert cand is not None
        assert cand.confidence == 0.90
        assert cand.match_method == "name_exact"

    def test_name_trigram_is_between_0_5_and_0_85(self) -> None:
        journal = _make_journal("Annals of Tourism Research")
        # Slightly different name — no ISSNs to match
        source = _make_source("S3333", "Annals of Tourist Research")
        cand = _score_candidate(journal, source)
        assert cand is not None
        assert 0.50 <= cand.confidence <= 0.85
        assert cand.match_method == "name_trigram"

    def test_source_without_id_returns_none(self) -> None:
        journal = _make_journal("Some Journal")
        source = {"display_name": "Some Journal", "issns": []}  # no "id" key
        cand = _score_candidate(journal, source)
        assert cand is None

    def test_short_id_extracted_from_url(self) -> None:
        journal = _make_journal("Tourism Management", issn_print="0261-5177")
        source = {
            "id": "https://openalex.org/S1234567890",
            "display_name": "Tourism Management",
            "issns": ["0261-5177"],
            "issn_l": "0261-5177",
        }
        cand = _score_candidate(journal, source, issn_type="issn_print")
        assert cand is not None
        assert cand.openalex_source_id == "S1234567890"


# ---------------------------------------------------------------------------
# find_best_match (integration-style with mock client)
# ---------------------------------------------------------------------------

class TestFindBestMatch:
    def _mock_client(self, issn_results: list, name_results: list):
        class _Client:
            def get_source_by_issn(self, issn: str) -> list:
                return issn_results

            def search_sources_by_name(self, name: str) -> list:
                return name_results

        return _Client()

    def test_accepts_high_confidence_issn_match(self) -> None:
        from thrn_ingest.match_sources import find_best_match

        journal = _make_journal("Annals of Tourism Research", issn_print="0160-7383")
        source = _make_source("S1111", "Annals of Tourism Research", issns=["0160-7383"])
        client = self._mock_client([source], [])

        best, all_cands = find_best_match(journal, client, min_confidence=0.85)
        assert best is not None
        assert best.openalex_source_id == "S1111"

    def test_rejects_low_confidence(self) -> None:
        from thrn_ingest.match_sources import find_best_match

        journal = _make_journal("Tourism Research Quarterly")
        # Low-similarity source
        source = _make_source("S2222", "Journal of Medicine and Biology")
        client = self._mock_client([], [source])

        best, all_cands = find_best_match(journal, client, min_confidence=0.85)
        assert best is None
        assert len(all_cands) == 1

    def test_manual_review_flag_prevents_auto_accept(self) -> None:
        from thrn_ingest.match_sources import find_best_match

        journal = _make_journal(
            "Journal of Travel and Tourism Marketing",
            issn_print="1054-8408",
            manual_review_flag=True,
        )
        source = _make_source("S3333", "Journal of Travel and Tourism Marketing", issns=["1054-8408"])
        client = self._mock_client([source], [])

        best, all_cands = find_best_match(journal, client, min_confidence=0.85)
        # High-confidence but manual_review blocks auto-accept
        assert best is None
        assert len(all_cands) > 0

    def test_no_candidates_returns_none_empty(self) -> None:
        from thrn_ingest.match_sources import find_best_match

        journal = _make_journal("Obscure Tourism Gazette")
        client = self._mock_client([], [])

        best, all_cands = find_best_match(journal, client, min_confidence=0.85)
        assert best is None
        assert all_cands == []
