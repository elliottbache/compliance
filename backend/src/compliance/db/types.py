"""Database types with production and test dialect variants."""

from pgvector.sqlalchemy import VECTOR
from sqlalchemy import JSON

EMBEDDING_VECTOR_TYPE = JSON().with_variant(VECTOR(), "postgresql")
