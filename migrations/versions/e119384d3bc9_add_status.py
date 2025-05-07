"""add status

Revision ID: e119384d3bc9
Revises: 
Create Date: 2025-04-16 21:27:41.199578

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.


from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'e119384d3bc9'
down_revision = None
branch_labels = None
depends_on = None

def upgrade():
    op.add_column('employee_profile', sa.Column('status', sa.String(length=50), nullable=True))

def downgrade():
    op.drop_column('employee_profile', 'status')