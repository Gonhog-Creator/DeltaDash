"""add_cover_color_accessories_images_pdf

Revision ID: e6f7a8b9c0d1
Revises: d5e6f7a8b9c0
Create Date: 2026-09-08 12:30:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'e6f7a8b9c0d1'
down_revision = 'd5e6f7a8b9c0'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('covers', sa.Column('color', sa.String(), nullable=True))
    op.add_column('covers', sa.Column('construction_description', sa.String(), nullable=True))
    op.add_column('covers', sa.Column('has_badana', sa.Boolean(), server_default='false', nullable=False))
    op.add_column('covers', sa.Column('has_escudo', sa.Boolean(), server_default='false', nullable=False))
    op.add_column('covers', sa.Column('has_hombreras', sa.Boolean(), server_default='false', nullable=False))
    op.add_column('covers', sa.Column('pdf_document', sa.JSON(), nullable=True))
    op.add_column('covers', sa.Column('front_image', sa.JSON(), nullable=True))
    op.add_column('covers', sa.Column('back_image', sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column('covers', 'back_image')
    op.drop_column('covers', 'front_image')
    op.drop_column('covers', 'pdf_document')
    op.drop_column('covers', 'has_hombreras')
    op.drop_column('covers', 'has_escudo')
    op.drop_column('covers', 'has_badana')
    op.drop_column('covers', 'construction_description')
    op.drop_column('covers', 'color')
