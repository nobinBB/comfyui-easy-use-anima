# SPDX-License-Identifier: GPL-3.0-only
"""Dynamic multiline text inputs with combined and individual outputs."""

from __future__ import annotations

import random
import re


MAX_TEXT_INPUTS = 20
TEXT_NAMES = tuple(f"text_{index}" for index in range(1, MAX_TEXT_INPUTS + 1))
JOIN_MODES = ("line_by_line", "join_with_delimiter")
CHOICE_GROUP_PATTERN = re.compile(r"\{([^{}]*\|[^{}]*)\}")


def _clean_text(value: object) -> str:
    """Trim a value and collapse every consecutive whitespace run."""

    return " ".join(str(value).split())


def _resolve_choice_groups(value: str) -> str:
    """Replace every {a|b|c} group with one randomly selected alternative."""

    def replace(match: re.Match[str]) -> str:
        options = [part.strip() for part in match.group(1).split("|")]
        options = [option for option in options if option]
        return random.choice(options) if options else ""

    return CHOICE_GROUP_PATTERN.sub(replace, value)


class DynamicTextHub:
    """Expose one to twenty text fields through a compact dynamic UI."""

    @classmethod
    def INPUT_TYPES(cls):
        optional = {
            name: (
                "STRING",
                {
                    "default": "",
                    "multiline": True,
                    "dynamicPrompts": False,
                },
            )
            for name in TEXT_NAMES
        }
        # Keeping count after the text definitions lets the frontend place its
        # arrow control below the currently visible text widgets.
        optional["count"] = (
            "INT",
            {"default": 1, "min": 1, "max": MAX_TEXT_INPUTS, "step": 1},
        )
        # These controls are appended after count so workflows saved by the
        # previous release keep the same serialized text/count widget order.
        optional["mode"] = (JOIN_MODES, {"default": "line_by_line"})
        optional["delimiter"] = (
            "STRING",
            {"default": ", ", "multiline": False, "dynamicPrompts": False},
        )
        optional["clean_whitespace"] = ("BOOLEAN", {"default": False})
        return {"required": {}, "optional": optional}

    RETURN_TYPES = ("STRING",) * (MAX_TEXT_INPUTS + 1)
    RETURN_NAMES = ("text_all",) + TEXT_NAMES
    FUNCTION = "combine"
    CATEGORY = "EasyUse-Anima/Text"
    DESCRIPTION = (
        "Dynamically shows 1-20 multiline text fields. Combine active fields "
        "line by line or with a custom delimiter. Each {a|b|c} group is "
        "automatically replaced with one random choice on every execution."
    )

    @classmethod
    def IS_CHANGED(cls, **kwargs):
        """Force execution so choice groups can be selected again each queue."""

        return float("nan")

    def combine(
        self,
        count: int = 1,
        mode: str = "line_by_line",
        delimiter: str = ", ",
        clean_whitespace: bool = False,
        **kwargs,
    ):
        active_count = max(1, min(MAX_TEXT_INPUTS, int(count)))
        individual = [str(kwargs.get(name, "")) for name in TEXT_NAMES]
        if clean_whitespace:
            individual = [_clean_text(text) for text in individual]
        individual = [_resolve_choice_groups(text) for text in individual]

        active_texts = individual[:active_count]
        separator = str(delimiter) if mode == "join_with_delimiter" else "\n"
        combined = separator.join(active_texts)
        return (combined, *individual)


NODE_CLASS_MAPPINGS = {
    "easy animaDynamicTextHub": DynamicTextHub,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "easy animaDynamicTextHub": "Dynamic Text Hub",
}
