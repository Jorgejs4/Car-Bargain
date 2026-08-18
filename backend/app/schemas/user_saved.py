"""Schemas de favoritos y búsquedas guardadas."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class FavoriteRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    listing_id: int
    created_at: datetime


class SavedSearchCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    filters: dict = Field(default_factory=dict)


class SavedSearchRead(SavedSearchCreate):
    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: datetime
    updated_at: datetime
