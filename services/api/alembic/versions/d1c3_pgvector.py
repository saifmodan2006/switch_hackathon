"""Optional local 384-dimension embeddings in PostgreSQL pgvector.

SQLite uses JSON vectors and an exact cosine scan. Postgres uses indexed vectors.
"""
from alembic import op
revision='d1c3_pgvector'
down_revision='c80c1be47388'
branch_labels=None
depends_on=None


def upgrade():
    if op.get_bind().dialect.name=='postgresql':
        op.execute('CREATE EXTENSION IF NOT EXISTS vector')
        op.execute('ALTER TABLE document_chunks ADD COLUMN vector_embedding vector(384)')
        op.execute('CREATE INDEX ix_document_chunks_vector ON document_chunks USING hnsw (vector_embedding vector_cosine_ops)')


def downgrade():
    if op.get_bind().dialect.name=='postgresql':
        op.execute('DROP INDEX ix_document_chunks_vector')
        op.execute('ALTER TABLE document_chunks DROP COLUMN vector_embedding')
