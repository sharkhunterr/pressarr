"""Unit tests for quality service pure functions."""

from app.services.quality_service import (
    QUALITY_ORDER,
    compare_quality,
    is_at_cutoff,
    should_upgrade,
)


# ---------------------------------------------------------------------------
# Helpers — lightweight stand-ins for the ORM model
# ---------------------------------------------------------------------------

class _FakeItem:
    """Minimal stand-in for QualityProfileItem."""

    def __init__(self, quality: str, allowed: bool):
        self.quality = quality
        self.allowed = allowed


class _FakeProfile:
    """Minimal stand-in for QualityProfile."""

    def __init__(self, cutoff: str, items: list[_FakeItem] | None = None):
        self.cutoff = cutoff
        self.items = items or [
            _FakeItem(q, True) for q in QUALITY_ORDER
        ]


# ---------------------------------------------------------------------------
# compare_quality
# ---------------------------------------------------------------------------

class TestCompareQuality:
    """Tests for compare_quality()."""

    def test_equal_qualities(self):
        for q in QUALITY_ORDER:
            assert compare_quality(q, q) == 0

    def test_lower_is_negative(self):
        assert compare_quality("unknown", "truepdf") < 0

    def test_higher_is_positive(self):
        assert compare_quality("truepdf", "unknown") > 0

    def test_ordering_matches_hierarchy(self):
        """Each quality should compare less than the one after it."""
        for i in range(len(QUALITY_ORDER) - 1):
            low = QUALITY_ORDER[i]
            high = QUALITY_ORDER[i + 1]
            assert compare_quality(low, high) < 0, f"{low} should be < {high}"
            assert compare_quality(high, low) > 0, f"{high} should be > {low}"

    def test_unrecognised_quality_treated_as_lowest(self):
        assert compare_quality("garbage", "unknown") < 0
        assert compare_quality("unknown", "garbage") > 0


# ---------------------------------------------------------------------------
# is_at_cutoff
# ---------------------------------------------------------------------------

class TestIsAtCutoff:
    """Tests for is_at_cutoff()."""

    def test_quality_at_cutoff(self):
        profile = _FakeProfile(cutoff="pdf_hq")
        assert is_at_cutoff("pdf_hq", profile) is True

    def test_quality_above_cutoff(self):
        profile = _FakeProfile(cutoff="pdf_hq")
        assert is_at_cutoff("truepdf", profile) is True

    def test_quality_below_cutoff(self):
        profile = _FakeProfile(cutoff="pdf_hq")
        assert is_at_cutoff("scan", profile) is False

    def test_lowest_cutoff(self):
        profile = _FakeProfile(cutoff="unknown")
        for q in QUALITY_ORDER:
            assert is_at_cutoff(q, profile) is True

    def test_highest_cutoff(self):
        profile = _FakeProfile(cutoff="truepdf")
        for q in QUALITY_ORDER[:-1]:
            assert is_at_cutoff(q, profile) is False
        assert is_at_cutoff("truepdf", profile) is True


# ---------------------------------------------------------------------------
# should_upgrade
# ---------------------------------------------------------------------------

class TestShouldUpgrade:
    """Tests for should_upgrade()."""

    def test_upgrade_when_below_cutoff_and_new_is_better(self):
        profile = _FakeProfile(cutoff="pdf_hq")
        assert should_upgrade("scan", "pdf_hq", profile) is True

    def test_no_upgrade_when_at_cutoff(self):
        profile = _FakeProfile(cutoff="pdf_hq")
        assert should_upgrade("pdf_hq", "truepdf", profile) is False

    def test_no_upgrade_when_above_cutoff(self):
        profile = _FakeProfile(cutoff="pdf_hq")
        assert should_upgrade("retail", "truepdf", profile) is False

    def test_no_upgrade_when_new_is_worse(self):
        profile = _FakeProfile(cutoff="pdf_hq")
        assert should_upgrade("scan", "unknown", profile) is False

    def test_no_upgrade_when_new_is_equal(self):
        profile = _FakeProfile(cutoff="pdf_hq")
        assert should_upgrade("scan", "scan", profile) is False

    def test_no_upgrade_when_new_quality_not_allowed(self):
        """Even if the new quality is better, it must be allowed in the profile."""
        items = [
            _FakeItem("unknown", True),
            _FakeItem("scan", True),
            _FakeItem("pdf_lq", True),
            _FakeItem("pdf_hq", False),  # pdf_hq disallowed
            _FakeItem("retail", True),
            _FakeItem("truepdf", True),
        ]
        profile = _FakeProfile(cutoff="retail", items=items)
        assert should_upgrade("scan", "pdf_hq", profile) is False

    def test_upgrade_with_allowed_quality(self):
        """Upgrade should succeed when the new quality is allowed."""
        items = [
            _FakeItem("unknown", True),
            _FakeItem("scan", True),
            _FakeItem("pdf_lq", True),
            _FakeItem("pdf_hq", True),
            _FakeItem("retail", False),
            _FakeItem("truepdf", True),
        ]
        profile = _FakeProfile(cutoff="truepdf", items=items)
        assert should_upgrade("scan", "pdf_hq", profile) is True

    def test_profile_with_only_some_qualities_allowed(self):
        """Only truepdf allowed — upgrade from scan to truepdf should work,
        but scan to pdf_hq should not."""
        items = [
            _FakeItem("unknown", False),
            _FakeItem("scan", False),
            _FakeItem("pdf_lq", False),
            _FakeItem("pdf_hq", False),
            _FakeItem("retail", False),
            _FakeItem("truepdf", True),
        ]
        profile = _FakeProfile(cutoff="truepdf", items=items)
        assert should_upgrade("scan", "truepdf", profile) is True
        assert should_upgrade("scan", "pdf_hq", profile) is False
        assert should_upgrade("scan", "retail", profile) is False
