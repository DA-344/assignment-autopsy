from pathlib import Path

from assignment_autopsy.storage.extractors import extract_text


def test_extract_text_from_markdown(tmp_path: Path) -> None:
    document = tmp_path / "work.md"
    document.write_text("# Entrega\nContenido", encoding="utf-8")
    assert "Contenido" in extract_text(document.read_bytes(), document.suffix)


def test_unsupported_extension_returns_no_text(tmp_path: Path) -> None:
    document = tmp_path / "unsafe.exe"
    document.write_bytes(b"never execute this")
    assert extract_text(document.read_bytes(), document.suffix) == ""
