#!/usr/bin/env python3
"""Command-line entry point for SMART Patrol XML to KML conversion."""

from smartpatrol_kml.converter import ConvertStats, convert_file, find_xml_files, main

__all__ = ["ConvertStats", "convert_file", "find_xml_files", "main"]


if __name__ == "__main__":
    raise SystemExit(main())
