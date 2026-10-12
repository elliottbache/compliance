from unittest.mock import MagicMock

import pytest
from compliance.llm.rag.parse_boe import (
    BOE_API_BASE_URL,
    as_list,
    build_boe_url,
    create_article_node,
    create_heading_node,
    create_node,
    extract_article_heading,
    extract_article_number,
    extract_article_text,
    extract_article_title,
    extract_heading_title,
    fetch_boe_regulation,
    get_text,
    latest_version,
    normalize_heading_type,
    parse_boe_date,
    parse_boe_datetime,
    parse_boe_regulation,
    parse_heading_label,
    parse_metadata,
    parse_structure,
)


class TestAsList:
    @pytest.mark.parametrize(
        ("value", "expected"),
        [(None, []), ("value", ["value"]), (["a", "b"], ["a", "b"])],
    )
    def test_normalizes_xml_values(self, value, expected) -> None:
        assert as_list(value) == expected


class TestGetText:
    @pytest.mark.parametrize(
        ("value", "expected"),
        [
            (None, None),
            ("  text  ", "text"),
            ([" first ", {"#text": "second"}], "first second"),
            ({"@class": "ignored", "#text": "Lead", "em": "nested"}, "Lead nested"),
            (42, "42"),
        ],
    )
    def test_extracts_plain_text(self, value, expected) -> None:
        assert get_text(value) == expected


class TestLatestVersion:
    def test_returns_none_without_versions(self) -> None:
        assert latest_version({}) is None

    def test_prefers_latest_publication_then_effective_date(self) -> None:
        latest = {"@fecha_publicacion": "20260102", "@fecha_vigencia": "20260101"}
        block = {
            "version": [
                {"@fecha_publicacion": "20260101", "@fecha_vigencia": "20260103"},
                latest,
            ]
        }

        assert latest_version(block) is latest


class TestParseBoeDates:
    def test_formats_datetime(self) -> None:
        assert parse_boe_datetime("20260720T102442Z") == "2026-07-20T10:24:42Z"

    def test_formats_date(self) -> None:
        assert parse_boe_date("20181205") == "2018-12-05"

    @pytest.mark.parametrize("parser", [parse_boe_datetime, parse_boe_date])
    def test_returns_none_for_missing_value(self, parser) -> None:
        assert parser(None) is None


def test_parse_metadata_maps_boe_fields_and_status() -> None:
    result = parse_metadata(
        {
            "identificador": "BOE-A-2026-1",
            "titulo": "Example regulation",
            "fecha_actualizacion": "20260720T102442Z",
            "fecha_disposicion": "20260115",
            "estatus_derogacion": "V",
            "url_eli": "https://example.test/eli",
        }
    )

    assert result == {
        "id": "BOE-A-2026-1",
        "title": "Example regulation",
        "source_kind": "public_regulation",
        "jurisdiction": "Spain",
        "updated_at": "2026-07-20T10:24:42Z",
        "effective_date": "2026-01-15",
        "status": "active",
        "url_eli": "https://example.test/eli",
    }


def test_create_node_initializes_independent_children() -> None:
    first = create_node(node_type="title", number="I")
    second = create_node(node_type="article", number="1", text="Body")
    first["children"].append(second)

    assert first["children"] == [second]
    assert second["children"] == []


class TestHeadingParsing:
    @pytest.mark.parametrize(
        ("label", "expected"),
        [
            ("TÍTULO V", ("title", "V", 2)),
            ("capitulo II", ("chapter", "II", 3)),
            ("Sección 1.ª", ("section", "1.ª", 4)),
            ("not a heading", None),
        ],
    )
    def test_parses_supported_labels(self, label, expected) -> None:
        assert parse_heading_label(label) == expected

    def test_normalizes_accents(self) -> None:
        assert normalize_heading_type("SECCIÓN") == "seccion"

    def test_extracts_descriptive_title_from_latest_version(self) -> None:
        block = {
            "@titulo": "TÍTULO V",
            "version": {"p": ["TÍTULO V.", "Data controller obligations"]},
        }

        assert extract_heading_title(block) == "Data controller obligations"
        assert create_heading_node(block) == (
            2,
            create_node(
                node_type="title", number="V", title="Data controller obligations"
            ),
        )


