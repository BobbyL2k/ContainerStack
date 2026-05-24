"""Tests for ImageLayer and LayeredImage."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from ctn_stack.container import Image, ImageLayer, LayeredImage


class MockBaseImage(Image):
    """Minimal mock of Image for testing."""

    def __init__(self, name: str, tag: str, abvr_tag: str | None = None) -> None:
        super().__init__(
            name=name,
            full_tag=tag,
            abvr_tag=abvr_tag if abvr_tag is not None else tag,
            prev_abvr_tags=(),
        )

    async def ensure_exists(self) -> None:
        pass


class TestImageLayerValidation:
    """Test build-arg validation in ImageLayer.__call__."""

    def test_missing_required_arg_raises(self) -> None:
        layer = ImageLayer(
            dockerfile=Path("Dockerfile"),
            name="app",
            full_tag="latest",
            abvr_tag="app",
            build_arg_defs={"API_KEY": None},
        )
        base = MockBaseImage("ubuntu", "24.04")
        with pytest.raises(ValueError, match="Missing required build arg"):
            layer(base, build_args={})

    def test_extra_arg_raises(self) -> None:
        layer = ImageLayer(
            dockerfile=Path("Dockerfile"),
            name="app",
            full_tag="latest",
            abvr_tag="app",
            build_arg_defs={"WORKER_COUNT": "4"},
        )
        base = MockBaseImage("ubuntu", "24.04")
        with pytest.raises(ValueError, match="Unexpected build args"):
            layer(base, build_args={"WORKER_COUNT": "8", "EXTRA": "bad"})

    def test_defaults_merged_with_supplied(self) -> None:
        layer = ImageLayer(
            dockerfile=Path("Dockerfile"),
            name="app",
            full_tag="latest",
            abvr_tag="app",
            build_arg_defs={"WORKER_COUNT": "4", "LOG_LEVEL": "info"},
        )
        base = MockBaseImage("ubuntu", "24.04")
        derived = layer(base, build_args={"WORKER_COUNT": "8"})

        assert derived.build_args == {"WORKER_COUNT": "8", "LOG_LEVEL": "info"}

    def test_base_image_excluded_from_validation(self) -> None:
        """BASE_IMAGE should not be listed in build_arg_defs and should not
        cause validation errors even if supplied by caller."""
        layer = ImageLayer(
            dockerfile=Path("Dockerfile"),
            name="app",
            full_tag="latest",
            abvr_tag="app",
            build_arg_defs={"WORKER_COUNT": "4"},
        )
        base = MockBaseImage("ubuntu", "24.04")
        # BASE_IMAGE supplied by caller should be treated as extra
        with pytest.raises(ValueError, match="Unexpected build args"):
            layer(base, build_args={"WORKER_COUNT": "4", "BASE_IMAGE": "alpine:3"})

    def test_no_build_arg_defs_accepts_empty(self) -> None:
        layer = ImageLayer(
            dockerfile=Path("Dockerfile"),
            name="app",
            full_tag="latest",
            abvr_tag="app",
        )
        base = MockBaseImage("ubuntu", "24.04")
        derived = layer(base)
        assert derived.build_args == {}

    def test_name_tag_overrides(self) -> None:
        layer = ImageLayer(
            dockerfile=Path("Dockerfile"),
            name="default_name",
            full_tag="default_tag",
            abvr_tag="df",
        )
        base = MockBaseImage("ubuntu", "24.04")
        derived = layer(base, name="custom", tag="v2")
        assert derived.name == "custom"
        assert derived.tag == "v2"

    def test_name_tag_uses_defaults(self) -> None:
        layer = ImageLayer(
            dockerfile=Path("Dockerfile"),
            name="default_name",
            full_tag="default_tag",
            abvr_tag="df",
        )
        base = MockBaseImage("ubuntu", "24.04")
        derived = layer(base)
        assert derived.name == "default_name"
        assert derived.full_tag == "default_tag"


class TestLayeredImageBuild:
    """Test LayeredImage.build injects BASE_IMAGE and delegates correctly."""

    @pytest.mark.asyncio
    async def test_build_injects_base_image(self) -> None:
        base = MockBaseImage("ubuntu", "24.04", abvr_tag="u24")
        dockerfile = Path("/ctx/Dockerfile")
        image = LayeredImage(
            base=base,
            dockerfile=dockerfile,
            name="myapp",
            full_tag="latest",
            abvr_tag="myapp",
            build_args={"WORKER_COUNT": "4"},
        )

        with patch("ctn_stack.container.docker.build", new=AsyncMock()) as mock_build:
            await image.build()

            mock_build.assert_awaited_once_with(
                dockerfile_path=dockerfile,
                context_path=Path("/ctx"),
                tag="myapp:latest-u24",
                build_args={"BASE_IMAGE": "ubuntu:24.04", "WORKER_COUNT": "4"},
            )

    @pytest.mark.asyncio
    async def test_build_derives_context_from_dockerfile_parent(self) -> None:
        base = MockBaseImage("alpine", "3.19")
        dockerfile = Path("/some/deep/path/Dockerfile.prod")
        image = LayeredImage(
            base=base,
            dockerfile=dockerfile,
            name="prod",
            full_tag="v1",
            abvr_tag="prdv1",
            build_args={},
        )

        with patch("ctn_stack.container.docker.build", new=AsyncMock()) as mock_build:
            await image.build()

            call_args = mock_build.call_args
            assert call_args.kwargs["context_path"] == Path("/some/deep/path")


class TestLayeredImageEnsureExists:
    """Test LayeredImage.ensure_exists ensures base first, then builds."""

    @pytest.mark.asyncio
    async def test_ensures_base_then_builds_when_missing(self) -> None:
        base = MockBaseImage("ubuntu", "24.04")

        image = LayeredImage(
            base=base,
            dockerfile=Path("/ctx/Dockerfile"),
            name="myapp",
            full_tag="latest",
            abvr_tag="myapp",
            build_args={},
        )

        with (
            patch.object(image, "exists", new=AsyncMock(return_value=False)),
            patch.object(image, "build", new=AsyncMock()) as mock_build,
            patch.object(base, "ensure_exists", new=AsyncMock()) as base_ensure,
        ):
            await image.ensure_exists()

            base_ensure.assert_awaited_once()
            mock_build.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_does_nothing_when_present(self) -> None:
        base = MockBaseImage("ubuntu", "24.04")

        image = LayeredImage(
            base=base,
            dockerfile=Path("/ctx/Dockerfile"),
            name="myapp",
            full_tag="latest",
            abvr_tag="common",
            build_args={},
        )

        with (
            patch.object(image, "exists", new=AsyncMock(return_value=True)),
            patch.object(image, "build", new=AsyncMock()) as mock_build,
            patch.object(base, "ensure_exists", new=AsyncMock()) as base_ensure,
        ):
            await image.ensure_exists()

            base_ensure.assert_not_awaited()
            mock_build.assert_not_awaited()
