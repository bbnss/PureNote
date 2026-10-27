"""Android display density and font preferences must remain independent."""

import sys
from types import SimpleNamespace

import pytest


@pytest.mark.parametrize("density", [1.0, 2.625, 3.5])
@pytest.mark.parametrize("font_scale", [1.0, 1.5, 2.0])
def test_android_uses_display_density_and_native_font_curve(monkeypatch, density, font_scale):
    import theme

    display = SimpleNamespace(density=density, scaledDensity=density * font_scale)
    resources = SimpleNamespace(
        getDisplayMetrics=lambda: display,
        getConfiguration=lambda: SimpleNamespace(fontScale=font_scale),
    )
    activity = SimpleNamespace(getResources=lambda: resources)

    def native_size(unit, size, metrics):
        assert unit == 2
        assert metrics is display
        # A nonlinear curve deliberately differs from multiplying by fontScale.
        scale = font_scale if size <= 14 else 1 + (font_scale - 1) * 0.7
        return density * size * scale

    classes = {
        "org.kivy.android.PythonActivity": SimpleNamespace(mActivity=activity),
        "android.util.TypedValue": SimpleNamespace(COMPLEX_UNIT_SP=2, applyDimension=native_size),
    }
    monkeypatch.setitem(sys.modules, "jnius", SimpleNamespace(autoclass=classes.__getitem__))
    monkeypatch.setattr(theme, "Metrics", SimpleNamespace(density=0, fontscale=0))
    monkeypatch.setattr(theme, "_android_font", None)

    theme.configure_android_scaling()

    assert theme.Metrics.density == density
    assert theme.Metrics.fontscale == font_scale
    assert theme.font(11) == pytest.approx(native_size(2, 11, display))
    assert theme.font(18) == pytest.approx(native_size(2, 18, display))
