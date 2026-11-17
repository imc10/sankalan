"""paths.py: settings.json, folder checks for Change… (T25, ENV-5, UX-11)."""
import json
from pathlib import Path

import pytest

from conftest import make_paths, spec
from sankalan import paths
from sankalan.db import datafolder


@spec("T25", "DEP-03")
def test_default_paths_from_environment(monkeypatch, tmp_path):
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "L"))
    monkeypatch.setenv("TEMP", str(tmp_path / "T"))
    p = paths.AppPaths.from_environment()
    assert p.root == tmp_path / "L" / "Sankalan"
    assert p.temp == tmp_path / "T" / "Sankalan"
    assert p.default_data_folder == tmp_path / "L" / "Sankalan" / "Data"
    assert p.logs == tmp_path / "L" / "Sankalan" / "logs"
    assert paths.load_settings(p) == {"data_folder": str(tmp_path / "L" / "Sankalan" / "Data")}


def test_settings_round_trip_and_bad_file(tmp_path):
    p = make_paths(tmp_path)
    paths.save_settings(p, {"data_folder": r"D:\SankalanData", "other": 1})
    assert json.loads(p.settings_file.read_text(encoding="utf-8"))["data_folder"] == r"D:\SankalanData"
    assert paths.data_folder(p) == Path(r"D:\SankalanData")
    p.settings_file.write_text("{not json", encoding="utf-8")
    assert paths.data_folder(p) == p.default_data_folder


def test_empty_folder_keeps_the_folder(tmp_path):
    (tmp_path / "a" / "b").mkdir(parents=True)
    (tmp_path / "a" / "b" / "x.tmp").write_bytes(b"1")
    (tmp_path / "y.tmp").write_bytes(b"1")
    paths.empty_folder(tmp_path)
    assert tmp_path.is_dir() and list(tmp_path.iterdir()) == []
    paths.empty_folder(tmp_path / "missing")          # no error


@spec("ENV-5", "T25", "DEP-08")
@pytest.mark.parametrize("path", [r"\\fileserver\share\Sankalan", "//fileserver/share/Sankalan",
                                  r"\\?\UNC\fileserver\share\Sankalan"])
def test_unc_paths_are_network(path):
    assert paths.is_network_path(path)


@spec("ENV-5", "T25", "DEP-08")
def test_mapped_drive_is_network(monkeypatch):
    monkeypatch.setattr(paths, "_drive_type", lambda d: paths.DRIVE_REMOTE if d == "Z:\\" else 3)
    assert paths.is_network_path(r"Z:\Sankalan")
    assert not paths.is_network_path(r"D:\SankalanData")
    assert not paths.is_network_path(r"\\?\D:\SankalanData")


def test_local_drive_is_not_network(tmp_path):
    assert not paths.is_network_path(tmp_path)


@spec("T25", "R6", "DEP-09")
def test_onedrive_detection(monkeypatch, tmp_path):
    monkeypatch.setenv("OneDrive", str(tmp_path / "OneDrive"))
    assert paths.is_onedrive_path(tmp_path / "OneDrive" / "Data")
    assert paths.is_onedrive_path(r"C:\Users\x\OneDrive - Acme Ltd\Sankalan")
    monkeypatch.delenv("OneDrive")
    for var in ("OneDriveConsumer", "OneDriveCommercial"):
        monkeypatch.delenv(var, raising=False)
    assert not paths.is_onedrive_path(tmp_path / "SankalanData")
    assert not paths.is_onedrive_path(r"C:\Users\x\OneDriveBackup\Sankalan")


# ---------------------------------------------------------------------------------------------- Change… checks
@spec("ENV-5", "DEP-08")
def test_destination_refuses_network(monkeypatch, tmp_path):
    monkeypatch.setattr(paths, "_drive_type", lambda d: paths.DRIVE_REMOTE)
    for dest in (r"\\fileserver\share\Sankalan", r"Z:\Sankalan"):
        c = datafolder.check_destination(tmp_path / "Data", Path(dest))
        assert c.refusal == datafolder.NETWORK_REFUSAL


def test_destination_must_be_empty_and_outside(monkeypatch, tmp_path):
    for var in ("OneDrive", "OneDriveConsumer", "OneDriveCommercial"):
        monkeypatch.delenv(var, raising=False)
    cur = tmp_path / "Data"
    cur.mkdir()
    full = tmp_path / "Full"
    full.mkdir()
    (full / "keep.txt").write_text("mine")
    assert datafolder.check_destination(cur, full).refusal == datafolder.NOT_EMPTY_REFUSAL
    assert datafolder.check_destination(cur, cur).refusal == datafolder.SAME_REFUSAL
    assert datafolder.check_destination(cur, cur / "sub").refusal == datafolder.INSIDE_REFUSAL
    assert datafolder.check_destination(cur, tmp_path).refusal == datafolder.INSIDE_REFUSAL
    assert datafolder.check_destination(cur, tmp_path / "New", needed_bytes=10 ** 18).refusal \
        == datafolder.SPACE_REFUSAL
    ok = datafolder.check_destination(cur, tmp_path / "New", needed_bytes=10)
    assert ok.ok and ok.warnings == []
    (tmp_path / "Empty").mkdir()
    assert datafolder.check_destination(cur, tmp_path / "Empty").ok


@spec("T25", "DEP-09")
def test_destination_warns_for_onedrive(monkeypatch, tmp_path):
    monkeypatch.setenv("OneDrive", str(tmp_path / "OneDrive"))
    c = datafolder.check_destination(tmp_path / "Data", tmp_path / "OneDrive" / "Sankalan")
    assert c.ok and c.warnings == [datafolder.ONEDRIVE_WARNING]
