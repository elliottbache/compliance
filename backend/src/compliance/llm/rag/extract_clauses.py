import hashlib
import json
import re
from collections.abc import Sequence
from typing import Any

type DocumentNode = dict[str, Any]
type RagClause = dict[str, str | None]

# ---------------------------------------------------------------------------
# Display labels
# ---------------------------------------------------------------------------

TYPE_LABELS = {
    "book": "Libro",
    "title": "Título",
    "chapter": "Capítulo",
    "section": "Sección",
    "subsection": "Subsección",
    "article": "Artículo",
    "part": "Parte",
    "annex": "Anexo",
    "paragraph": "Párrafo",
    "clause": "Cláusula",
    "rule": "Regla",
}


# ---------------------------------------------------------------------------
# Text helpers
# ---------------------------------------------------------------------------


def normalize_text(value: object | None) -> str | None:
    """
    Normalize text while preserving newline structure.

    Returns None for empty text.
    """
    if value is None:
        return None

    value = str(value)

    value = value.replace("\r\n", "\n").replace("\r", "\n")

    lines = []

    for line in value.split("\n"):
        line = re.sub(
            r"[ \t]+",
            " ",
            line,
        ).strip()

        lines.append(line)

    value = "\n".join(lines).strip()

    return value or None


def type_label(node_type: str | None) -> str:
    """
    Return a human-readable type label.

    Known types use explicit labels.

    Unknown types fall back gracefully:

        safety_requirement
            ->
        Safety Requirement
    """
    if not node_type:
        return ""

    return TYPE_LABELS.get(
        node_type,
        node_type.replace(
            "_",
            " ",
        ).title(),
    )


# ---------------------------------------------------------------------------
# Citation and title generation
# ---------------------------------------------------------------------------


def build_citation_ref(node: DocumentNode) -> str:
    """
    Examples:

        {
            "type": "article",
            "number": "15"
        }

        -> "Artículo 15"


        {
            "type": "section",
            "number": "1.ª"
        }

        -> "Sección 1.ª"
    """
    node_type = node.get("type")
    number = node.get("number")
    title = normalize_text(node.get("title"))

    label = type_label(node_type)

    if number:
        return f"{label} {number}"

    if title:
        return title

    return label


def build_title(node: DocumentNode) -> str | None:
    """
    Return only the descriptive title.

    Example:

        citation_ref:
            Artículo 15

        title:
            Derecho de acceso del interesado
    """
    return normalize_text(node.get("title"))


def build_path_heading(node: DocumentNode) -> str:
    """
    Build one ancestor component for path_text.

    Example:

        Título III. Derechos de las personas

    or:

        Capítulo II. Ejercicio de los derechos
    """
    citation_ref = build_citation_ref(node)

    title = build_title(node)

    if not title:
        return citation_ref

    if citation_ref == title:
        return title

    return f"{citation_ref}. {title}"


def build_path_text(ancestors: Sequence[DocumentNode]) -> str:
    """
    Build the human-readable ancestor path.

    The current node is deliberately excluded.

    Example:

        Título III. Derechos de las personas >
        Capítulo II. Ejercicio de los derechos
    """
    return " > ".join(build_path_heading(node) for node in ancestors)


# ---------------------------------------------------------------------------
# Content hash
# ---------------------------------------------------------------------------


def build_content_hash(
    *,
    citation_ref: str,
    title: str | None,
    path_text: str,
    text: str,
) -> str:
    """
    Create a deterministic SHA-256 hash for the
    RAG-relevant clause content.

    A change to the citation, title, path, or text
    will produce a different hash.
    """
    content = {
        "citation_ref": citation_ref,
        "title": title,
        "path_text": path_text,
        "text": text,
    }

    serialized = json.dumps(
        content,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )

    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


# ---------------------------------------------------------------------------
# Sort key
# ---------------------------------------------------------------------------


def build_sort_key(index_path: Sequence[int]) -> str:
    """
    Convert the node's hierarchical position
    into a lexicographically sortable key.

    Example:

        [3, 2, 1]

    becomes:

        000003.000002.000001
    """
    return ".".join(f"{index:06d}" for index in index_path)


# ---------------------------------------------------------------------------
# Clause creation
# ---------------------------------------------------------------------------


def build_clause(
    *,
    document_id: str,
    node: DocumentNode,
    ancestors: Sequence[DocumentNode],
    index_path: Sequence[int],
) -> RagClause | None:
    """
    Create one RAG clause from a text-bearing node.

    Returns None when the node contains no text.
    """
    text = normalize_text(node.get("text"))

    if not text:
        return None

    citation_ref = build_citation_ref(node)

    title = build_title(node)

    path_text = build_path_text(ancestors)

    content_hash = build_content_hash(
        citation_ref=citation_ref,
        title=title,
        path_text=path_text,
        text=text,
    )

    return {
        "document_source_id": document_id,
        "citation_ref": citation_ref,
        "title": title,
        "path_text": path_text,
        "text": text,
        "content_hash": content_hash,
        "sort_key": build_sort_key(index_path),
    }


# ---------------------------------------------------------------------------
# Recursive tree traversal
# ---------------------------------------------------------------------------


def collect_clauses(
    *,
    document_id: str,
    nodes: Sequence[DocumentNode],
    ancestors: Sequence[DocumentNode] | None = None,
    parent_index_path: Sequence[int] | None = None,
) -> list[RagClause]:
    """
    Recursively walk the generic document tree.

    Every node containing non-empty text becomes
    exactly one RAG clause.
    """
    if ancestors is None:
        ancestors = []

    if parent_index_path is None:
        parent_index_path = []

    clauses = []

    for index, node in enumerate(
        nodes,
        start=1,
    ):
        index_path = [
            *parent_index_path,
            index,
        ]

        clause = build_clause(
            document_id=document_id,
            node=node,
            ancestors=ancestors,
            index_path=index_path,
        )

        if clause is not None:
            clauses.append(clause)

        child_clauses = collect_clauses(
            document_id=document_id,
            nodes=node.get(
                "children",
                [],
            ),
            ancestors=[
                *ancestors,
                node,
            ],
            parent_index_path=index_path,
        )

        clauses.extend(child_clauses)

    return clauses


# ---------------------------------------------------------------------------
# Document importer
# ---------------------------------------------------------------------------


def import_rag_clauses(document: DocumentNode) -> list[RagClause]:
    """
    Convert a serialized generic document into
    a flat list of RAG clauses.
    """
    document_id = document["id"]

    structure = document.get(
        "structure",
        [],
    )

    return collect_clauses(
        document_id=document_id,
        nodes=structure,
    )
