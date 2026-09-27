from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

import pytest


@pytest.mark.skipif(os.name != "nt", reason="Inno discovery uses Windows PowerShell")
def test_inno_setup_discovery_contract(tmp_path: Path) -> None:
    powershell = shutil.which("powershell.exe") or shutil.which("powershell")
    if not powershell:
        pytest.skip("Windows PowerShell is unavailable")

    repository = Path(__file__).resolve().parents[1]
    result = subprocess.run(
        [
            powershell,
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(repository / "tests" / "test_inno_setup_discovery.ps1"),
            "-ModulePath",
            str(repository / "tools" / "inno_setup_discovery.ps1"),
            "-ScratchPath",
            str(tmp_path / "inno-test"),
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert "Inno Setup discovery tests: PASS" in result.stdout
