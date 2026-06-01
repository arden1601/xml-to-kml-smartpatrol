#!/usr/bin/env python3
"""Convert SMART Conservation patrol XML exports to ArcGIS-compatible KML."""

from __future__ import annotations

import argparse
import html
import sys
import traceback
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable

try:
    from shapely import wkb
    from shapely.geometry import GeometryCollection, LineString, MultiLineString
except ImportError as exc:  # pragma: no cover - user-facing guard
    raise SystemExit(
        "Missing dependency: shapely. Install with: python3 -m pip install -r requirements.txt"
    ) from exc

KML_NS = "http://www.opengis.net/kml/2.2"
ET.register_namespace("", KML_NS)


@dataclass
class ConvertStats:
    source: Path
    output: Path
    tracks: int = 0
    waypoints: int = 0
    warnings: list[str] = field(default_factory=list)


def q(tag: str) -> str:
    return f"{{{KML_NS}}}{tag}"


def local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1] if "}" in tag else tag


def children(element: ET.Element, name: str) -> list[ET.Element]:
    return [child for child in list(element) if local_name(child.tag) == name]


def descendants(element: ET.Element, name: str) -> list[ET.Element]:
    return [node for node in element.iter() if local_name(node.tag) == name]


def first_text(element: ET.Element | None, default: str = "") -> str:
    if element is None or element.text is None:
        return default
    return element.text.strip()


def elem(parent: ET.Element, tag: str, text: str | None = None, **attrs: str) -> ET.Element:
    node = ET.SubElement(parent, q(tag), attrs)
    if text is not None:
        node.text = text
    return node


def warn(stats: ConvertStats, message: str) -> None:
    stats.warnings.append(message)
    print(f"warning: {stats.source.name}: {message}", file=sys.stderr)


def add_extended_data(parent: ET.Element, data: dict[str, str]) -> None:
    if not data:
        return
    extended = elem(parent, "ExtendedData")
    for key, value in data.items():
        if value == "":
            continue
        data_el = elem(extended, "Data", name=key)
        elem(data_el, "value", value)


def add_data_value(data: dict[str, str], key: str, value: str) -> None:
    key = key.strip()
    value = value.strip()
    if not key or not value:
        return
    if key in data and data[key]:
        existing = [part.strip() for part in data[key].split("; ")]
        if value not in existing:
            data[key] = f"{data[key]}; {value}"
    else:
        data[key] = value


def html_table(rows: Iterable[tuple[str, str]]) -> str:
    body = []
    for key, value in rows:
        if value == "":
            continue
        body.append(
            "<tr>"
            f"<th>{html.escape(key)}</th>"
            f"<td>{html.escape(value)}</td>"
            "</tr>"
        )
    if not body:
        return ""
    return (
        '<table border="1" cellpadding="3" cellspacing="0">'
        "<tr><th>Field</th><th>Value</th></tr>"
        + "".join(body)
        + "</table>"
    )


def clean_category(category: str) -> str:
    parts = [part for part in category.strip(".").split(".") if part]
    if not parts:
        return "Observation"
    return parts[-1].replace("_", " ").replace("-", " ").title()


def extract_attribute_value(attr: ET.Element) -> str:
    for inline_name in ("stringValue", "value", "doubleValue", "intValue", "booleanValue"):
        if inline_name in attr.attrib:
            return attr.attrib[inline_name].strip()

    for value_tag in ("itemKey", "sValue", "dValue", "iValue", "bValue"):
        values = [first_text(child) for child in children(attr, value_tag)]
        values = [value for value in values if value]
        if values:
            return "; ".join(values)

    return first_text(attr)


