from datetime import date
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class Profile(BaseModel):
    model_config = ConfigDict(extra="forbid")
    nationality: str = Field(min_length=1, max_length=80)
    purpose: Literal["working_holiday", "employment", "internship"]
    visa_status: Literal["undecided", "preparing", "held"]
    city: Literal["Sydney"] = "Sydney"
    arrival_date: date
    workplace: Literal["Sydney CBD", "Surry Hills", "Parramatta"]
    company: str = Field(default="", max_length=120)
    monthly_budget: float = Field(gt=0, le=100000, allow_inf_nan=False, strict=True)
    initial_budget: float = Field(gt=0, le=1000000, allow_inf_nan=False, strict=True)
    housing_type: Literal["any", "share", "studio"] = "any"
    max_commute: int = Field(ge=1, le=180, strict=True)
    insurance: float | None = Field(default=None, ge=0, le=10000, allow_inf_nan=False, strict=True)
    sort_by: Literal["balanced", "cheapest", "fastest"] = "balanced"

    @field_validator("nationality")
    @classmethod
    def clean_nationality(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("국적을 입력해 주세요.")
        return value.strip()


class Revision(BaseModel):
    model_config = ConfigDict(extra="forbid")
    profile: Profile
    message: str = Field(min_length=1, max_length=1000)


class ProfilePatch(BaseModel):
    model_config = ConfigDict(extra="forbid")
    monthly_budget: float | None = Field(default=None, gt=0, le=100000, allow_inf_nan=False, strict=True)
    initial_budget: float | None = Field(default=None, gt=0, le=1000000, allow_inf_nan=False, strict=True)
    max_commute: int | None = Field(default=None, ge=1, le=180, strict=True)
    housing_type: Literal["any", "share", "studio"] | None = None
    sort_by: Literal["balanced", "cheapest", "fastest"] | None = None
    insurance: float | None = Field(default=None, ge=0, le=10000, allow_inf_nan=False, strict=True)
    workplace: Literal["Sydney CBD", "Surry Hills", "Parramatta"] | None = None

    def changes(self) -> dict:
        # Null means “not changed”; clearing insurance is available in the main form.
        return self.model_dump(exclude_none=True)
