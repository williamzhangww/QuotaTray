from pathlib import Path

import pytest

from tools import verify_frozen


@pytest.fixture
def payload(tmp_path, monkeypatch):
    root = tmp_path / "payload"
    for rel in verify_frozen.REQUIRED_QT_FILES:
        file = root / "_internal" / rel
        file.parent.mkdir(parents=True, exist_ok=True)
        file.touch()
    (root / "QuotaTray.exe").touch()
    system = tmp_path / "Windows" / "System32"
    system.mkdir(parents=True)
    (system / "icuuc.dll").touch()
    monkeypatch.setenv("SystemRoot", str(system.parent))
    monkeypatch.setattr(verify_frozen, "_pe_exports", lambda _: set(verify_frozen.QT_REQUIRED_ICU_EXPORTS))
    return root


@pytest.mark.parametrize("relative", ["icuuc.dll", "_internal/icudt78.dll", "_internal/PySide6/ICUIN78.DLL", "_internal/icuio.dll"])
def test_frozen_rejects_icu_anywhere(payload, relative, capsys):
    (payload / relative).touch()
    assert verify_frozen.main(["verify_frozen.py", str(payload)]) == 1
    assert "ERROR: bundled ICU detected" in capsys.readouterr().out


def test_frozen_accepts_payload_without_icu(payload, capsys):
    assert verify_frozen.main(["verify_frozen.py", str(payload)]) == 0
    assert "RESULT: PASS" in capsys.readouterr().out


def test_frozen_rejects_missing_qt_file(payload):
    (payload / "_internal" / verify_frozen.REQUIRED_QT_FILES[0]).unlink()
    assert verify_frozen.main(["verify_frozen.py", str(payload)]) == 1


@pytest.mark.parametrize(
    "relative",
    [
        "_internal/PySide6/Qt6VirtualKeyboard.dll",
        "_internal/PySide6/QtVirtualKeyboard.pyd",
        "_internal/PySide6/plugins/platforminputcontexts/qtvirtualkeyboardplugin.dll",
        "_internal/PySide6/qml/QtQuick/VirtualKeyboard/virtualkeyboardplugin.dll",
    ],
)
def test_frozen_rejects_virtual_keyboard(payload, relative, capsys):
    file = payload / relative
    file.parent.mkdir(parents=True, exist_ok=True)
    file.touch()

    assert verify_frozen.main(["verify_frozen.py", str(payload)]) == 1
    output = capsys.readouterr().out
    assert "ERROR: Qt Virtual Keyboard detected" in output
    assert "RESULT: FAIL" in output


@pytest.mark.parametrize(
    "relative",
    [
        "_internal/PySide6/Qt6Qml.dll",
        "_internal/PySide6/Qt6Quick.dll",
        "_internal/PySide6/Qt6Pdf.dll",
        "_internal/PySide6/Qt6Svg.dll",
        "_internal/PySide6/Qt6OpenGL.dll",
        "_internal/PySide6/opengl32sw.dll",
    ],
)
def test_frozen_rejects_unused_qt_components(payload, relative, capsys):
    file = payload / relative
    file.parent.mkdir(parents=True, exist_ok=True)
    file.touch()

    assert verify_frozen.main(["verify_frozen.py", str(payload)]) == 1
    output = capsys.readouterr().out
    assert "ERROR: unused Qt modules/plugins detected" in output


@pytest.mark.parametrize(
    "relative",
    [
        "_internal/PySide6/plugins/networkinformation/qopensslbackend.dll",
        "_internal/PySide6/libssl-1_1.dll",
        "_internal/libcrypto-1_1.dll",
    ],
)
def test_frozen_rejects_openssl_11_runtime(payload, relative, capsys):
    file = payload / relative
    file.parent.mkdir(parents=True, exist_ok=True)
    file.touch()

    assert verify_frozen.main(["verify_frozen.py", str(payload)]) == 1
    output = capsys.readouterr().out
    assert "ERROR: unused OpenSSL/Python TLS native runtime remains" in output


@pytest.mark.parametrize("name", ["MSVCP140.dll", "msvcp140_2.DLL", "VCRUNTIME140_1.dll"])
def test_frozen_rejects_bundled_msvc_runtime(payload, name, capsys):
    file = payload / "_internal" / "PySide6" / name
    file.parent.mkdir(parents=True, exist_ok=True)
    file.touch()

    assert verify_frozen.main(["verify_frozen.py", str(payload)]) == 1
    output = capsys.readouterr().out
    assert "ERROR: bundled MSVC runtime detected" in output
    assert str(file.relative_to(payload)) in output


@pytest.mark.parametrize(
    "name",
    ["ucrtbase.dll", "api-ms-win-crt-runtime-l1-1-0.dll", "API-MS-WIN-CORE-LIBRARYLOADER-L1-2-0.DLL"],
)
def test_frozen_rejects_app_local_ucrt_and_apisets(payload, name, capsys):
    file = payload / "_internal" / name
    file.parent.mkdir(parents=True, exist_ok=True)
    file.touch()

    assert verify_frozen.main(["verify_frozen.py", str(payload)]) == 1
    output = capsys.readouterr().out
    assert "ERROR: bundled UCRT/API-set runtime detected" in output
    assert str(file.relative_to(payload)) in output


def test_frozen_rejects_standalone_qml_payload(payload, capsys):
    file = payload / "_internal" / "PySide6" / "qml" / "QtQuick" / "thing.qml"
    file.parent.mkdir(parents=True, exist_ok=True)
    file.touch()

    assert verify_frozen.main(["verify_frozen.py", str(payload)]) == 1
    assert "ERROR: unused Qt modules/plugins detected" in capsys.readouterr().out
