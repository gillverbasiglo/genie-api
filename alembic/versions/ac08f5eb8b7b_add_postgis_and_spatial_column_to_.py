"""add postgis and spatial column to recommendations table

Revision ID: ac08f5eb8b7b
Revises: d241e3f732e4
Create Date: 2025-05-30 11:20:40.906816

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'ac08f5eb8b7b'
down_revision: Union[str, None] = 'd241e3f732e4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Enable PostGIS extension
    op.execute('CREATE EXTENSION IF NOT EXISTS postgis')
    
    # Add geometry column to recommendations table
    op.execute('ALTER TABLE recommendations ADD COLUMN location_geom geometry(Point, 4326)')
    
    # Create spatial index
    op.execute('CREATE INDEX idx_recommendations_location_geom ON recommendations USING GIST (location_geom)')
    
    # Add trigger to update geometry from place_details
    op.execute('''
        CREATE OR REPLACE FUNCTION update_recommendation_geometry()
        RETURNS TRIGGER AS $$
        BEGIN
            IF NEW.place_details IS NOT NULL AND 
               NEW.place_details->'location'->>'lat' IS NOT NULL AND 
               NEW.place_details->'location'->>'lng' IS NOT NULL THEN
                NEW.location_geom = ST_SetSRID(
                    ST_MakePoint(
                        (NEW.place_details->'location'->>'lng')::float,
                        (NEW.place_details->'location'->>'lat')::float
                    ),
                    4326
                );
            END IF;
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
    ''')

    op.execute('''
        CREATE TRIGGER update_recommendation_geometry_trigger
        BEFORE INSERT OR UPDATE OF place_details
        ON recommendations
        FOR EACH ROW
        EXECUTE FUNCTION update_recommendation_geometry();
    ''')


def downgrade() -> None:
    """Downgrade schema."""
    op.execute('DROP TRIGGER IF EXISTS update_recommendation_geometry_trigger ON recommendations')
    op.execute('DROP FUNCTION IF EXISTS update_recommendation_geometry()')
    op.execute('DROP INDEX IF EXISTS idx_recommendations_location_geom')
    op.execute('ALTER TABLE recommendations DROP COLUMN IF EXISTS location_geom')
    op.execute('DROP EXTENSION IF EXISTS postgis')
