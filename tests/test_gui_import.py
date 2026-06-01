def test_gui_module_imports() -> None:
    import smartpatrol_kml.gui as gui

    assert gui.SmartPatrolApp is not None
    assert gui.main is not None


def test_run_gui_imports() -> None:
    import run_gui

    assert run_gui.main is not None
