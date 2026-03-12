"""Tests for the ``NoteTool`` builtin tool."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from helix.tools.note import NoteTool, _slugify


class TestSlugify:
    """Unit tests for the slugify helper."""

    def test_when_normal_title_expect_dashed_lowercase(self) -> None:
        assert _slugify("Hello World") == "hello-world"

    def test_when_special_chars_expect_stripped(self) -> None:
        assert _slugify("My Note! @#$%") == "my-note-"

    def test_when_empty_string_expect_untitled(self) -> None:
        assert _slugify("") == "untitled"

    def test_when_long_title_expect_truncated(self) -> None:
        assert len(_slugify("a" * 200)) <= 80


class TestNoteTool:
    """Unit tests for ``NoteTool``."""

    def setup_method(self) -> None:
        self.tool = NoteTool()

    def test_when_checking_name_expect_note(self) -> None:
        assert self.tool.name == "note"

    def test_when_checking_description_expect_non_empty_string(self) -> None:
        assert isinstance(self.tool.description, str)
        assert len(self.tool.description) > 0

    def test_when_checking_parameters_schema_expect_command_required(self) -> None:
        schema = self.tool.parameters_schema
        assert "command" in schema["properties"]
        assert "command" in schema["required"]

    def test_when_serialising_expect_valid_openai_schema(self) -> None:
        schema = self.tool.to_openai_schema()
        assert schema["type"] == "function"
        assert schema["function"]["name"] == "note"

    async def test_when_unknown_command_expect_error(self) -> None:
        result = await self.tool.run(command="delete")
        assert "Error" in result

    async def test_when_create_without_title_expect_error(self) -> None:
        result = await self.tool.run(command="create", content="some text")
        assert "Error" in result
        assert "title" in result.lower()

    async def test_when_create_without_content_expect_error(self) -> None:
        result = await self.tool.run(command="create", title="Test")
        assert "Error" in result
        assert "content" in result.lower()

    async def test_when_create_expect_file_written(self, tmp_path: Path) -> None:
        with patch("helix.tools.note._NOTES_DIR", tmp_path):
            result = await self.tool.run(command="create", title="Test Note", content="Hello world")

        assert "saved" in result.lower()
        files = list(tmp_path.glob("*.md"))
        assert len(files) == 1
        content = files[0].read_text()
        assert "Hello world" in content
        assert "title: Test Note" in content

    async def test_when_list_empty_dir_expect_no_notes(self, tmp_path: Path) -> None:
        with patch("helix.tools.note._NOTES_DIR", tmp_path):
            result = await self.tool.run(command="list")
        assert "No notes" in result

    async def test_when_list_with_notes_expect_names(self, tmp_path: Path) -> None:
        (tmp_path / "first.md").write_text("content")
        (tmp_path / "second.md").write_text("content")

        with patch("helix.tools.note._NOTES_DIR", tmp_path):
            result = await self.tool.run(command="list")

        assert "first" in result
        assert "second" in result
        assert "2" in result

    async def test_when_read_existing_note_expect_content(self, tmp_path: Path) -> None:
        note_content = "---\ntitle: My Note\n---\n\nHello!"
        (tmp_path / "my-note.md").write_text(note_content)

        with patch("helix.tools.note._NOTES_DIR", tmp_path):
            result = await self.tool.run(command="read", title="My Note")

        assert "Hello!" in result

    async def test_when_read_missing_note_expect_not_found(self, tmp_path: Path) -> None:
        with patch("helix.tools.note._NOTES_DIR", tmp_path):
            result = await self.tool.run(command="read", title="Nonexistent")

        assert "not found" in result.lower()

    async def test_when_search_match_expect_results(self, tmp_path: Path) -> None:
        (tmp_path / "recipe.md").write_text("Chocolate cake recipe")
        (tmp_path / "todo.md").write_text("Buy groceries")

        with patch("helix.tools.note._NOTES_DIR", tmp_path):
            result = await self.tool.run(command="search", query="chocolate")

        assert "recipe" in result

    async def test_when_search_no_match_expect_empty(self, tmp_path: Path) -> None:
        (tmp_path / "note.md").write_text("Hello world")

        with patch("helix.tools.note._NOTES_DIR", tmp_path):
            result = await self.tool.run(command="search", query="xyznonexistent")

        assert "No notes" in result

    async def test_when_search_without_query_expect_error(self) -> None:
        result = await self.tool.run(command="search")
        assert "Error" in result
