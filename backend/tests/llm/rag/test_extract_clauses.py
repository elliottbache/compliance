from compliance.llm.rag.extract_clauses import (
    build_clause,
    build_content_hash,
    collect_clauses,
)


class TestCollectClauses:
    def test_title_with_one_article_produces_one_clause(self) -> None:
        clauses = collect_clauses(
            document_id="doc-1",
            nodes=[
                {
                    "type": "title",
                    "number": "I",
                    "title": "General provisions",
                    "children": [
                        {
                            "type": "article",
                            "number": "1",
                            "text": "Article text.",
                        }
                    ],
                }
            ],
        )

        assert len(clauses) == 1
        assert clauses[0]["text"] == "Article text."

    def test_node_with_no_text_is_skipped(self) -> None:
        clauses = collect_clauses(
            document_id="doc-1",
            nodes=[
                {
                    "type": "article",
                    "number": "1",
                    "children": [],
                }
            ],
        )

        assert clauses == []

    def test_node_with_text_and_children_is_saved_and_children_are_processed(
        self,
    ) -> None:
        clauses = collect_clauses(
            document_id="doc-1",
            nodes=[
                {
                    "type": "article",
                    "number": "1",
                    "text": "Parent text.",
                    "children": [
                        {
                            "type": "paragraph",
                            "number": "1",
                            "text": "Child text.",
                        }
                    ],
                }
            ],
        )

        assert [clause["citation_ref"] for clause in clauses] == [
            "Artículo 1",
            "Párrafo 1",
        ]
        assert [clause["text"] for clause in clauses] == [
            "Parent text.",
            "Child text.",
        ]

    def test_empty_string_and_whitespace_text_are_skipped(self) -> None:
        clauses = collect_clauses(
            document_id="doc-1",
            nodes=[
                {
                    "type": "article",
                    "number": "1",
                    "text": "",
                },
                {
                    "type": "article",
                    "number": "2",
                    "text": " \n\t ",
                },
            ],
        )

        assert clauses == []

    def test_path_text_is_empty_for_top_level_text_node(self) -> None:
        clauses = collect_clauses(
            document_id="doc-1",
            nodes=[
                {
                    "type": "article",
                    "number": "1",
                    "text": "Top-level text.",
                }
            ],
        )

        assert clauses[0]["path_text"] == ""

    def test_path_text_contains_ancestors_but_not_current_node(self) -> None:
        clauses = collect_clauses(
            document_id="doc-1",
            nodes=[
                {
                    "type": "title",
                    "number": "I",
                    "title": "General provisions",
                    "children": [
                        {
                            "type": "article",
                            "number": "3",
                            "title": "Scope",
                            "text": "Article text.",
                        }
                    ],
                }
            ],
        )

        assert clauses[0]["path_text"] == "Título I. General provisions"
        assert "Artículo 3" not in clauses[0]["path_text"]
        assert "Scope" not in clauses[0]["path_text"]

    def test_citation_ref_comes_from_current_node(self) -> None:
        clauses = collect_clauses(
            document_id="doc-1",
            nodes=[
                {
                    "type": "title",
                    "number": "I",
                    "children": [
                        {
                            "type": "article",
                            "number": "7",
                            "text": "Article text.",
                        }
                    ],
                }
            ],
        )

        assert clauses[0]["citation_ref"] == "Artículo 7"

    def test_sort_key_preserves_original_tree_order(self) -> None:
        clauses = collect_clauses(
            document_id="doc-1",
            nodes=[
                {
                    "type": "article",
                    "number": "1",
                    "text": "First article.",
                    "children": [
                        {
                            "type": "paragraph",
                            "number": "1",
                            "text": "First child.",
                        },
                        {
                            "type": "paragraph",
                            "number": "2",
                            "text": "Second child.",
                        },
                    ],
                },
                {
                    "type": "article",
                    "number": "2",
                    "text": "Second article.",
                },
            ],
        )

        assert [clause["sort_key"] for clause in clauses] == [
            "000001",
            "000001.000001",
            "000001.000002",
            "000002",
        ]
        assert [
            clause["text"] for clause in sorted(clauses, key=lambda c: c["sort_key"])
        ] == [
            "First article.",
            "First child.",
            "Second child.",
            "Second article.",
        ]

    def test_sort_key_uses_tree_position_instead_of_article_number(self) -> None:
        clauses = collect_clauses(
            document_id="doc-1",
            nodes=[
                {
                    "type": "article",
                    "number": "20",
                    "text": "First in the tree.",
                },
                {
                    "type": "article",
                    "number": "3",
                    "text": "Second in the tree.",
                },
            ],
        )

        assert [clause["sort_key"] for clause in clauses] == [
            "000001",
            "000002",
        ]

    def test_same_article_number_under_different_paths_has_different_path_text(
        self,
    ) -> None:
        clauses = collect_clauses(
            document_id="doc-1",
            nodes=[
                {
                    "type": "title",
                    "number": "I",
                    "title": "First title",
                    "children": [
                        {
                            "type": "article",
                            "number": "1",
                            "text": "Article under first title.",
                        }
                    ],
                },
                {
                    "type": "title",
                    "number": "II",
                    "title": "Second title",
                    "children": [
                        {
                            "type": "article",
                            "number": "1",
                            "text": "Article under second title.",
                        }
                    ],
                },
            ],
        )

        assert [clause["citation_ref"] for clause in clauses] == [
            "Artículo 1",
            "Artículo 1",
        ]
        assert clauses[0]["path_text"] == "Título I. First title"
        assert clauses[1]["path_text"] == "Título II. Second title"
        assert clauses[0]["path_text"] != clauses[1]["path_text"]


class TestBuildContentHash:
    def test_changes_if_rag_content_changes(self) -> None:
        original_values = {
            "citation_ref": "Artículo 1",
            "title": "Purpose",
            "path_text": "Título I",
            "text": "Original text.",
        }
        original_hash = build_content_hash(**original_values)

        changed_values = {
            "citation_ref": "Artículo 2",
            "title": "Changed purpose",
            "path_text": "Título II",
            "text": "Changed text.",
        }

        for field, changed_value in changed_values.items():
            values = {
                **original_values,
                field: changed_value,
            }
            changed_hash = build_content_hash(**values)

            assert changed_hash != original_hash, field

    def test_does_not_change_if_sort_key_changes(self) -> None:
        first_clause = build_clause(
            document_id="doc-1",
            node={
                "type": "article",
                "number": "1",
                "title": "Purpose",
                "text": "Stable text.",
            },
            ancestors=[],
            index_path=[1],
        )
        second_clause = build_clause(
            document_id="doc-1",
            node={
                "type": "article",
                "number": "1",
                "title": "Purpose",
                "text": "Stable text.",
            },
            ancestors=[],
            index_path=[2],
        )

        assert first_clause is not None
        assert second_clause is not None
        assert first_clause["sort_key"] != second_clause["sort_key"]
        assert first_clause["content_hash"] == second_clause["content_hash"]
