from pathlib import Path
import xml.etree.ElementTree as ET

import smart_xml_to_kml


def test_convert_minimal_patrol_fixture(tmp_path: Path) -> None:
    source = Path(__file__).parent / "fixtures" / "minimal_patrol.xml"
    output = tmp_path / "minimal.kml"

    stats = smart_xml_to_kml.convert_file(source, output)

    assert stats.tracks == 0
    assert stats.waypoints == 1
    assert output.exists()

    tree = ET.parse(output)
    root = tree.getroot()
    assert root.tag.endswith("kml")
    text = output.read_text(encoding="utf-8")
    assert "PATROL-001" in text
    assert "Green turtle" in text
    assert "sumberdana" in text
