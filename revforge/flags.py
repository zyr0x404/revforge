"""Flag creation and formatting."""

from __future__ import annotations

from random import Random

DEFAULT_FLAG_FORMAT = "zyr0x{{{value}}}"

_SYLLABLES = [
    "r3v",
    "x0r",
    "vm",
    "c0d3",
    "b1n",
    "gdb",
    "r0p",
    "k3y",
    "s1gn",
    "tr4ce",
    "p4tch",
    "br34k",
    "l00p",
    "m4p",
    "7r41n1ng",
    "cr4ck",
]


def render_flag(flag_format: str, value: str) -> str:
    """Render a flag using RevForge's {{{value}}} placeholder convention."""

    if "{value}" in flag_format:
        try:
            return flag_format.format(value=value)
        except (KeyError, IndexError, ValueError) as exc:
            raise ValueError('flag format must use the placeholder "{value}", e.g. "zyr0x{{{value}}}"') from exc
    return f"{flag_format}{value}"


def random_flag_value(rng: Random) -> str:
    pieces = [rng.choice(_SYLLABLES) for _ in range(rng.randint(2, 4))]
    suffix = f"{rng.getrandbits(16):04x}"
    return "_".join([*pieces, suffix])


def resolve_flag(
    rng: Random,
    *,
    flag: str | None,
    random_flag: bool,
    flag_format: str | None,
) -> tuple[str, str]:
    """Return (flag, flag_format). Direct flags are preserved exactly."""

    selected_format = flag_format or DEFAULT_FLAG_FORMAT
    if flag:
        return flag, selected_format
    value = random_flag_value(rng)
    return render_flag(selected_format, value), selected_format
