"""Tests for RemoteImage."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from ctn_stack.container import RemoteImage


class TestRemoteImageEnsureExists:
    @pytest.mark.asyncio
    async def test_pulls_when_missing(self) -> None:
        image = RemoteImage("ubuntu", "24.04", abvr_tag="ubuntu24")

        with (
            patch.object(image, "exists", new=AsyncMock(return_value=False)),
            patch.object(image, "pull", new=AsyncMock()) as mock_pull,
        ):
            await image.ensure_exists()
            mock_pull.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_does_nothing_when_present(self) -> None:
        image = RemoteImage("ubuntu", "24.04", abvr_tag="ubuntu24")

        with (
            patch.object(image, "exists", new=AsyncMock(return_value=True)),
            patch.object(image, "pull", new=AsyncMock()) as mock_pull,
        ):
            await image.ensure_exists()
            mock_pull.assert_not_awaited()
