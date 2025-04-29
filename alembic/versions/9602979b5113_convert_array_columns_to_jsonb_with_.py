"""Convert array columns to JSONB with similarity_score

Revision ID: 9602979b5113
Revises: 5d142413ab4b
Create Date: 2025-04-29 11:41:18.983526

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import Column, String, text
from sqlalchemy.dialects.postgresql import ARRAY, JSONB


# revision identifiers, used by Alembic.
revision = '9602979b5113'
down_revision = '5d142413ab4b'
branch_labels = None
depends_on = None


def upgrade():
    # Step 1: Add new JSONB columns
    op.add_column('users', sa.Column('archetypes_jsonb', JSONB, nullable=True))
    op.add_column('users', sa.Column('keywords_jsonb', JSONB, nullable=True))
    
    # Step 2: Transform array data into JSONB format with default similarity_score of 1.0
    conn = op.get_bind()
    
    # Convert archetypes array to JSONB
    conn.execute(text("""
        UPDATE users 
        SET archetypes_jsonb = (
            SELECT jsonb_agg(jsonb_build_object('name', elem, 'similarity_score', 1.0))
            FROM unnest(archetypes) AS elem
            WHERE archetypes IS NOT NULL
        )
    """))
    
    # Convert keywords array to JSONB
    conn.execute(text("""
        UPDATE users 
        SET keywords_jsonb = (
            SELECT jsonb_agg(jsonb_build_object('name', elem, 'similarity_score', 1.0))
            FROM unnest(keywords) AS elem
            WHERE keywords IS NOT NULL
        )
    """))
    
    # Step 3: Create backup of original array columns (for safety and downgrade)
    op.add_column('users', sa.Column('archetypes_array_backup', ARRAY(String), nullable=True))
    op.add_column('users', sa.Column('keywords_array_backup', ARRAY(String), nullable=True))
    
    conn.execute(text("""
        UPDATE users 
        SET archetypes_array_backup = archetypes,
            keywords_array_backup = keywords
    """))
    
    # Step 4: Drop old columns and rename new ones
    op.drop_column('users', 'archetypes')
    op.drop_column('users', 'keywords')
    op.alter_column('users', 'archetypes_jsonb', new_column_name='archetypes')
    op.alter_column('users', 'keywords_jsonb', new_column_name='keywords')
    
    # Step 5: Create GIN indexes for better performance
    op.execute(text('CREATE INDEX archetypes_gin_idx ON users USING GIN (archetypes)'))
    op.execute(text('CREATE INDEX keywords_gin_idx ON users USING GIN (keywords)'))


def downgrade():
    # Step 1: Remove indexes
    op.execute(text('DROP INDEX IF EXISTS archetypes_gin_idx'))
    op.execute(text('DROP INDEX IF EXISTS keywords_gin_idx'))
    
    # Step 2: Add temporary array columns
    op.add_column('users', sa.Column('archetypes_array', ARRAY(String), nullable=True))
    op.add_column('users', sa.Column('keywords_array', ARRAY(String), nullable=True))
    
    # Step 3: Convert JSONB data back to arrays
    conn = op.get_bind()
    
    # Use backup if available, otherwise extract from JSONB
    conn.execute(text("""
        UPDATE users 
        SET archetypes_array = 
            CASE 
                WHEN archetypes_array_backup IS NOT NULL THEN archetypes_array_backup
                ELSE (
                    SELECT array_agg(elem->>'name')
                    FROM jsonb_array_elements(archetypes) AS elem
                    WHERE archetypes IS NOT NULL
                )
            END
    """))
    
    conn.execute(text("""
        UPDATE users 
        SET keywords_array = 
            CASE 
                WHEN keywords_array_backup IS NOT NULL THEN keywords_array_backup
                ELSE (
                    SELECT array_agg(elem->>'name')
                    FROM jsonb_array_elements(keywords) AS elem
                    WHERE keywords IS NOT NULL
                )
            END
    """))
    
    # Step 4: Drop JSONB columns and rename array columns
    op.drop_column('users', 'archetypes')
    op.drop_column('users', 'keywords')
    op.alter_column('users', 'archetypes_array', new_column_name='archetypes')
    op.alter_column('users', 'keywords_array', new_column_name='keywords')
    
    # Step 5: Drop backup columns
    op.drop_column('users', 'archetypes_array_backup')
    op.drop_column('users', 'keywords_array_backup')
