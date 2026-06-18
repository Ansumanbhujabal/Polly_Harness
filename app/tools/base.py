"""BaseTool — abstract base class for all L3 tool implementations.

Every tool in `app/tools/` inherits from this. The base class enforces:
- typed Input / Output as Pydantic submodels
- a standard async run() interface
- no imports from app.graph, app.mcp, or app.api (one-way dependency)
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from pydantic import BaseModel


class BaseTool(ABC):
    """Abstract base for all harness tools.

    Subclass must define:
      - name: str  — stable snake_case identifier
      - description: str  — one-paragraph description loaded into the prompt
      - Input(BaseTool.Input) — Pydantic submodel for inputs
      - Output(BaseTool.Output) — Pydantic submodel for outputs
      - async run(input: Input) -> Output
    """

    name: str
    description: str

    class Input(BaseModel):
        """Base input model — subclass and add fields."""

        model_config = {"arbitrary_types_allowed": True}

    class Output(BaseModel):
        """Base output model — subclass and add fields."""

        model_config = {"arbitrary_types_allowed": True}

    @abstractmethod
    async def run(self, input: "BaseTool.Input") -> "BaseTool.Output":
        """Execute the tool with the given typed input. Never raises — surface
        errors as structured Output fields or let executor.py wrap them."""
        ...

    def parse_input(self, payload: dict[str, Any]) -> "BaseTool.Input":
        """Parse a raw dict into the tool's Input model."""
        return self.Input(**payload)  # type: ignore[call-arg]

    def __repr__(self) -> str:
        return f"<Tool name={self.name!r}>"
