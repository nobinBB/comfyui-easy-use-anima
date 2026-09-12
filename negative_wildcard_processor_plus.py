# SPDX-License-Identifier: GPL-3.0-only
"""Move marked positive text to negative text without altering LoRA tags."""

from __future__ import annotations

import re


NEGATIVE_BLOCK_PATTERN = re.compile(r"<!(.*?)!>", re.DOTALL)


class NegativeWildcardProcessorPlus:
    """Process only <!text!> blocks and preserve every other prompt tag."""

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "positive": (
                    "STRING",
                    {"forceInput": True, "default": "", "multiline": True},
                ),
                "negative": (
                    "STRING",
                    {"forceInput": True, "default": "", "multiline": True},
                ),
            }
        }

    RETURN_TYPES = ("STRING", "STRING")
    RETURN_NAMES = ("text_positive", "text_negative")
    FUNCTION = "process_negative_wildcards"
    CATEGORY = "EasyUse-Anima/Text"
    DESCRIPTION = (
        "Moves only text enclosed by <! and !> from positive to negative. "
        "Multiline blocks are supported, and LoRA or other angle-bracket tags "
        "are preserved unchanged."
    )

    def process_negative_wildcards(self, positive: object, negative: object):
        positive_text = str(positive)
        negative_text = str(negative)

        moved_blocks = NEGATIVE_BLOCK_PATTERN.findall(positive_text)
        processed_positive = NEGATIVE_BLOCK_PATTERN.sub("", positive_text)

        processed_negative = negative_text
        for block in moved_blocks:
            if not block:
                continue
            separator = (
                ""
                if not processed_negative or processed_negative[-1].isspace()
                else " "
            )
            processed_negative += separator + block

        return (processed_positive, processed_negative)


NODE_CLASS_MAPPINGS = {
    "easy animaNegativeWildcardProcessorPlus": NegativeWildcardProcessorPlus,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "easy animaNegativeWildcardProcessorPlus": "Negative Wildcard Processor Plus",
}
