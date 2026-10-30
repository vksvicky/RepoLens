"""Synthetic pack. Keeps digits from a short string."""


def digits(raw: str) -> str:
    return "".join(ch for ch in raw if ch.isdigit())
