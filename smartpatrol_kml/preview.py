from __future__ import annotations

import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from pathlib import Path

from smartpatrol_kml.converter import children, find_xml_files, local_name


@dataclass
class PreviewInfo:
    source: Path
    is_valid: bool
    patrol_id: str = ""
    station: str = ""
    start_date: str = ""
    end_date: str = ""
    legs: int = 0
    tracks: int = 0
    waypoints: int = 0
    members: list[str] = field(default_factory=list)
    error: str = ""
    warnings: list[str] = field(default_factory=list)


@dataclass
class PathPreview:
    source: Path
    is_file: bool
    xml_files: int = 0
    first_valid: PreviewInfo | None = None
    error: str = ""


def preview_file(source: Path) -> PreviewInfo:
    source = source.resolve()
    try:
        tree = ET.parse(source)
    except Exception as exc:  # noqa: BLE001 - user-facing preview should not crash
        return PreviewInfo(source=source, is_valid=False, error=f"invalid XML: {exc}")

    root = tree.getroot()
    if local_name(root.tag) != "patrol":
        return PreviewInfo(
            source=source,
            is_valid=False,
            error=f"not a SMART patrol XML file: root is <{local_name(root.tag)}>",
        )

    station = ""
    stations = children(root, "station")
    if stations:
        station = stations[0].attrib.get("value", "").strip()

    legs = children(root, "legs")
    members: list[str] = []
    tracks = 0
    waypoints = 0

    for leg in legs:
        for member in children(leg, "members"):
            member_text = _member_label(member)
            if member_text:
                members.append(member_text)
        for day in children(leg, "days"):
            tracks += len(children(day, "track"))
            waypoints += len(children(day, "waypoints"))

    return PreviewInfo(
        source=source,
        is_valid=True,
        patrol_id=root.attrib.get("id", "").strip() or source.stem,
        station=station,
        start_date=root.attrib.get("startDate", "").strip(),
        end_date=root.attrib.get("endDate", "").strip(),
        legs=len(legs),
        tracks=tracks,
        waypoints=waypoints,
        members=members,
    )


def preview_path(source: Path, recursive: bool = False) -> PathPreview:
    source = source.resolve()
    if source.is_file():
        info = preview_file(source)
        xml_files = 1 if source.suffix.lower() == ".xml" else 0
        return PathPreview(source=source, is_file=True, xml_files=xml_files, first_valid=info)

    if not source.exists():
        return PathPreview(source=source, is_file=False, error="source does not exist")

    xml_files = find_xml_files(source, recursive)
    first_valid = None
    for xml_file in xml_files:
        info = preview_file(xml_file)
        if info.is_valid:
            first_valid = info
            break

    return PathPreview(source=source, is_file=False, xml_files=len(xml_files), first_valid=first_valid)


def _member_label(member: ET.Element) -> str:
    name = " ".join(
        part.strip()
        for part in (member.attrib.get("givenName", ""), member.attrib.get("familyName", ""))
        if part.strip()
    )
    employee_id = member.attrib.get("employeeId", "").strip()
    roles = []
    if member.attrib.get("isLeader", "false").lower() == "true":
        roles.append("leader")
    if member.attrib.get("isPilot", "false").lower() == "true":
        roles.append("pilot")
    role_text = f" ({', '.join(roles)})" if roles else ""
    id_text = f" [{employee_id}]" if employee_id else ""
    return f"{name}{id_text}{role_text}".strip()
