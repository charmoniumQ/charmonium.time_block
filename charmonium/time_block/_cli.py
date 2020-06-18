import click

from ._lib import returns_four


@click.command()
def main() -> None:
    """CLI for charmonium.time_block."""
    print(returns_four())
