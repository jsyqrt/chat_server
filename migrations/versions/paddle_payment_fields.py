"""Add Paddle payment fields

Revision ID: paddle_payment_fields
Revises: f95f05996d43
Create Date: 2025-05-15 16:50:33.816692

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql

# revision identifiers, used by Alembic.
revision = 'paddle_payment_fields'
down_revision = 'f95f05996d43'
branch_labels = None
depends_on = None


def upgrade():
    # Add Paddle-specific columns to the PAYMENT_ORDER table
    with op.batch_alter_table('PAYMENT_ORDER', schema=None) as batch_op:
        batch_op.add_column(sa.Column('paddle_checkout_id', sa.String(length=64), nullable=True))
        batch_op.add_column(sa.Column('paddle_subscription_id', sa.String(length=64), nullable=True))
        batch_op.add_column(sa.Column('paddle_payment_id', sa.String(length=64), nullable=True))


def downgrade():
    # Remove Paddle-specific columns from the PAYMENT_ORDER table
    with op.batch_alter_table('PAYMENT_ORDER', schema=None) as batch_op:
        batch_op.drop_column('paddle_payment_id')
        batch_op.drop_column('paddle_subscription_id')
        batch_op.drop_column('paddle_checkout_id')