from app.parser.magazine_parser import (
    ParseResult,
    fuzzy_match_title,
    normalize_title,
    parse_magazine_filename,
)


# ======================================================================
# T030: 25+ parser unit tests
# ======================================================================


# --- Multi-separator formats ---


class TestMultiSeparatorFormats:
    def test_dots_as_separators(self):
        r = parse_magazine_filename("Science.et.Vie.N1285.Octobre.2025.FRENCH.TruePDF.pdf")
        assert r.title == "Science et Vie"
        assert r.number == 1285
        assert r.month == 10
        assert r.year == 2025
        assert r.language == "french"
        assert r.quality == "truepdf"
        assert r.format == "pdf"

    def test_spaces_as_separators(self):
        r = parse_magazine_filename("Science et Vie N1285 Octobre 2025 FRENCH TruePDF.pdf")
        assert r.title == "Science et Vie"
        assert r.number == 1285
        assert r.month == 10
        assert r.year == 2025

    def test_underscores_as_separators(self):
        r = parse_magazine_filename("Science_et_Vie_N1285_Octobre_2025_FRENCH_TruePDF.pdf")
        assert r.title == "Science et Vie"
        assert r.number == 1285

    def test_mixed_dashes_and_spaces(self):
        r = parse_magazine_filename("National Geographic - Issue 12 - March 2025.pdf")
        assert r.title == "National Geographic"
        assert r.number == 12
        assert r.month == 3
        assert r.year == 2025


# --- Multilingual months ---


class TestMultilingualMonths:
    def test_french_month(self):
        r = parse_magazine_filename("Magazine Janvier 2025.pdf")
        assert r.month == 1
        assert r.year == 2025

    def test_french_month_accent(self):
        r = parse_magazine_filename("Magazine Février 2024.pdf")
        assert r.month == 2

    def test_english_month(self):
        r = parse_magazine_filename("Magazine December 2025.pdf")
        assert r.month == 12

    def test_german_month(self):
        r = parse_magazine_filename("Spiegel Oktober 2025.pdf")
        assert r.month == 10

    def test_spanish_month(self):
        r = parse_magazine_filename("Revista Agosto 2025.pdf")
        assert r.month == 8

    def test_italian_month(self):
        r = parse_magazine_filename("Rivista Settembre 2025.pdf")
        assert r.month == 9


# --- Issue numbers ---


class TestIssueNumbers:
    def test_n_prefix(self):
        r = parse_magazine_filename("Magazine N1285.pdf")
        assert r.number == 1285

    def test_issue_keyword(self):
        r = parse_magazine_filename("Magazine Issue 12.pdf")
        assert r.number == 12

    def test_hash_prefix(self):
        r = parse_magazine_filename("Magazine #42.pdf")
        assert r.number == 42

    def test_no_dot_prefix(self):
        r = parse_magazine_filename("Magazine No.5.pdf")
        assert r.number == 5

    def test_numero_keyword(self):
        r = parse_magazine_filename("Magazine Numero 10.pdf")
        assert r.number == 10

    def test_double_issue(self):
        # Double issues like N1285-1286: parser captures the first number
        r = parse_magazine_filename("Science et Vie N1285-1286 2025.pdf")
        assert r.number == 1285


# --- Volumes ---


class TestVolumes:
    def test_vol_dot(self):
        r = parse_magazine_filename("Encyclopedia Vol.3 2025.pdf")
        assert r.volume == 3

    def test_volume_full(self):
        r = parse_magazine_filename("Encyclopedia Volume 5 2025.pdf")
        assert r.volume == 5

    def test_v_prefix(self):
        r = parse_magazine_filename("Encyclopedia V2 2025.pdf")
        assert r.volume == 2


# --- Quality tags ---


class TestQualityTags:
    def test_truepdf(self):
        r = parse_magazine_filename("Magazine N1 TruePDF.pdf")
        assert r.quality == "truepdf"

    def test_retail(self):
        r = parse_magazine_filename("Magazine N1 Retail.pdf")
        assert r.quality == "retail"

    def test_scan(self):
        r = parse_magazine_filename("Magazine N1 Scan.pdf")
        assert r.quality == "scan"

    def test_hq(self):
        r = parse_magazine_filename("Magazine N1 HQ.pdf")
        assert r.quality == "pdf_hq"

    def test_lq(self):
        r = parse_magazine_filename("Magazine N1 LQ.pdf")
        assert r.quality == "pdf_lq"