class TestArticleParsing:
    @pytest.mark.parametrize(
        ("title", "expected"),
        [("Artículo 15", "15"), ("Artículo 53 bis", "53 bis"), ("Annex", "Annex")],
    )
    def test_extracts_article_number(self, title, expected) -> None:
        assert extract_article_number(title) == expected

    def test_extracts_heading_title_and_body(self) -> None:
        version = {
            "p": [
                {"@class": "articulo", "#text": "Artículo 28. General duties"},
                "First paragraph.",
                {"strong": "Second paragraph."},
            ]
        }

        assert extract_article_heading(version) == "Artículo 28. General duties"
        assert extract_article_title("Artículo 28", version) == "General duties"
        assert extract_article_text(version) == "First paragraph.\n\nSecond paragraph."

    def test_creates_node_from_latest_article_version(self) -> None:
        block = {
            "@titulo": "Artículo 28",
            "version": {
                "@fecha_publicacion": "20260101",
                "p": [
                    {"@class": "articulo", "#text": "Artículo 28. General duties"},
                    "Body text.",
                ],
            },
        }

        assert create_article_node(block) == create_node(
            node_type="article", number="28", title="General duties", text="Body text."
        )


def test_parse_structure_nests_headings_and_articles() -> None:
    structure = parse_structure(
        {
            "bloque": [
                {"@tipo": "encabezado", "@titulo": "TÍTULO I", "version": {}},
                {"@tipo": "encabezado", "@titulo": "CAPÍTULO I", "version": {}},
                {
                    "@tipo": "precepto",
                    "@titulo": "Artículo 1",
                    "version": {"p": ["Article body."]},
                },
                {"@tipo": "other", "@titulo": "Ignored"},
            ]
        }
    )

    assert structure[0]["type"] == "title"
    chapter = structure[0]["children"][0]
    assert chapter["type"] == "chapter"
    assert chapter["children"][0]["number"] == "1"
    assert chapter["children"][0]["text"] == "Article body."


class TestBoeApi:
    def test_builds_url(self) -> None:
        assert build_boe_url("BOE-A-2026-1") == f"{BOE_API_BASE_URL}/BOE-A-2026-1"

    def test_fetches_and_parses_xml(self, monkeypatch) -> None:
        response = MagicMock(content=b"<response><data>ok</data></response>")
        get = MagicMock(return_value=response)
        monkeypatch.setattr("compliance.llm.rag.parse_boe.requests.get", get)

        result = fetch_boe_regulation("BOE-A-2026-1")

        get.assert_called_once_with(
            f"{BOE_API_BASE_URL}/BOE-A-2026-1",
            headers={"Accept": "application/xml"},
            timeout=30,
        )
        response.raise_for_status.assert_called_once_with()
        assert result == {"response": {"data": "ok"}}


def test_parse_boe_regulation_combines_metadata_and_structure() -> None:
    result = parse_boe_regulation(
        {
            "response": {
                "data": {
                    "metadatos": {
                        "identificador": "BOE-A-2026-1",
                        "titulo": "Example regulation",
                        "fecha_disposicion": "20260115",
                        "estatus_derogacion": "V",
                    },
                    "texto": {
                        "bloque": {
                            "@tipo": "precepto",
                            "@titulo": "Artículo 1",
                            "version": {"p": ["Body text."]},
                        }
                    },
                }
            }
        }
    )

    assert result["id"] == "BOE-A-2026-1"
    assert result["status"] == "active"
    assert result["structure"][0]["text"] == "Body text."
