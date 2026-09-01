import re
from datetime import datetime
from typing import Any

import requests
import xmltodict

BOE_API_BASE_URL = "https://www.boe.es/datosabiertos/api/legislacion-consolidada/id"

type XmlNode = dict[str, Any]
type DocumentNode = dict[str, Any]


# ---------------------------------------------------------------------------
# BOE mappings
# ---------------------------------------------------------------------------

STATUS_MAP = {
    "V": "active",
    "N": "inactive",
    "M": "superseded",
    "T": "superseded",
    "P": "inactive",
}


HIERARCHY_LEVELS = {
    "libro": 1,
    "titulo": 2,
    "capitulo": 3,
    "seccion": 4,
    "subseccion": 5,
}


TYPE_NAMES = {
    "libro": "book",
    "titulo": "title",
    "capitulo": "chapter",
    "seccion": "section",
    "subseccion": "subsection",
}


# ---------------------------------------------------------------------------
# Generic XML helpers
# ---------------------------------------------------------------------------


def as_list(value: Any) -> list[Any]:
    """Ensure an xmltodict value is always returned as a list."""
    if value is None:
        return []

    if isinstance(value, list):
        return value

    return [value]


def get_text(value: Any) -> str | None:
    """Recursively extract plain text from an xmltodict node."""
    if value is None:
        return None

    if isinstance(value, str):
        return value.strip()

    if isinstance(value, list):
        parts = [get_text(item) for item in value]

        return " ".join(part for part in parts if part)

    if isinstance(value, dict):
        dict_parts: list[str] = []

        if "#text" in value:
            dict_parts.append(str(value["#text"]))

        for key, child in value.items():
            if key.startswith("@") or key == "#text":
                continue

            child_text = get_text(child)

            if child_text:
                dict_parts.append(child_text)

        return " ".join(dict_parts).strip()

    return str(value).strip()


def latest_version(block: XmlNode) -> XmlNode | None:
    """Return the most recently published version of a BOE block."""
    versions = as_list(block.get("version"))

    if not versions:
        return None

    return max(
        versions,
        key=lambda version: (
            version.get("@fecha_publicacion", ""),
            version.get("@fecha_vigencia", ""),
        ),
    )


# ---------------------------------------------------------------------------
# Date parsing
# ---------------------------------------------------------------------------


def parse_boe_datetime(value: str | None) -> str | None:
    """
    Convert:

        20260720T102442Z

    to:

        2026-07-20T10:24:42Z
    """
    if not value:
        return None

    dt = datetime.strptime(
        value,
        "%Y%m%dT%H%M%SZ",
    )

    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def parse_boe_date(value: str | None) -> str | None:
    """
    Convert:

        20181205

    to:

        2018-12-05
    """
    if not value:
        return None

    date = datetime.strptime(
        value,
        "%Y%m%d",
    )

    return date.strftime("%Y-%m-%d")


# ---------------------------------------------------------------------------
# Metadata
# ---------------------------------------------------------------------------


def parse_metadata(metadata: XmlNode) -> dict[str, str | None]:
    raw_status = metadata.get("estatus_derogacion")
    status = raw_status if isinstance(raw_status, str) else None
    mapped_status = STATUS_MAP.get(status, status) if status is not None else None

    return {
        "id": metadata.get("identificador"),
        "title": metadata.get("titulo"),
        "source_kind": "public_regulation",
        "jurisdiction": "Spain",
        "updated_at": parse_boe_datetime(metadata.get("fecha_actualizacion")),
        "effective_date": parse_boe_date(metadata.get("fecha_disposicion")),
        "status": mapped_status,
        "url_eli": metadata.get("url_eli"),
    }


# ---------------------------------------------------------------------------
# Generic document node
# ---------------------------------------------------------------------------


def create_node(
    *,
    node_type: str,
    number: str | None = None,
    title: str | None = None,
    text: str | None = None,
) -> DocumentNode:
    return {
        "type": node_type,
        "number": number,
        "title": title,
        "text": text,
        "children": [],
    }


# ---------------------------------------------------------------------------
# Structural headings
# ---------------------------------------------------------------------------


def normalize_heading_type(value: str) -> str:
    """Normalize accented BOE heading names."""
    value = value.lower()

    replacements = {
        "í": "i",
        "ó": "o",
    }

    for old, new in replacements.items():
        value = value.replace(old, new)

    return value


def parse_heading_label(label: str) -> tuple[str, str, int] | None:
    """
    Parse headings such as:

        TÍTULO V
        CAPÍTULO II
        Sección 1.ª
        Subsección 2.ª

    Returns:

        ("title", "V", 2)
    """
    match = re.match(
        (r"^(LIBRO|T[IÍ]TULO|CAP[IÍ]TULO|" r"SECCI[ÓO]N|SUBSECCI[ÓO]N)" r"\s+(.+)$"),
        label.strip(),
        flags=re.IGNORECASE,
    )

    if not match:
        return None

    raw_type = normalize_heading_type(match.group(1))

    number = match.group(2).strip()

    return (
        TYPE_NAMES[raw_type],
        number,
        HIERARCHY_LEVELS[raw_type],
    )