def collect_waypoint_data(waypoint: ET.Element) -> tuple[list[tuple[str, str]], dict[str, str], list[str], list[str]]:
    rows: list[tuple[str, str]] = []
    data: dict[str, str] = {}
    categories: list[str] = []
    photos: list[str] = []

    for observation in descendants(waypoint, "observations"):
        category = observation.attrib.get("categoryKey", "").strip()
        if category:
            categories.append(category)
            rows.append(("category", category))
            add_data_value(data, "category", category)

        for attr in children(observation, "attributes"):
            key = attr.attrib.get("attributeKey") or attr.attrib.get("key") or "attribute"
            value = extract_attribute_value(attr)
            rows.append((key, value))
            add_data_value(data, key, value)

        for attachment in children(observation, "attachments"):
            filename = attachment.attrib.get("filename", "").strip()
            if filename:
                photos.append(filename)

    if photos:
        photo_list = ", ".join(photos)
        rows.append(("photos", photo_list))
        data["photos"] = photo_list

    return rows, data, categories, photos


def iter_lines(geometry) -> Iterable[LineString]:
    if isinstance(geometry, LineString):
        yield geometry
    elif isinstance(geometry, MultiLineString):
        yield from geometry.geoms
    elif isinstance(geometry, GeometryCollection):
        for child in geometry.geoms:
            yield from iter_lines(child)


def kml_coords_from_line(line: LineString) -> str:
    coords = []
    for coord in line.coords:
        lon, lat = coord[0], coord[1]
        coords.append(f"{lon:.8f},{lat:.8f}")
    return " ".join(coords)


def coords_are_valid(lon: float, lat: float) -> bool:
    return -180 <= lon <= 180 and -90 <= lat <= 90


def add_styles(document: ET.Element) -> None:
    track_style = elem(document, "Style", id="trackStyle")
    line_style = elem(track_style, "LineStyle")
    elem(line_style, "color", "ffff00ff")  # KML AABBGGRR: opaque magenta.
    elem(line_style, "width", "2")

    point_style = elem(document, "Style", id="waypointStyle")
    icon_style = elem(point_style, "IconStyle")
    elem(icon_style, "scale", "1.0")
    icon = elem(icon_style, "Icon")
    elem(icon, "href", "http://maps.google.com/mapfiles/kml/paddle/red-circle.png")


def collect_patrol_metadata(root: ET.Element) -> tuple[list[tuple[str, str]], dict[str, str]]:
    rows: list[tuple[str, str]] = []
    data: dict[str, str] = {}

    for key in ("id", "patrolType", "startDate", "endDate", "isArmed"):
        value = root.attrib.get(key, "").strip()
        if value:
            rows.append((key, value))
            data[key] = value

    station = children(root, "station")
    if station:
        value = station[0].attrib.get("value", "").strip()
        if value:
            rows.append(("station", value))
            data["station"] = value

    transports: list[str] = []
    members: list[str] = []
    mandates: list[str] = []

    for leg in children(root, "legs"):
        leg_id = leg.attrib.get("id", "").strip()
        for transport in children(leg, "transportType"):
            value = transport.attrib.get("value", "").strip()
            if value and value not in transports:
                transports.append(value)

        for member in children(leg, "members"):
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
            leg_text = f"leg {leg_id}: " if leg_id else ""
            member_text = f"{leg_text}{name}{id_text}{role_text}".strip()
            if member_text and member_text not in members:
                members.append(member_text)

        for mandate in children(leg, "mandate"):
            value = mandate.attrib.get("value", "").strip()
            if value and value not in mandates:
                mandates.append(value)

    if transports:
        value = "; ".join(transports)
        rows.append(("transportType", value))
        data["transportType"] = value
    if members:
        value = "; ".join(members)
        rows.append(("members", value))
        data["members"] = value
    if mandates:
        value = "; ".join(mandates)
        rows.append(("mandate", value))
        data["mandate"] = value

    comment = children(root, "comment")
    if comment:
        value = first_text(comment[0])
        if value:
            rows.append(("comment", value))
            data["comment"] = value

    for attr in children(root, "attributes"):
        key = attr.attrib.get("key") or attr.attrib.get("attributeKey")
        if not key:
            continue
        value = extract_attribute_value(attr)
        if value:
            rows.append((key, value))
            data[key] = value

    return rows, data


