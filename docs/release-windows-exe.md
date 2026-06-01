# Windows EXE Release Notes

## Build

The Windows executable is built by GitHub Actions.

Manual build:

1. Open the **Build Windows EXE** workflow in GitHub Actions.
2. Click **Run workflow**.
3. Download the `SMART-Patrol-XML-to-KML-windows` artifact.

Tag build:

```bash
git tag v0.1.0
git push origin v0.1.0
```

## Artifact

The workflow uploads:

```text
SMART-Patrol-XML-to-KML.exe
```

## Smoke Test on Windows

1. Double-click `SMART-Patrol-XML-to-KML.exe`.
2. Select a SMART patrol XML file.
3. Confirm preview metadata appears.
4. Click **Convert to KML**.
5. Confirm a `.kml` file is created beside the XML, or in the selected output folder.
6. Import the KML into ArcGIS Pro using **KML To Layer**.
