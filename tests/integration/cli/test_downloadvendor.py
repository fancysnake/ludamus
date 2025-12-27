"""Integration tests for downloadvendor management command."""

from __future__ import annotations

import base64
import hashlib
from io import StringIO
from typing import TYPE_CHECKING

import pytest
import responses
from django.core.management import call_command
from django.core.management.base import CommandError
from requests.exceptions import ConnectionError as RequestsConnectionError

if TYPE_CHECKING:
    from pathlib import Path

SAMPLE_JS_CONTENT = b"console.log('hello');"
SAMPLE_JS_HASH = base64.b64encode(hashlib.sha384(SAMPLE_JS_CONTENT).digest()).decode()

SAMPLE_CSS_CONTENT = b"body { color: red; }"
SAMPLE_CSS_HASH = base64.b64encode(hashlib.sha384(SAMPLE_CSS_CONTENT).digest()).decode()


@pytest.fixture(name="vendor_dir")
def vendor_dir_fixture(tmp_path: Path) -> Path:
    vendor = tmp_path / "vendor"
    vendor.mkdir()
    return vendor


@pytest.fixture(name="single_dependency")
def single_dependency_fixture() -> list[dict[str, str]]:
    return [
        {
            "name": "test-lib",
            "url": "https://cdn.example.com/test-lib.min.js",
            "filename": "test-lib.min.js",
            "sha384": SAMPLE_JS_HASH,
        }
    ]


@pytest.fixture(name="multiple_dependencies")
def multiple_dependencies_fixture() -> list[dict[str, str]]:
    return [
        {
            "name": "test-js",
            "url": "https://cdn.example.com/test.min.js",
            "filename": "test.min.js",
            "sha384": SAMPLE_JS_HASH,
        },
        {
            "name": "test-css",
            "url": "https://cdn.example.com/test.min.css",
            "filename": "test.min.css",
            "sha384": SAMPLE_CSS_HASH,
        },
    ]


@pytest.fixture(name="nested_dependency")
def nested_dependency_fixture() -> list[dict[str, str]]:
    return [
        {
            "name": "icon-font",
            "url": "https://cdn.example.com/fonts/icons.woff2",
            "filename": "fonts/icons.woff2",
            "sha384": SAMPLE_JS_HASH,
        }
    ]


