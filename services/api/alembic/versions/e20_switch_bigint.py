"""Switch generations and event cursors are 64-bit values in the live protocol."""
from alembic import op
import sqlalchemy as sa
revision='e20_switch_bigint'
down_revision='d1c3_pgvector'
branch_labels=None
depends_on=None

def upgrade():
    if op.get_bind().dialect.name=='postgresql':
        op.alter_column('agents','generation',existing_type=sa.Integer(),type_=sa.BigInteger())
        op.alter_column('agents','cursor',existing_type=sa.Integer(),type_=sa.BigInteger())
        op.alter_column('agent_messages','sequence',existing_type=sa.Integer(),type_=sa.BigInteger())

def downgrade():
    # Narrowing can lose real protocol values; never cast 64-bit cursors silently.
    pass
