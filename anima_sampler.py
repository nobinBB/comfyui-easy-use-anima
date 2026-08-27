# SPDX-License-Identifier: GPL-3.0-only
"""Anima full sampler with optional Easy-Use integration and a core fallback."""

from __future__ import annotations

from typing import Any

import comfy.samplers
import nodes


IMAGE_OUTPUT_MODES = [
    "Hide",
    "Preview",
    "Save",
    "Hide&Save",
    "Sender",
    "Sender&Save",
    "None",
]


class _KSamplerReturnTypes:
    """Resolve standard KSampler COMBO choices after every extension has loaded."""

    def __get__(self, instance, owner):
        return (
            "PIPE_LINE",
            "IMAGE",
            "MODEL",
            "CONDITIONING",
            "CONDITIONING",
            "LATENT",
            "VAE",
            "CLIP",
            "INT",
            "FLOAT",
            "INT",
            comfy.samplers.KSampler.SAMPLERS,
            comfy.samplers.KSampler.SCHEDULERS,
        )


def _base_sampler_class():
    """Return Easy-Use's full sampler when it is installed, otherwise None."""
    return nodes.NODE_CLASS_MAPPINGS.get("easy fullkSampler")


def _standalone_input_types() -> dict[str, dict[str, Any]]:
    return {
        "required": {
            "pipe": ("PIPE_LINE",),
            "steps": ("INT", {"default": 20, "min": 1, "max": 10000}),
            "cfg": (
                "FLOAT",
                {"default": 8.0, "min": 0.0, "max": 100.0, "step": 0.1},
            ),
            "sampler_name": (comfy.samplers.KSampler.SAMPLERS,),
            "scheduler": (comfy.samplers.KSampler.SCHEDULERS,),
            "denoise": (
                "FLOAT",
                {"default": 1.0, "min": 0.0, "max": 1.0, "step": 0.01},
            ),
            "image_output": (IMAGE_OUTPUT_MODES,),
            "link_id": (
                "INT",
                {"default": 0, "min": 0, "max": 0x7FFFFFFFFFFFFFFF, "step": 1},
            ),
            "save_prefix": ("STRING", {"default": "ComfyUI"}),
        },
        "optional": {
            "seed": (
                "INT",
                {
                    "default": 0,
                    "min": 0,
                    "max": 0xFFFFFFFFFFFFFFFF,
                    "control_after_generate": True,
                },
            ),
            "model": ("MODEL",),
            "positive": ("CONDITIONING",),
            "negative": ("CONDITIONING",),
            "latent": ("LATENT",),
            "vae": ("VAE",),
            "clip": ("CLIP",),
            "image": ("IMAGE",),
        },
        "hidden": {
            "tile_size": "INT",
            "prompt": "PROMPT",
            "extra_pnginfo": "EXTRA_PNGINFO",
            "my_unique_id": "UNIQUE_ID",
        },
    }


def _require(value: Any, name: str) -> Any:
    if value is None:
        raise RuntimeError(
            f"EasyKSampler (Full) - Anima requires '{name}'. "
            f"Connect the optional {name} input or provide it in the input pipe."
        )
    return value


def _save_or_preview(
    images: Any,
    image_output: str,
    save_prefix: str,
    prompt: Any,
    extra_pnginfo: Any,
) -> list[dict[str, Any]]:
    if image_output in ("Preview", "Sender"):
        node_name = "PreviewImage"
    elif image_output in ("Save", "Hide&Save", "Sender&Save"):
        node_name = "SaveImage"
    else:
        return []

    saver_class = nodes.NODE_CLASS_MAPPINGS.get(node_name)
    if saver_class is None:
        raise RuntimeError(f"ComfyUI core node '{node_name}' is unavailable.")

    saved = saver_class().save_images(
        images,
        filename_prefix=save_prefix,
        prompt=prompt,
        extra_pnginfo=extra_pnginfo,
    )
    return list(saved.get("ui", {}).get("images", []))


