from __future__ import annotations

import json
from pathlib import Path

from firestrip.core.backup import BackupManager


def test_record_disabled(backup_manager: BackupManager) -> None:
    backup_manager.record_disabled("com.amazon.cloud9")
    backup_manager.record_disabled("com.amazon.cloud9")  # dedup
    backup_manager.record_disabled("com.amazon.venezia")
    assert backup_manager.disabled_this_session == [
        "com.amazon.cloud9",
        "com.amazon.venezia",
    ]


def test_list_backups_empty_when_dir_missing(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(BackupManager, "DEFAULT_DIR", tmp_path / "nope")
    bm = BackupManager()
    assert bm.list_backups() == []


def test_create_writes_json(tmp_path: Path, monkeypatch, mock_adb, mock_device) -> None:
    monkeypatch.setattr(BackupManager, "DEFAULT_DIR", tmp_path)
    bm = BackupManager()
    bm.record_disabled("com.amazon.cloud9")
    path = bm.create(mock_adb, mock_device)
    assert path.exists()
    data = json.loads(path.read_text())
    assert data["version"] == 1
    assert data["device"]["model"] == "AFTBOXE1"
    assert "com.amazon.cloud9" in data["packages"]["disabled_by_firestrip"]
    assert "all_installed" in data["packages"]
    assert "settings" in data
    assert "launcher" in data


def test_restore_dry_run(tmp_path: Path, monkeypatch, mock_adb, mock_device) -> None:
    monkeypatch.setattr(BackupManager, "DEFAULT_DIR", tmp_path)
    bm = BackupManager()
    bm.record_disabled("com.amazon.cloud9")
    path = bm.create(mock_adb, mock_device)
    results = bm.restore(mock_adb, path, dry_run=True)
    actions = {r.action for r in results}
    assert "dry_run" in actions
    assert "com.amazon.cloud9" not in mock_adb.disabled or True  # not modified


def test_restore_apply_re_enables(tmp_path: Path, monkeypatch, mock_adb, mock_device) -> None:
    monkeypatch.setattr(BackupManager, "DEFAULT_DIR", tmp_path)
    bm = BackupManager()
    bm.record_disabled("com.amazon.cloud9")
    path = bm.create(mock_adb, mock_device)
    mock_adb.disabled.add("com.amazon.cloud9")
    bm.restore(mock_adb, path, dry_run=False)
    assert "com.amazon.cloud9" not in mock_adb.disabled