# --- Language tags ---


class TestLanguageTags:
    def test_french(self):
        r = parse_magazine_filename("Magazine FRENCH.pdf")
        assert r.language == "french"

    def test_english(self):
        r = parse_magazine_filename("Magazine ENGLISH.pdf")
        assert r.language == "english"

    def test_multi(self):
        r = parse_magazine_filename("Magazine MULTI.pdf")
        assert r.language == "multi"


# --- Hors-serie markers ---


class TestHorsSerie:
    def test_hs(self):
        r = parse_magazine_filename("Science et Vie HS N42 2025.pdf")
        assert r.is_special is True
        assert r.number == 42

    def test_hors_serie_hyphen(self):
        r = parse_magazine_filename("Science et Vie Hors-Serie N10.pdf")
        assert r.is_special is True

    def test_hors_serie_space(self):
        r = parse_magazine_filename("Science et Vie Hors Serie N10.pdf")
        assert r.is_special is True

    def test_special(self):
        r = parse_magazine_filename("Science et Vie Special N10.pdf")
        assert r.is_special is True


# --- Format detection ---


class TestFormatDetection:
    def test_pdf(self):
        assert parse_magazine_filename("Mag.pdf").format == "pdf"

    def test_epub(self):
        assert parse_magazine_filename("Mag.epub").format == "epub"

    def test_cbr(self):
        assert parse_magazine_filename("Mag.cbr").format == "cbr"

    def test_cbz(self):
        assert parse_magazine_filename("Mag.cbz").format == "cbz"

    def test_unknown_extension(self):
        assert parse_magazine_filename("Mag.zip").format == "unknown"


# --- Release groups ---


class TestReleaseGroups:
    def test_parentheses_group(self):
        r = parse_magazine_filename("Magazine N1 2025 (TeamGroup).pdf")
        assert r.release_group == "TeamGroup"

    def test_bracket_group(self):
        r = parse_magazine_filename("Magazine N1 2025 [TeamGroup].pdf")
        assert r.release_group == "TeamGroup"


# --- Date-only periodicals ---


class TestDateOnlyPeriodicals:
    def test_month_year_no_number(self):
        r = parse_magazine_filename("The Economist March 2025.pdf")
        assert r.month == 3
        assert r.year == 2025
        assert r.number is None

    def test_year_month_format(self):
        r = parse_magazine_filename("The Economist 2025-03.pdf")
        assert r.year == 2025
        assert r.month == 3


# --- Edge cases ---


class TestEdgeCases:
    def test_no_number_at_all(self):
        r = parse_magazine_filename("Some Random Magazine.pdf")
        assert r.number is None
        assert r.title == "Some Random Magazine"
        assert r.format == "pdf"

    def test_minimal_info(self):
        r = parse_magazine_filename("Mag.pdf")
        assert r.title == "Mag"
        assert r.format == "pdf"

    def test_empty_string(self):
        r = parse_magazine_filename("")
        assert r.title == ""
        assert r.format == "unknown"

    def test_raw_filename_preserved(self):
        fname = "Science.et.Vie.N1285.2025.pdf"
        r = parse_magazine_filename(fname)
        assert r.raw_filename == fname

    def test_never_crashes_on_garbage(self):
        r = parse_magazine_filename("!@#$%^&*().pdf")
        assert isinstance(r, ParseResult)


# --- Fuzzy title matching ---


class TestNormalizeTitle:
    def test_removes_articles(self):
        assert normalize_title("The New Yorker") == "new yorker"

    def test_removes_french_articles(self):
        assert normalize_title("Le Monde") == "monde"

    def test_strips_accents(self):
        assert normalize_title("Télérama") == "telerama"


class TestFuzzyMatchTitle:
    def test_exact_match(self):
        result = fuzzy_match_title("Science et Vie", ["Science et Vie", "Le Monde"])
        assert result is not None
        assert result[0] == "Science et Vie"

    def test_close_match(self):
        result = fuzzy_match_title("Sciencs et Vie", ["Science et Vie", "Le Monde"])
        assert result is not None
        assert result[0] == "Science et Vie"

    def test_no_match_below_threshold(self):
        result = fuzzy_match_title("xyzzy", ["Science et Vie", "Le Monde"])
        assert result is None

    def test_empty_input(self):
        assert fuzzy_match_title("", ["Science et Vie"]) is None

    def test_empty_known_list(self):
        assert fuzzy_match_title("Science", []) is None