class AnimaFullKSampler:
    """Use Easy-Use when available and ComfyUI core sampling when it is not."""

    @classmethod
    def INPUT_TYPES(cls):
        base_sampler = _base_sampler_class()
        if base_sampler is not None:
            return base_sampler.INPUT_TYPES()
        return _standalone_input_types()

    RETURN_TYPES = _KSamplerReturnTypes()
    RETURN_NAMES = (
        "pipe",
        "image",
        "model",
        "positive",
        "negative",
        "latent",
        "vae",
        "clip",
        "steps",
        "cfg",
        "seed",
        "sampler_name",
        "scheduler",
    )
    OUTPUT_NODE = True
    FUNCTION = "run"
    CATEGORY = "EasyUse-Anima/Sampler"
    DESCRIPTION = (
        "Anima full sampler. Uses EasyKSampler (Full) when ComfyUI-Easy-Use is "
        "installed and automatically falls back to ComfyUI core sampling when "
        "it is not. The actual model, sampler, and scheduler are preserved in "
        "the output pipe. Steps and CFG are also exposed for metadata saving."
    )

    def run(
        self,
        pipe,
        steps,
        cfg,
        sampler_name,
        scheduler,
        denoise,
        image_output,
        link_id,
        save_prefix,
        **kwargs,
    ):
        base_sampler = _base_sampler_class()
        if base_sampler is not None:
            return self._run_with_easy_use(
                base_sampler,
                pipe,
                steps,
                cfg,
                sampler_name,
                scheduler,
                denoise,
                image_output,
                link_id,
                save_prefix,
                **kwargs,
            )
        return self._run_standalone(
            pipe,
            steps,
            cfg,
            sampler_name,
            scheduler,
            denoise,
            image_output,
            link_id,
            save_prefix,
            **kwargs,
        )

    def _run_with_easy_use(
        self,
        base_sampler_class,
        pipe,
        steps,
        cfg,
        sampler_name,
        scheduler,
        denoise,
        image_output,
        link_id,
        save_prefix,
        **kwargs,
    ):
        result = base_sampler_class().run(
            pipe=pipe,
            steps=steps,
            cfg=cfg,
            sampler_name=sampler_name,
            scheduler=scheduler,
            denoise=denoise,
            image_output=image_output,
            link_id=link_id,
            save_prefix=save_prefix,
            **kwargs,
        )
        if not isinstance(result, dict) or "result" not in result:
            raise RuntimeError("EasyKSampler (Full) returned an unsupported result.")

        outputs = list(result["result"])
        if len(outputs) < 9 or not isinstance(outputs[0], dict):
            raise RuntimeError("EasyKSampler (Full) returned an incomplete pipe.")

        used_model = kwargs.get("model")
        if used_model is None:
            used_model = outputs[0].get("model", pipe.get("model"))

        fixed_pipe = {
            **outputs[0],
            "model": used_model,
            "loader_settings": {
                **outputs[0].get("loader_settings", {}),
                "steps": steps,
                "cfg": cfg,
                "sampler_name": sampler_name,
                "scheduler": scheduler,
                "denoise": denoise,
            },
        }
        outputs = outputs[:9]
        outputs[0] = fixed_pipe
        outputs[2] = used_model
        outputs[8:8] = (steps, cfg)
        outputs.extend((sampler_name, scheduler))
        return {**result, "result": tuple(outputs)}

    def _run_standalone(
        self,
        pipe,
        steps,
        cfg,
        sampler_name,
        scheduler,
        denoise,
        image_output,
        link_id,
        save_prefix,
        **kwargs,
    ):
        model = kwargs.get("model")
        positive = kwargs.get("positive")
        negative = kwargs.get("negative")
        latent = kwargs.get("latent")
        vae = kwargs.get("vae")
        clip = kwargs.get("clip")
        model = _require(model if model is not None else pipe.get("model"), "model")
        positive = _require(
            positive if positive is not None else pipe.get("positive"), "positive"
        )
        negative = _require(
            negative if negative is not None else pipe.get("negative"), "negative"
        )
        latent = _require(
            latent if latent is not None else pipe.get("samples"), "latent"
        )
        vae = vae if vae is not None else pipe.get("vae")
        clip = clip if clip is not None else pipe.get("clip")
        seed = kwargs.get("seed")
        if seed is None:
            seed = pipe.get("seed", 0)

        source_image = kwargs.get("image")
        if source_image is not None and kwargs.get("latent") is None:
            vae = _require(vae, "vae")
            latent = {"samples": vae.encode(source_image[:, :, :, :3])}

        sampled_latent = nodes.common_ksampler(
            model,
            seed,
            steps,
            cfg,
            sampler_name,
            scheduler,
            positive,
            negative,
            latent,
            denoise=denoise,
        )[0]

        images = None
        if image_output != "None":
            vae = _require(vae, "vae")
            samples = sampled_latent["samples"]
            tile_size = kwargs.get("tile_size")
            if tile_size is not None:
                images = vae.decode_tiled(
                    samples, tile_x=tile_size // 8, tile_y=tile_size // 8
                )
            else:
                images = vae.decode(samples)
            if hasattr(images, "cpu"):
                images = images.cpu()
            if getattr(images, "ndim", None) == 5:
                images = images.reshape(
                    -1, images.shape[-3], images.shape[-2], images.shape[-1]
                )

        prompt = kwargs.get("prompt")
        extra_pnginfo = kwargs.get("extra_pnginfo")
        ui_images = _save_or_preview(
            images, image_output, save_prefix, prompt, extra_pnginfo
        )

        if image_output in ("Sender", "Sender&Save") and ui_images:
            try:
                from server import PromptServer

                PromptServer.instance.send_sync(
                    "img-send", {"link_id": link_id, "images": ui_images}
                )
            except (AttributeError, ImportError):
                pass

        new_pipe = {
            **pipe,
            "model": model,
            "positive": positive,
            "negative": negative,
            "samples": sampled_latent,
            "vae": vae,
            "clip": clip,
            "images": images,
            "seed": seed,
            "loader_settings": {
                **pipe.get("loader_settings", {}),
                "steps": steps,
                "cfg": cfg,
                "sampler_name": sampler_name,
                "scheduler": scheduler,
                "denoise": denoise,
            },
        }

        visible_ui = image_output not in ("Hide", "Hide&Save", "None")
        return {
            "ui": {"images": ui_images} if visible_ui else {},
            "result": (
                new_pipe,
                images,
                model,
                positive,
                negative,
                sampled_latent,
                vae,
                clip,
                steps,
                cfg,
                seed,
                sampler_name,
                scheduler,
            ),
        }


NODE_CLASS_MAPPINGS = {
    "easy animaFullKSampler": AnimaFullKSampler,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "easy animaFullKSampler": "EasyKSampler (Full) - Anima",
}