def add_track_placemarks(root: ET.Element, tracks_folder: ET.Element, stats: ConvertStats) -> None:
    track_index = 0
    for leg in children(root, "legs"):
        leg_id = leg.attrib.get("id", "").strip() or "unknown"
        for day in children(leg, "days"):
            date = day.attrib.get("date", "").strip()
            for track in children(day, "track"):
                track_index += 1
                geom_hex = track.attrib.get("geom", "").strip()
                if not geom_hex:
                    warn(stats, f"track {track_index} has no geom; skipped")
                    continue
                try:
                    geometry = wkb.loads(bytes.fromhex(geom_hex))
                except Exception as exc:  # noqa: BLE001 - continue batch on bad source data
                    warn(stats, f"track {track_index} WKB decode failed: {exc}; skipped")
                    continue

                lines = [line for line in iter_lines(geometry) if len(line.coords) >= 2]
                if not lines:
                    warn(stats, f"track {track_index} decoded to no lines; skipped")
                    continue

                placemark = elem(tracks_folder, "Placemark")
                elem(placemark, "name", f"Track {track_index} — Leg {leg_id}" + (f" — {date}" if date else ""))
                elem(placemark, "styleUrl", "#trackStyle")

                distance = track.attrib.get("distance", "").strip()
                rows = [("track", str(track_index)), ("leg", leg_id)]
                data = {"track": str(track_index), "leg": leg_id}
                if date:
                    rows.append(("date", date))
                    data["date"] = date
                if distance:
                    rows.append(("distance", distance))
                    data["distance"] = distance
                elem(placemark, "description", html_table(rows))
                add_extended_data(placemark, data)

                if len(lines) == 1:
                    add_line_string(placemark, lines[0])
                else:
                    multi = elem(placemark, "MultiGeometry")
                    for line in lines:
                        add_line_string(multi, line)
                stats.tracks += 1


def add_line_string(parent: ET.Element, line: LineString) -> None:
    line_string = elem(parent, "LineString")
    elem(line_string, "tessellate", "1")
    elem(line_string, "altitudeMode", "clampToGround")
    elem(line_string, "coordinates", kml_coords_from_line(line))


def add_waypoint_placemarks(root: ET.Element, waypoints_folder: ET.Element, stats: ConvertStats) -> None:
    waypoint_index = 0
    for leg in children(root, "legs"):
        leg_id = leg.attrib.get("id", "").strip()
        for day in children(leg, "days"):
            date = day.attrib.get("date", "").strip()
            for waypoint in children(day, "waypoints"):
                waypoint_index += 1
                waypoint_id = waypoint.attrib.get("id", "").strip() or str(waypoint_index)
                try:
                    lon = float(waypoint.attrib["x"])
                    lat = float(waypoint.attrib["y"])
                except (KeyError, ValueError) as exc:
                    warn(stats, f"waypoint {waypoint_id} has bad/missing x/y: {exc}; skipped")
                    continue
                if not coords_are_valid(lon, lat):
                    warn(stats, f"waypoint {waypoint_id} coords out of lon/lat range: {lon},{lat}; skipped")
                    continue

                rows, data, categories, _photos = collect_waypoint_data(waypoint)
                category_name = clean_category(categories[0]) if categories else "Observation"
                name = f"WP {waypoint_index:03d} — {category_name} (id {waypoint_id})"

                time_value = waypoint.attrib.get("time", "").strip()
                if leg_id:
                    add_data_value(data, "leg", leg_id)
                add_data_value(data, "waypoint_id", waypoint_id)
                add_data_value(data, "longitude", f"{lon:.8f}")
                add_data_value(data, "latitude", f"{lat:.8f}")
                if date:
                    add_data_value(data, "date", date)
                if time_value:
                    add_data_value(data, "time", time_value)

                description_rows = [
                    ("waypoint_id", waypoint_id),
                    ("longitude", f"{lon:.8f}"),
                    ("latitude", f"{lat:.8f}"),
                ]
                if leg_id:
                    description_rows.append(("leg", leg_id))
                if date:
                    description_rows.append(("date", date))
                if time_value:
                    description_rows.append(("time", time_value))
                description_rows.extend(rows)

                placemark = elem(waypoints_folder, "Placemark")
                elem(placemark, "name", name)
                elem(placemark, "styleUrl", "#waypointStyle")
                elem(placemark, "description", html_table(description_rows))
                add_extended_data(placemark, data)

                if date and time_value:
                    timestamp = elem(placemark, "TimeStamp")
                    elem(timestamp, "when", f"{date}T{time_value}")

                point = elem(placemark, "Point")
                elem(point, "altitudeMode", "clampToGround")
                elem(point, "coordinates", f"{lon:.8f},{lat:.8f}")
                stats.waypoints += 1


