# SPDX-License-Identifier: GPL-3.0-only
"""Two-text wrapper for Prompt Control's PC: Schedule LoRAs node."""

from __future__ import annotations

import importlib


PC_NODE_NAME = "PCLazyLoraLoader"


def _combine_text(text_1: object, text_2: object) -> str:
    """Join non-empty text boxes without inserting an empty line."""

    values = (str(text_1), str(text_2))
    return "\n".join(value for value in values if value.strip())


def _get_prompt_control_node_class():
    """Resolve Prompt Control lazily so this extension can still load alone."""

    try:
        comfy_nodes = importlib.import_module("nodes")
    except ImportError as error:
        raise RuntimeError(
            "PC: Schedule LoRAs Plus requires comfyui-prompt-control."
        ) from error

    node_class = getattr(comfy_nodes, "NODE_CLASS_MAPPINGS", {}).get(PC_NODE_NAME)
    if node_class is None:
        raise RuntimeError(
            "PC: Schedule LoRAs Plus requires comfyui-prompt-control. "
            "Install or update Prompt Control, then restart ComfyUI."
        )
    return node_class


class ScheduleLorasTwoText:
    """Schedule LoRAs from two text boxes and also return their combined text."""

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "optional": {
                "model": ("MODEL", {"rawLink": True}),
                "clip": ("CLIP", {"rawLink": True}),
                "text_1": (
                    "STRING",
                    {"multiline": True, "default": "", "dynamicPrompts": False},
                ),
                "text_2": (
                    "STRING",
                    {"multiline": True, "default": "", "dynamicPrompts": False},
                ),
            },
            "hidden": {"unique_id": "UNIQUE_ID"},
        }

    RETURN_TYPES = ("MODEL", "CLIP", "STRING", "STRING")
    RETURN_NAMES = ("model", "clip", "loras_text", "text")
    OUTPUT_TOOLTIPS = (
        "Model with the LoRA schedule applied.",
        "CLIP with the LoRA schedule applied.",
        "Contents of the upper text_1 box.",
        "Combined text_1 and text_2 passed to Prompt Control.",
    )
    FUNCTION = "apply"
    CATEGORY = "EasyUse-Anima/Text"
    DESCRIPTION = (
        "Uses Prompt Control's PC: Schedule LoRAs with two multiline text boxes. "
        "The non-empty boxes are joined with a newline and returned as text."
    )

    def apply(self, unique_id, model=None, clip=None, text_1="", text_2=""):
        combined_text = _combine_text(text_1, text_2)
        prompt_control_node = _get_prompt_control_node_class()()
        response = prompt_control_node.apply(
            unique_id=unique_id,
            model=model,
            clip=clip,
            text=combined_text,
        )

        if not isinstance(response, dict) or "result" not in response:
            raise RuntimeError("PC: Schedule LoRAs returned an invalid response.")

        original_result = tuple(response["result"])
        if len(original_result) < 2:
            raise RuntimeError("PC: Schedule LoRAs did not return MODEL and CLIP.")

        wrapped_response = dict(response)
        wrapped_response["result"] = (
            original_result[0],
            original_result[1],
            str(text_1),
            combined_text,
        )
        return wrapped_response


NODE_CLASS_MAPPINGS = {
    "easy animaScheduleLorasTwoText": ScheduleLorasTwoText,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "easy animaScheduleLorasTwoText": "PC: Schedule LoRAs Plus",
}
