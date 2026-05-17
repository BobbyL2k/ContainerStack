"""Tests for the base Image class."""

from __future__ import annotations

import pytest

from ctn_stack.container import Image


class ConcreteImage(Image):
    """Concrete subclass for testing Image base behaviour."""

    def __init__(self, name: str, tag: str) -> None:
        self.name = name
        self.tag = tag


class TestImage:
    def test_get_name_tag(self) -> None:
        img = ConcreteImage("ubuntu", "24.04")
        assert img.get_name_tag() == "ubuntu:24.04"

    @pytest.mark.asyncio
    async def test_ensure_exists_raises_not_implemented(self) -> None:
        img = ConcreteImage("ubuntu", "24.04")
        with pytest.raises(NotImplementedError):
            await img.ensure_exists()
