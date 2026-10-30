"""Synthetic pack. Entry that calls the adder."""

from app import add


def start() -> int:
    return add(2, 3)
