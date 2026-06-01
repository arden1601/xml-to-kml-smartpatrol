# SMART Patrol XML to KML

Convert SMART Conservation Software patrol XML exports to ArcGIS-compatible KML.

## Install

```bash
python3 -m pip install -r requirements.txt
```

## GUI

Launch the desktop interface:

```bash
python3 run_gui.py
```

The GUI can convert one XML file or a folder of XML files. Leave the output folder blank to write each `.kml` beside its source XML, matching the command-line behavior.

## Single file

```bash
python3 smart_xml_to_kml.py ST_107_T_16_BTNBB_KSA_02_01_B_05_2026.xml
```

This writes `ST_107_T_16_BTNBB_KSA_02_01_B_05_2026.kml` beside the XML.

Use a custom output path:

```bash
python3 smart_xml_to_kml.py input.xml -o output.kml
```

## Batch folder

Convert every `.xml` in a folder:

```bash
python3 smart_xml_to_kml.py /path/to/folder
```

Convert recursively through subfolders:

```bash
python3 smart_xml_to_kml.py /path/to/folder --recursive
```

## Output contents

Each KML contains:

- `Tracks` folder: patrol GPS tracks decoded from SMART WKB geometry.
  - The source track Z value is an epoch-millisecond timestamp, not elevation.
  - The converter drops Z and writes lon,lat only for ArcGIS compatibility.
- `Waypoints` folder: one point per SMART waypoint.
- Observation attributes in both:
  - popup HTML description tables
  - KML `ExtendedData` fields for ArcGIS table/query use
- Photo attachment filenames only. No image links are created.
- Patrol metadata on the KML document: patrol id, dates, station, members, transport, mandate, comment, and `sumberdana` when present.

## ArcGIS Pro

Import with **KML To Layer**.

KML uses WGS84 lon/lat (`EPSG:4326`), as required by KML and expected by ArcGIS.

## Windows EXE

Windows builds are produced by GitHub Actions on a Windows runner. Run the `Build Windows EXE` workflow manually, or push a `v*` tag. Download `SMART-Patrol-XML-to-KML.exe` from the workflow artifacts.

## Troubleshooting

If shapely is missing:

```bash
python3 -m pip install -r requirements.txt
```

For detailed errors during conversion:

```bash
python3 smart_xml_to_kml.py input.xml --traceback
```
