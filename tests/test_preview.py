from pathlib import Path

from smartpatrol_kml.preview import preview_file, preview_path

FIXTURES = Path(__file__).parent / "fixtures"


def test_preview_file_reads_patrol_metadata() -> None:
    info = preview_file(FIXTURES / "minimal_patrol.xml")

    assert info.is_valid is True
    assert info.patrol_id == "PATROL-001"
    assert info.station == "Resort Teluk Terima"
    assert info.start_date == "2026-05-06"
    assert info.end_date == "2026-05-08"
    assert info.legs == 1
    assert info.tracks == 0
    assert info.waypoints == 1
    assert info.members == ["Budi Santoso [E001] (leader)"]
    assert info.error == ""


def test_preview_file_rejects_non_patrol_xml(tmp_path: Path) -> None:
    source = tmp_path / "not_patrol.xml"
    source.write_text("<root />", encoding="utf-8")

    info = preview_file(source)

    assert info.is_valid is False
    assert "not a SMART patrol XML file" in info.error


def test_preview_path_counts_folder_xml_files() -> None:
    batch = preview_path(FIXTURES, recursive=False)

    assert batch.source == FIXTURES
    assert batch.xml_files == 1
    assert batch.first_valid is not None
    assert batch.first_valid.patrol_id == "PATROL-001"
