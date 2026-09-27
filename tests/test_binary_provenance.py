from tools.binary_provenance import (
    approved_source_roots,
    contaminated_native_sources,
    native_toc_entries,
    read_collect_toc,
)
from tools import verify_frozen


def test_native_toc_entries_keep_only_native_binary_destinations(tmp_path):
    dll = tmp_path / "good.dll"
    pyd = tmp_path / "extension.pyd"
    rows = [
        ("_internal/good.dll", str(dll), "BINARY"),
        ("_internal/extension.pyd", str(pyd), "EXTENSION"),
        ("assets/icon.ico", str(tmp_path / "icon.ico"), "DATA"),
    ]

    assert native_toc_entries(rows) == [
        ("_internal/good.dll", str(dll)),
        ("_internal/extension.pyd", str(pyd)),
    ]


def test_provenance_accepts_python_and_system_roots(tmp_path):
    project = tmp_path / "project"
    python = tmp_path / "python"
    windows = tmp_path / "Windows"
    project.mkdir()
    python.mkdir()
    windows.mkdir()
    pyside_dll = python / "Lib" / "site-packages" / "PySide6" / "Qt6Core.dll"
    pyside_dll.parent.mkdir(parents=True)
    pyside_dll.touch()
    api_dll = windows / "System32" / "api-ms-win-core-test.dll"
    api_dll.parent.mkdir()
    api_dll.touch()
    roots = approved_source_roots(project, python, windows)

    assert contaminated_native_sources(
        [
            ("PySide6/Qt6Core.dll", str(pyside_dll), "BINARY"),
            ("api-ms-win-core-test.dll", str(api_dll), "BINARY"),
        ],
        roots,
    ) == []


def test_provenance_rejects_codex_cache_even_inside_an_approved_root(tmp_path):
    project = tmp_path / "project"
    python = tmp_path / "python"
    windows = tmp_path / "Windows"
    cache_dll = project / ".cache" / "codex-runtimes" / "libheif" / "ucrtbase.dll"
    cache_dll.parent.mkdir(parents=True)
    cache_dll.touch()
    roots = approved_source_roots(project, python, windows)

    assert contaminated_native_sources(
        [("ucrtbase.dll", str(cache_dll), "BINARY")], roots
    ) == [("ucrtbase.dll", str(cache_dll))]


def test_read_collect_toc(tmp_path):
    source = tmp_path / "python" / "native.dll"
    source.parent.mkdir()
    source.touch()
    toc = tmp_path / "COLLECT-00.toc"
    toc.write_text(repr(([("native.dll", str(source), "BINARY")],)), encoding="utf-8")

    assert read_collect_toc(toc) == [("native.dll", str(source), "BINARY")]


def test_release_verifier_rejects_contaminated_toc(tmp_path, monkeypatch, capsys):
    payload = tmp_path / "payload"
    for rel in verify_frozen.REQUIRED_QT_FILES:
        file = payload / "_internal" / rel
        file.parent.mkdir(parents=True, exist_ok=True)
        file.touch()
    (payload / "QuotaTray.exe").touch()
    system = tmp_path / "Windows"
    (system / "System32").mkdir(parents=True)
    (system / "System32" / "icuuc.dll").touch()
    monkeypatch.setenv("SystemRoot", str(system))
    monkeypatch.setattr(
        verify_frozen,
        "_pe_exports",
        lambda _: set(verify_frozen.QT_REQUIRED_ICU_EXPORTS),
    )
    contaminated = tmp_path / ".cache" / "codex-runtimes" / "libheif" / "ucrtbase.dll"
    contaminated.parent.mkdir(parents=True)
    contaminated.touch()
    toc = tmp_path / "COLLECT-00.toc"
    toc.write_text(
        repr(([("ucrtbase.dll", str(contaminated), "BINARY")],)), encoding="utf-8"
    )

    assert verify_frozen.main(
        ["verify_frozen.py", str(payload), "--toc", str(toc)]
    ) == 1
    output = capsys.readouterr().out
    assert "ERROR: contaminated binary provenance" in output
    assert "ucrtbase.dll" in output