def convert_file(source: Path, output: Path | None = None) -> ConvertStats:
    source = source.resolve()
    if output is None:
        output = source.with_suffix(".kml")
    else:
        output = output.resolve()

    stats = ConvertStats(source=source, output=output)
    tree = ET.parse(source)
    root = tree.getroot()
    if local_name(root.tag) != "patrol":
        raise ValueError(f"not a SMART patrol XML file: root is <{local_name(root.tag)}>")

    patrol_id = root.attrib.get("id") or source.stem
    kml = ET.Element(q("kml"))
    document = elem(kml, "Document")
    elem(document, "name", patrol_id)
    add_styles(document)

    patrol_rows, patrol_data = collect_patrol_metadata(root)
    elem(document, "description", html_table(patrol_rows))
    add_extended_data(document, patrol_data)

    tracks_folder = elem(document, "Folder")
    elem(tracks_folder, "name", "Tracks")
    add_track_placemarks(root, tracks_folder, stats)

    waypoints_folder = elem(document, "Folder")
    elem(waypoints_folder, "name", "Waypoints")
    add_waypoint_placemarks(root, waypoints_folder, stats)

    ET.indent(kml, space="  ")
    output.parent.mkdir(parents=True, exist_ok=True)
    ET.ElementTree(kml).write(output, encoding="utf-8", xml_declaration=True)
    return stats


def find_xml_files(path: Path, recursive: bool) -> list[Path]:
    if path.is_file():
        return [path]
    pattern = "**/*.xml" if recursive else "*.xml"
    return sorted(file for file in path.glob(pattern) if file.is_file())


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Convert SMART Conservation patrol XML exports to ArcGIS-compatible KML."
    )
    parser.add_argument("input", type=Path, help="SMART patrol XML file or directory")
    parser.add_argument("-o", "--output", type=Path, help="Output KML path for single-file conversion")
    parser.add_argument("--recursive", action="store_true", help="When input is a directory, convert XML files recursively")
    parser.add_argument("--traceback", action="store_true", help="Print Python tracebacks for failed files")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    input_path = args.input.resolve()

    if not input_path.exists():
        print(f"error: input not found: {input_path}", file=sys.stderr)
        return 2
    if input_path.is_dir() and args.output:
        print("error: --output can only be used with a single XML file", file=sys.stderr)
        return 2

    files = find_xml_files(input_path, args.recursive)
    if not files:
        print(f"error: no XML files found in {input_path}", file=sys.stderr)
        return 1

    converted = 0
    failed = 0
    for source in files:
        try:
            stats = convert_file(source, args.output if len(files) == 1 else None)
        except Exception as exc:  # noqa: BLE001 - batch should continue after one bad file
            failed += 1
            print(f"failed: {source}: {exc}", file=sys.stderr)
            if args.traceback:
                traceback.print_exc()
            continue
        converted += 1
        print(
            f"converted: {stats.source} -> {stats.output} "
            f"({stats.tracks} tracks, {stats.waypoints} waypoints, {len(stats.warnings)} warnings)"
        )

    print(f"summary: {converted} converted, {failed} failed")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
