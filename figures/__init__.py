import matplotlib as mpl

import fig1, fig2, fig3, fig4, fig5, fig6  # noqa: E401

__all__ = [
    "fig1",
    "fig2",
    "fig3",
    "fig4",
    "fig5",
    "fig6",
]

# Matplotlib style
mpl.rc("font", **{"family": "sans-serif", "sans-serif": ["Helvetica"]})
