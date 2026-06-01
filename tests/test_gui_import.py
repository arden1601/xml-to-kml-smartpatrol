def test_gui_module_imports() -> None:
    import smartpatrol_kml.gui as gui

    assert gui.SmartPatrolApp is not None
    assert gui.main is not None