def extract_heading_title(block: XmlNode) -> str | None:
    """
    Example:

        @titulo:
            TÍTULO V

        version text:
            TÍTULO V
            Responsable y encargado del tratamiento  # codespell:ignore

    returns:

        Responsable y encargado del tratamiento  # codespell:ignore
    """
    block_label = block.get(
        "@titulo",
        "",
    ).strip()

    version = latest_version(block)

    if version is None:
        return None

    paragraphs = []

    for paragraph in as_list(version.get("p")):
        text = get_text(paragraph)

        if text:
            paragraphs.append(text)

    descriptive_parts = [
        text
        for text in paragraphs
        if (text.casefold().rstrip(".") != block_label.casefold().rstrip("."))
    ]

    if not descriptive_parts:
        return None

    return " ".join(descriptive_parts)


def create_heading_node(block: XmlNode) -> tuple[int, DocumentNode] | None:
    label = block.get(
        "@titulo",
        "",
    )

    parsed = parse_heading_label(label)

    if parsed is None:
        return None

    node_type, number, level = parsed

    node = create_node(
        node_type=node_type,
        number=number,
        title=extract_heading_title(block),
    )

    return level, node


# ---------------------------------------------------------------------------
# Articles
# ---------------------------------------------------------------------------


def extract_article_number(block_title: str) -> str:
    """
    Examples:

        Artículo 15
            -> "15"

        Artículo 53 bis
            -> "53 bis"
    """
    match = re.match(
        r"Artículo\s+(.+)",
        block_title,
        flags=re.IGNORECASE,
    )

    if not match:
        return block_title

    return match.group(1).strip()


def extract_article_heading(version: XmlNode) -> str | None:
    """
    Find the paragraph containing the article heading.
    """
    for paragraph in as_list(version.get("p")):
        if isinstance(paragraph, dict) and paragraph.get("@class") == "articulo":
            return get_text(paragraph)

    return None


def extract_article_title(
    block_title: str,
    version: XmlNode,
) -> str | None:
    """
    Example:

        Artículo 28.
        Obligaciones generales del responsable...  # codespell:ignore responsable

    returns:

        Obligaciones generales del responsable...  # codespell:ignore responsable
    """
    heading = extract_article_heading(version)

    if not heading:
        return None

    pattern = rf"^{re.escape(block_title)}" rf"\.?\s*"

    title = re.sub(
        pattern,
        "",
        heading,
        flags=re.IGNORECASE,
    ).strip()

    return title or None


def extract_article_text(version: XmlNode) -> str:
    """
    Extract article body paragraphs,
    excluding the article heading.
    """
    paragraphs = []

    for paragraph in as_list(version.get("p")):
        if isinstance(paragraph, dict) and paragraph.get("@class") == "articulo":
            continue

        text = get_text(paragraph)

        if text:
            paragraphs.append(text)

    return "\n\n".join(paragraphs)


def create_article_node(block: XmlNode) -> DocumentNode | None:
    block_title = block.get(
        "@titulo",
        "",
    )

    version = latest_version(block)

    if version is None:
        return None

    return create_node(
        node_type="article",
        number=extract_article_number(block_title),
        title=extract_article_title(
            block_title,
            version,
        ),
        text=extract_article_text(version),
    )


# ---------------------------------------------------------------------------
# Hierarchy builder
# ---------------------------------------------------------------------------


def parse_structure(texto: XmlNode) -> list[DocumentNode]:
    """
    Convert BOE's flat sequence of blocks into
    a generic nested document tree.

    Example:

        title
        └── chapter
            └── section
                ├── article
                └── article

    But no particular hierarchy is required.
    """
    structure: list[DocumentNode] = []

    # Each stack item is:
    #
    #     (hierarchy_level, node)
    #
    stack: list[tuple[int, DocumentNode]] = []

    for block in as_list(texto.get("bloque")):
        block_type = block.get("@tipo")

        block_title = block.get(
            "@titulo",
            "",
        )

        # ------------------------------------------------------------
        # Structural heading
        # ------------------------------------------------------------

        if block_type == "encabezado":
            result = create_heading_node(block)

            if result is None:
                continue

            level, node = result

            # Remove nodes at the same or deeper hierarchy level.
            while stack and stack[-1][0] >= level:
                stack.pop()

            if stack:
                parent = stack[-1][1]

                parent["children"].append(node)
            else:
                structure.append(node)

            stack.append((level, node))

            continue

        # ------------------------------------------------------------
        # Article
        # ------------------------------------------------------------

        if block_type == "precepto" and block_title.lower().startswith("artículo"):
            article = create_article_node(block)

            if article is None:
                continue

            if stack:
                parent = stack[-1][1]

                parent["children"].append(article)

            else:
                # Some documents may contain articles
                # without a preceding structural heading.
                structure.append(article)

    return structure


# ---------------------------------------------------------------------------
# Fetch + complete document parser
# ---------------------------------------------------------------------------


def build_boe_url(boe_id: str) -> str:
    """Build the BOE consolidated legislation API URL for a BOE identifier."""
    return f"{BOE_API_BASE_URL}/{boe_id}"


def fetch_boe_regulation(boe_id: str) -> XmlNode:
    """Fetch a consolidated BOE regulation by BOE identifier."""
    response = requests.get(
        build_boe_url(boe_id),
        headers={
            "Accept": "application/xml",
        },
        timeout=30,
    )

    response.raise_for_status()

    return xmltodict.parse(response.content)


def parse_boe_regulation(data: XmlNode) -> dict[str, Any]:
    document = data["response"]["data"]

    metadata = parse_metadata(document["metadatos"])

    return {
        **metadata,
        "structure": parse_structure(document["texto"]),
    }
