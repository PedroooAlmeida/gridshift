"""Typed event boundary shared by parsers, tools, and deterministic graders."""

from decimal import Decimal
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, model_validator


class Event(BaseModel):
    model_config = ConfigDict(extra="forbid")
    kind: Literal["demand_response", "outage", "clarify"]
    start_hour: Optional[int] = Field(default=None, strict=True, ge=0, le=23)
    end_hour: Optional[int] = Field(default=None, strict=True, ge=1, le=24)
    reduction_kw: Optional[int] = Field(default=None, strict=True, gt=0, le=100000)
    reward_dollars: Optional[Decimal] = Field(default=None, ge=0, le=1000000)
    penalty_dollars: Optional[Decimal] = Field(default=None, ge=0, le=1000000)
    machine_id: Optional[str] = None
    clarification: Optional[str] = None

    @model_validator(mode="after")
    def coherent(self):
        if self.kind == "clarify":
            if not self.clarification:
                raise ValueError("Clarification needs a question")
            if any(
                x is not None
                for x in (
                    self.start_hour,
                    self.end_hour,
                    self.reduction_kw,
                    self.reward_dollars,
                    self.penalty_dollars,
                    self.machine_id,
                )
            ):
                raise ValueError("Clarification cannot execute partially specified actions")
            return self
        if self.clarification is not None:
            raise ValueError("Executable events cannot also request clarification")
        if self.start_hour is None or self.end_hour is None or self.start_hour >= self.end_hour:
            raise ValueError("A complete, increasing time window is required")
        if self.kind == "demand_response":
            if any(
                x is None for x in (self.reduction_kw, self.reward_dollars, self.penalty_dollars)
            ):
                raise ValueError("Reduction, reward, and penalty are required")
            if self.machine_id is not None:
                raise ValueError("Demand response cannot contain a machine outage")
        elif not self.machine_id or any(
            x is not None for x in (self.reduction_kw, self.reward_dollars, self.penalty_dollars)
        ):
            raise ValueError("Outage requires only a machine and time window")
        return self
