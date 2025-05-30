from sqlalchemy import Column, Integer, String, Boolean, Float, DateTime, ForeignKey, Text, Table
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import JSONB, ARRAY
from datetime import datetime, timezone
from geoalchemy2 import Geometry

from app.database import Base

class Recommendation(Base):
    __tablename__ = 'recommendations'
    
    id = Column(Integer, primary_key=True)
    
    # General recommendation info
    category = Column(String(100), nullable=False)  # restaurants, coffee shops, landmarks, etc.
    prompt = Column(Text, nullable=False)  # The recommendation text
    search_query = Column(String(255), nullable=True)  # Original search query
    
    # Place details as JSONB - includes all TripAdvisor or Google Places data
    place_details = Column(JSONB, nullable=True)
    
    # Spatial data for location-based queries
    location_geom = Column(Geometry('POINT', srid=4326, spatial_index=True), nullable=True)
    
    # Recommendation metadata - useful for AI learning
    archetypes = Column(ARRAY(String), nullable=True)  # e.g., ['foodie', 'cultural explorer']
    keywords = Column(ARRAY(String), nullable=True)  # e.g., ['coffee', 'atmosphere']
    
    # Image information
    image_concept = Column(String(100), nullable=True)
    image_url = Column(String(255), nullable=True)
    
    # Source tracking
    source = Column(String(50), nullable=True)  # e.g., 'TripAdvisor', 'Google Places'
    external_id = Column(String(100), nullable=True)  # ID from external source
    
    # For search optimization
    search_vector = Column(Text, nullable=True)  # Add a trigger for full-text search
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=datetime.now(timezone.utc), onupdate=datetime.now(timezone.utc))
    
    # Relationships
    user_recommendations = relationship("UserRecommendation", back_populates="recommendation")

class UserRecommendation(Base):
    __tablename__ = 'user_recommendations'
    
    id = Column(Integer, primary_key=True)
    user_id = Column(String, ForeignKey('users.id'), nullable=False)
    recommendation_id = Column(Integer, ForeignKey('recommendations.id'), nullable=False)
    
    # User interaction tracking
    is_seen = Column(Boolean, default=False)
    is_saved = Column(Boolean, default=False)
    is_visited = Column(Boolean, default=False)
    is_shared = Column(Boolean, default=False)
    is_liked = Column(Boolean, default=False)
    
    # Feedback for AI improvement
    user_rating = Column(Integer, nullable=True)  # 1-5 star rating
    feedback = Column(Text, nullable=True)  # Text feedback
    
    # Timestamps for analytics and model training
    created_at = Column(DateTime, default=datetime.utcnow)
    seen_at = Column(DateTime, nullable=True)
    saved_at = Column(DateTime, nullable=True)
    visited_at = Column(DateTime, nullable=True)
    shared_at = Column(DateTime, nullable=True)
    
    # Relationships
    user = relationship("User", back_populates="recommendations")
    recommendation = relationship("Recommendation", back_populates="user_recommendations")