class TestDownloadVendorCommand:
    """Tests for the downloadvendor management command."""

    @responses.activate
    def test_downloads_single_dependency(
        self, settings, vendor_dir: Path, single_dependency: list[dict[str, str]]
    ) -> None:
        """Test downloading a single vendor dependency."""
        settings.VENDOR_DEPENDENCIES = single_dependency
        settings.VENDOR_STATIC_DIR = vendor_dir

        responses.add(
            responses.GET,
            "https://cdn.example.com/test-lib.min.js",
            body=SAMPLE_JS_CONTENT,
            status=200,
        )

        out = StringIO()
        call_command("downloadvendor", stdout=out)

        output = out.getvalue()
        assert "Downloading vendor dependencies" in output
        assert "test-lib" in output
        assert "Verified" in output
        assert "1 downloaded" in output

        downloaded_file = vendor_dir / "test-lib.min.js"
        assert downloaded_file.exists()
        assert downloaded_file.read_bytes() == SAMPLE_JS_CONTENT

    @responses.activate
    def test_downloads_multiple_dependencies(
        self, settings, vendor_dir: Path, multiple_dependencies: list[dict[str, str]]
    ) -> None:
        """Test downloading multiple vendor dependencies."""
        settings.VENDOR_DEPENDENCIES = multiple_dependencies
        settings.VENDOR_STATIC_DIR = vendor_dir

        responses.add(
            responses.GET,
            "https://cdn.example.com/test.min.js",
            body=SAMPLE_JS_CONTENT,
            status=200,
        )
        responses.add(
            responses.GET,
            "https://cdn.example.com/test.min.css",
            body=SAMPLE_CSS_CONTENT,
            status=200,
        )

        out = StringIO()
        call_command("downloadvendor", stdout=out)

        output = out.getvalue()
        assert "2 downloaded" in output

        assert (vendor_dir / "test.min.js").exists()
        assert (vendor_dir / "test.min.css").exists()

    @responses.activate
    def test_creates_subdirectories_for_nested_paths(
        self, settings, vendor_dir: Path, nested_dependency: list[dict[str, str]]
    ) -> None:
        """Test that nested paths like fonts/ are created automatically."""
        settings.VENDOR_DEPENDENCIES = nested_dependency
        settings.VENDOR_STATIC_DIR = vendor_dir

        responses.add(
            responses.GET,
            "https://cdn.example.com/fonts/icons.woff2",
            body=SAMPLE_JS_CONTENT,
            status=200,
        )

        call_command("downloadvendor")

        downloaded_file = vendor_dir / "fonts" / "icons.woff2"
        assert downloaded_file.exists()
        assert downloaded_file.read_bytes() == SAMPLE_JS_CONTENT

    def test_skips_existing_file_with_valid_hash(
        self, settings, vendor_dir: Path, single_dependency: list[dict[str, str]]
    ) -> None:
        """Test that existing files with valid hash are skipped."""
        settings.VENDOR_DEPENDENCIES = single_dependency
        settings.VENDOR_STATIC_DIR = vendor_dir

        existing_file = vendor_dir / "test-lib.min.js"
        existing_file.write_bytes(SAMPLE_JS_CONTENT)

        out = StringIO()
        call_command("downloadvendor", stdout=out)

        output = out.getvalue()
        assert "Skipped" in output
        assert "file exists with valid hash" in output
        assert "1 skipped" in output

    @responses.activate
    def test_redownloads_file_with_invalid_hash(
        self, settings, vendor_dir: Path, single_dependency: list[dict[str, str]]
    ) -> None:
        """Test that existing files with invalid hash are re-downloaded."""
        settings.VENDOR_DEPENDENCIES = single_dependency
        settings.VENDOR_STATIC_DIR = vendor_dir

        existing_file = vendor_dir / "test-lib.min.js"
        existing_file.write_bytes(b"corrupted content")

        responses.add(
            responses.GET,
            "https://cdn.example.com/test-lib.min.js",
            body=SAMPLE_JS_CONTENT,
            status=200,
        )

        out = StringIO()
        call_command("downloadvendor", stdout=out)

        output = out.getvalue()
        assert "invalid hash" in output
        assert "1 downloaded" in output
        assert existing_file.read_bytes() == SAMPLE_JS_CONTENT

    @responses.activate
    def test_force_redownloads_valid_files(
        self, settings, vendor_dir: Path, single_dependency: list[dict[str, str]]
    ) -> None:
        """Test --force flag re-downloads even valid files."""
        settings.VENDOR_DEPENDENCIES = single_dependency
        settings.VENDOR_STATIC_DIR = vendor_dir

        existing_file = vendor_dir / "test-lib.min.js"
        existing_file.write_bytes(SAMPLE_JS_CONTENT)

        responses.add(
            responses.GET,
            "https://cdn.example.com/test-lib.min.js",
            body=SAMPLE_JS_CONTENT,
            status=200,
        )

        out = StringIO()
        call_command("downloadvendor", "--force", stdout=out)

        output = out.getvalue()
        assert "1 downloaded" in output
        assert "Skipped" not in output

    def test_dry_run_does_not_download(
        self, settings, vendor_dir: Path, single_dependency: list[dict[str, str]]
    ) -> None:
        """Test --dry-run flag shows what would be downloaded without downloading."""
        settings.VENDOR_DEPENDENCIES = single_dependency
        settings.VENDOR_STATIC_DIR = vendor_dir

        out = StringIO()
        call_command("downloadvendor", "--dry-run", stdout=out)

        output = out.getvalue()
        assert "[DRY RUN]" in output
        assert "Would download" in output
        assert "would be downloaded" in output

        assert not (vendor_dir / "test-lib.min.js").exists()

    @responses.activate
    def test_fails_on_hash_mismatch(
        self, settings, vendor_dir: Path, single_dependency: list[dict[str, str]]
    ) -> None:
        """Test that hash mismatch raises CommandError."""
        settings.VENDOR_DEPENDENCIES = single_dependency
        settings.VENDOR_STATIC_DIR = vendor_dir

        responses.add(
            responses.GET,
            "https://cdn.example.com/test-lib.min.js",
            body=b"different content with wrong hash",
            status=200,
        )

        out = StringIO()
        with pytest.raises(CommandError, match=r"1 dependency download.*failed"):
            call_command("downloadvendor", stdout=out)

        output = out.getvalue()
        assert "Hash mismatch" in output

    @responses.activate
    def test_fails_on_network_error(
        self, settings, vendor_dir: Path, single_dependency: list[dict[str, str]]
    ) -> None:
        """Test that network errors raise CommandError."""
        settings.VENDOR_DEPENDENCIES = single_dependency
        settings.VENDOR_STATIC_DIR = vendor_dir

        responses.add(
            responses.GET,
            "https://cdn.example.com/test-lib.min.js",
            body=RequestsConnectionError("Connection refused"),
        )

        out = StringIO()
        with pytest.raises(CommandError, match=r"1 dependency download.*failed"):
            call_command("downloadvendor", stdout=out)

        output = out.getvalue()
        assert "Download failed" in output

    @responses.activate
    def test_fails_on_http_error(
        self, settings, vendor_dir: Path, single_dependency: list[dict[str, str]]
    ) -> None:
        """Test that HTTP errors raise CommandError."""
        settings.VENDOR_DEPENDENCIES = single_dependency
        settings.VENDOR_STATIC_DIR = vendor_dir

        responses.add(
            responses.GET, "https://cdn.example.com/test-lib.min.js", status=404
        )

        out = StringIO()
        with pytest.raises(CommandError, match=r"1 dependency download.*failed"):
            call_command("downloadvendor", stdout=out)

        output = out.getvalue()
        assert "Download failed" in output

    def test_warns_when_no_dependencies_configured(
        self, settings, vendor_dir: Path
    ) -> None:
        """Test warning message when no dependencies are configured."""
        settings.VENDOR_DEPENDENCIES = []
        settings.VENDOR_STATIC_DIR = vendor_dir

        out = StringIO()
        call_command("downloadvendor", stdout=out)

        output = out.getvalue()
        assert "No vendor dependencies configured" in output

    @responses.activate
    def test_continues_after_single_failure(
        self, settings, vendor_dir: Path, multiple_dependencies: list[dict[str, str]]
    ) -> None:
        """Test that command continues processing after a single failure."""
        settings.VENDOR_DEPENDENCIES = multiple_dependencies
        settings.VENDOR_STATIC_DIR = vendor_dir

        responses.add(responses.GET, "https://cdn.example.com/test.min.js", status=404)
        responses.add(
            responses.GET,
            "https://cdn.example.com/test.min.css",
            body=SAMPLE_CSS_CONTENT,
            status=200,
        )

        out = StringIO()
        with pytest.raises(CommandError, match=r"1 dependency download.*failed"):
            call_command("downloadvendor", stdout=out)

        output = out.getvalue()
        assert "1 downloaded" in output
        assert "1 failed" in output

        assert not (vendor_dir / "test.min.js").exists()
        assert (vendor_dir / "test.min.css").exists()

    @responses.activate
    def test_creates_vendor_directory_if_not_exists(
        self, settings, tmp_path: Path, single_dependency: list[dict[str, str]]
    ) -> None:
        """Test that vendor directory is created if it doesn't exist."""
        vendor_dir = tmp_path / "nonexistent" / "vendor"
        settings.VENDOR_DEPENDENCIES = single_dependency
        settings.VENDOR_STATIC_DIR = vendor_dir

        responses.add(
            responses.GET,
            "https://cdn.example.com/test-lib.min.js",
            body=SAMPLE_JS_CONTENT,
            status=200,
        )

        call_command("downloadvendor")

        assert vendor_dir.exists()
        assert (vendor_dir / "test-lib.min.js").exists()
