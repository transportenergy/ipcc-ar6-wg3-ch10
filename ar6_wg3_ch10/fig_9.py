import logging

# import plotnine as p9

from .common import Figure

log = logging.getLogger(__name__)


class Fig9(Figure):
    """Placeholder for an aviation figure."""

    has_option = dict(normalize=True)

    # Data preparation
    years = list(range(2020, 2100 + 1, 5))
    variables = []

    def prepare_data(self, data):
        raise NotImplementedError

    def generate(self):
        raise NotImplementedError
