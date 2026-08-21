# SPDX-License-Identifier: GPL-3.0-only
"""Anima image saver with A1111-style generation metadata.

The behavior is based on ``SD Prompt Saver`` from comfyui-prompt-reader-node
(Copyright (c) 2023 Rhys Yang, MIT License). The Anima port resolves models
from ComfyUI's ``diffusion_models`` folder instead of ``checkpoints``.
"""

from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime
from itertools import chain
from pathlib import Path
from typing import Any

import comfy.samplers
import folder_paths
import numpy as np
import piexif
import piexif.helper
from comfy.cli_args import args
from nodes import MAX_RESOLUTION
from PIL import Image
from PIL.PngImagePlugin import PngInfo

try:
    from .anima_model_filter import anima_model_names
except ImportError:  # Direct module loading used by tests and development tools.
    from anima_model_filter import anima_model_names


SUPPORTED_FORMATS = (".png", ".jpg", ".jpeg", ".webp")


class AnyType(str):
    def __ne__(self, other: object) -> bool:
        return False


ANY_TYPE = AnyType("*")


def _log(message: str) -> None:
    print(f"[Anima Prompt Saver] {message}")


class AnimaPromptSaver:
    model_hash_dict: dict[str, str] = {}
    vae_hash_dict: dict[str, str] = {}
    lora_hash_dict: dict[str, str] = {}
    ti_hash_dict: dict[str, str] = {}
    ti_paths: list[str] = []
    ti_names: list[str] = []
    ti_stems: list[str] = []

    def __init__(self):
        self.output_dir = folder_paths.get_output_directory()
        self.type = "output"
        self.prefix_append = ""

    @classmethod
    def INPUT_TYPES(cls):
        embeddings = folder_paths.get_filename_list("embeddings")
        cls.ti_paths = list(embeddings)
        cls.ti_names = [Path(name).name for name in embeddings]
        cls.ti_stems = [Path(name).stem for name in embeddings]

        return {
            "required": {
                "images": ("IMAGE",),
            },
            "optional": {
                "filename": (
                    "STRING",
                    {"default": "ComfyUI_%time_%seed_%counter", "multiline": False},
                ),
                "path": ("STRING", {"default": "%date/", "multiline": False}),
                "model_name": (anima_model_names(),),
                "vae_name": (folder_paths.get_filename_list("vae"),),
                "seed": (
                    "INT",
                    {"default": 0, "min": 0, "max": 0xFFFFFFFFFFFFFFFF},
                ),
                "steps": ("INT", {"default": 20, "min": 1, "max": 10000}),
                "cfg": (
                    "FLOAT",
                    {
                        "default": 8.0,
                        "min": 0.0,
                        "max": 100.0,
                        "step": 0.5,
                        "round": 0.01,
                    },
                ),
                # These are intentionally the exact lists used by core KSampler.
                # Samplers/schedulers registered by extensions are included when
                # those extensions add them to the core lists.
                "sampler_name": (comfy.samplers.KSampler.SAMPLERS,),
                "scheduler": (comfy.samplers.KSampler.SCHEDULERS,),
                "lora_name": (ANY_TYPE,),
                "width": (
                    "INT",
                    {"default": 1, "min": 1, "max": MAX_RESOLUTION, "step": 1},
                ),
                "height": (
                    "INT",
                    {"default": 1, "min": 1, "max": MAX_RESOLUTION, "step": 1},
                ),
                "positive": ("STRING", {"default": "", "multiline": True}),
                "negative": ("STRING", {"default": "", "multiline": True}),
                "extension": (["png", "jpg", "jpeg", "webp"],),
                "calculate_hash": ("BOOLEAN", {"default": True}),
                "resource_hash": ("BOOLEAN", {"default": True}),
                "lossless_webp": ("BOOLEAN", {"default": True}),
                "jpg_webp_quality": (
                    "INT",
                    {"default": 100, "min": 1, "max": 100},
                ),
                "date_format": (
                    "STRING",
                    {"default": "%Y-%m-%d", "multiline": False},
                ),
                "time_format": (
                    "STRING",
                    {"default": "%H%M%S", "multiline": False},
                ),
                "save_metadata_file": ("BOOLEAN", {"default": False}),
                "extra_info": ("STRING", {"default": "", "multiline": True}),
            },
            "hidden": {"prompt": "PROMPT", "extra_pnginfo": "EXTRA_PNGINFO"},
        }

    RETURN_TYPES = ("STRING", "STRING", "STRING")
    RETURN_NAMES = ("FILENAME", "FILE_PATH", "METADATA")
    FUNCTION = "save_images"
    OUTPUT_NODE = True
    CATEGORY = "EasyUse-Anima"
    DESCRIPTION = (
        "Save Anima images with A1111-style metadata. Model names and hashes "
        "are resolved from models/diffusion_models."
    )

    def save_images(
        self,
        images,
        filename: str = "ComfyUI_%time_%seed_%counter",
        path: str = "%date/",
        model_name: str = "",
        model_name_str: str = "",
        vae_name: str = "",
        seed: int = 0,
        steps: int = 0,
        cfg: float = 0.0,
        sampler_name: str = "",
        sampler_name_str: str = "",
        scheduler: str = "",
        scheduler_str: str = "",
        lora_name=None,
        width: int = 1,
        height: int = 1,
        positive: str = "",
        negative: str = "",
        extension: str = "png",
        calculate_hash: bool = True,
        resource_hash: bool = True,
        lossless_webp: bool = True,
        jpg_webp_quality: int = 100,
        date_format: str = "%Y-%m-%d",
        time_format: str = "%H%M%S",
        save_metadata_file: bool = False,
        extra_info: str = "",
        prompt=None,
        extra_pnginfo=None,
    ):
        full_output_folder, _, _, _, _ = folder_paths.get_save_image_path(
            self.prefix_append,
            self.output_dir,
            images[0].shape[1],
            images[0].shape[0],
        )

        results = []
        files = []
        comments = []
        file_paths = []

        for image in images:
            model_name_real = model_name_str if model_name_str else model_name
            sampler_name_real = sampler_name_str if sampler_name_str else sampler_name
            scheduler_real = scheduler_str if scheduler_str else scheduler
            extra_info_real = f", Extra info: {extra_info}" if extra_info else ""

            variable_map = {
                "%date": self.get_time(date_format),
                "%time": self.get_time(time_format),
                "%seed": seed,
                "%steps": steps,
                "%cfg": cfg,
                "%width": width,
                "%height": height,
                "%extension": extension,
                "%model": Path(model_name_real).stem,
                "%sampler": sampler_name_real,
                "%scheduler": scheduler_real,
                "%quality": jpg_webp_quality,
            }

            subfolder = self.get_path(path, variable_map)
            output_folder = Path(full_output_folder) / subfolder
            output_folder.mkdir(parents=True, exist_ok=True)
            variable_map["%counter"] = f"{self.get_counter(output_folder):05}"

            array = 255.0 * image.cpu().numpy()
            img = Image.fromarray(np.clip(array, 0, 255).astype(np.uint8))

            model_hash_str = ""
            vae_hash_str = ""
            vae_str = f"VAE: {Path(vae_name).stem}, " if vae_name else ""
            lora_hash_str = ""
            ti_hash_str = ""
            hashes: dict[str, str] = {}

            if calculate_hash:
                if model_name_real:
                    model_hash = self.calculate_hash(model_name_real, "model")
                    model_hash_str = f"Model hash: {model_hash}, "
                    hashes["model"] = model_hash

                if vae_name:
                    vae_hash = self.calculate_hash(vae_name, "vae")
                    vae_hash_str = f"VAE hash: {vae_hash}, "
                    hashes["vae"] = vae_hash

                if lora_name:
                    lora_names = lora_name if isinstance(lora_name, list) else [lora_name]
                    lora_hashes = {}
                    for name in dict.fromkeys(lora_names):
                        lora_hash = self.calculate_hash(name, "lora")
                        lora_hashes[Path(name).stem] = lora_hash
                        hashes[f"lora:{Path(name).stem}"] = lora_hash
                    value = ", ".join(f"{key}: {item}" for key, item in lora_hashes.items())
                    lora_hash_str = f'Lora hashes: "{value}", '

                ti_pattern = (
                    r"(?:\(|\s|,)?embedding:([^\s:,()]+)"
                    r"(?:\.(?:pt|safetensors))?(?::\d+(?:\.\d+)?)?(?:\)|,|\s)?"
                )
                ti_names = re.findall(ti_pattern, f"{positive}\n{negative}")
                ti_hashes = {}
                for name in (self.search_ti(item) for item in ti_names):
                    if name:
                        ti_hash = self.calculate_hash(name, "ti")
                        ti_hashes[Path(name).stem] = ti_hash
                        hashes[f"embed:{Path(name).stem}"] = ti_hash
                value = ", ".join(f"{key}: {item}" for key, item in ti_hashes.items())
                ti_hash_str = f'TI hashes: "{value}", ' if value else ""

            hashes_str = (
                f", Hashes: {json.dumps(hashes)}" if hashes and resource_hash else ""
            )
            sampler_metadata = sampler_name_real
            if scheduler_real and scheduler_real != "normal":
                sampler_metadata += f"_{scheduler_real}"

            comment = (
                f"{positive}\n"
                f"Negative prompt: {negative}\n"
                f"Steps: {steps}, "
                f"Sampler: {sampler_metadata}, "
                f"CFG scale: {cfg}, "
                f"Seed: {seed}, "
                f"Size: {img.width if width == 0 else width}x"
                f"{img.height if height == 0 else height}, "
                f"{model_hash_str}"
                f"Model: {Path(model_name_real).stem}, "
                f"{vae_hash_str}"
                f"{vae_str}"
                f"{lora_hash_str}"
                f"{ti_hash_str}"
                f"Version: ComfyUI"
                f"{hashes_str}"
                f"{extra_info_real}"
            )

            stem = self.get_path(filename, variable_map)
            file = self.get_unique_filename(stem, extension, output_folder)
            file_path = output_folder / file

            if extension == "png":
                metadata = None
                if not args.disable_metadata:
                    metadata = PngInfo()
                    metadata.add_text("parameters", comment)
                    if prompt is not None:
                        metadata.add_text("prompt", json.dumps(prompt))
                    if extra_pnginfo is not None:
                        for key, value in extra_pnginfo.items():
                            metadata.add_text(key, json.dumps(value))
                img.save(file_path, pnginfo=metadata, compress_level=4)
            else:
                save_options: dict[str, Any] = {"quality": jpg_webp_quality}
                if extension == "webp":
                    save_options["lossless"] = lossless_webp
                img.save(file_path, **save_options)
                if not args.disable_metadata:
                    metadata = piexif.dump(
                        {
                            "Exif": {
                                piexif.ExifIFD.UserComment: piexif.helper.UserComment.dump(
                                    comment, encoding="unicode"
                                )
                            }
                        }
                    )
                    piexif.insert(metadata, str(file_path))

            if save_metadata_file:
                file_path.with_suffix(".txt").write_text(comment, encoding="utf-8")

            results.append(
                {"filename": file.name, "subfolder": str(subfolder), "type": self.type}
            )
            files.append(str(file))
            file_paths.append(str(file_path))
            comments.append(comment)
            _log(f"Saved file: {file}")

        return {
            "ui": {"images": results},
            "result": (
                self.unpack_singleton(files),
                self.unpack_singleton(file_paths),
                self.unpack_singleton(comments),
            ),
        }

    @classmethod
    def calculate_hash(cls, name: str, hash_type: str) -> str:
        locations = {
            "model": (cls.model_hash_dict, "diffusion_models"),
            "vae": (cls.vae_hash_dict, "vae"),
            "lora": (cls.lora_hash_dict, "loras"),
            "ti": (cls.ti_hash_dict, "embeddings"),
        }
        if hash_type not in locations:
            return ""
        hash_dict, folder_name = locations[hash_type]
        if name in hash_dict:
            return hash_dict[name]

        file_name = folder_paths.get_full_path(folder_name, name)
        if not file_name:
            raise FileNotFoundError(
                f"Could not resolve {hash_type} '{name}' in models/{folder_name}."
            )
        hash_sha256 = hashlib.sha256()
        with open(file_name, "rb") as file_handle:
            for chunk in iter(lambda: file_handle.read(1024 * 1024), b""):
                hash_sha256.update(chunk)
        hash_value = hash_sha256.hexdigest()[:10]
        hash_dict[name] = hash_value
        return hash_value

    @staticmethod
    def get_counter(directory: Path) -> int:
        image_files = list(
            chain(*(directory.rglob(f"*{suffix}") for suffix in SUPPORTED_FORMATS))
        )
        return len(image_files) + 1

    @staticmethod
    def get_path(name: str, variable_map: dict[str, Any]) -> Path:
        for variable, value in variable_map.items():
            name = name.replace(variable, str(value))
        return Path(name)

    @staticmethod
    def get_time(time_format: str) -> str:
        try:
            return datetime.now().strftime(time_format)
        except (TypeError, ValueError):
            return ""

    @staticmethod
    def get_unique_filename(stem: Path, extension: str, output_folder: Path) -> Path:
        file = stem.with_suffix(f"{stem.suffix}.{extension}")
        index = 0
        while (output_folder / file).exists():
            index += 1
            new_stem = Path(f"{stem}_{index}")
            file = new_stem.with_suffix(f"{new_stem.suffix}.{extension}")
        return file

    @classmethod
    def search_ti(cls, ti: str) -> str:
        if not ti or ti in cls.ti_paths:
            return ti
        if ti in cls.ti_stems:
            return cls.ti_paths[cls.ti_stems.index(ti)]
        if ti in cls.ti_names:
            return cls.ti_paths[cls.ti_names.index(ti)]
        return ""

    @staticmethod
    def unpack_singleton(items: list[str]):
        return items[0] if len(items) == 1 else items


NODE_CLASS_MAPPINGS = {
    "easy animaPromptSaver": AnimaPromptSaver,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "easy animaPromptSaver": "Anima Prompt Saver",
}
