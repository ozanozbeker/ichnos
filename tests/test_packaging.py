import importlib.resources

import ichnos


def test_the_package_imports():
    assert ichnos.__name__ == "ichnos"


def test_the_package_has_a_typing_marker():
    # The editable install reads src/, so this catches a deleted marker but not a wheel without one.
    marker = importlib.resources.files("ichnos").joinpath("py.typed")
    assert marker.is_file()
