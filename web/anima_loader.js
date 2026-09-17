// SPDX-License-Identifier: GPL-3.0-only

import { app } from "../../../scripts/app.js";

const NODE_NAME = "easy animaLoaderV2";
const NO_CHECKPOINT = "None (use separate model / CLIP / VAE)";
const WIDGET_LAYOUT_VERSION = 1;
const SEPARATE_COMPONENT_WIDGETS = [
    "model_name",
    "weight_dtype",
    "clip_name",
    "clip_device",
    "vae_name",
];

function resizeNode(node) {
    const computed = node.computeSize?.() || [360, 240];
    const currentWidth = Number(node.size?.[0]) || 360;
    node.setSize?.([Math.max(360, currentWidth, computed[0]), computed[1]]);
    node.updateConnectionsPos?.();
    node.setDirtyCanvas?.(true, true);
}

function prepareHideableWidget(widget) {
    if (widget.__easyAnimaHideable) return;
    widget.__easyAnimaHideable = true;
    widget.__easyAnimaOriginalType = widget.type;
    widget.__easyAnimaOriginalComputeSize = widget.computeSize;
    widget.__easyAnimaOriginalComputeLayoutSize = widget.computeLayoutSize;
}

function setWidgetVisible(widget, visible) {
    if (!widget) return;
    prepareHideableWidget(widget);
    widget.hidden = !visible;
    widget.options ||= {};
    widget.options.noDraw = !visible;

    if (visible) {
        widget.type = widget.__easyAnimaOriginalType;
        widget.computeSize = widget.__easyAnimaOriginalComputeSize;
        widget.computeLayoutSize = widget.__easyAnimaOriginalComputeLayoutSize;
        delete widget.computedHeight;
    } else {
        widget.type = "easy-anima-hidden";
        widget.computeSize = () => [0, -4];
        widget.computeLayoutSize = () => ({ minHeight: 0, maxHeight: 0, minWidth: 0 });
        widget.computedHeight = 0;
    }

    const element = widget.inputEl || widget.input || widget.element;
    if (element?.style) element.style.display = visible ? "" : "none";
}

function applyCheckpointVisibility(node) {
    const checkPointWidget = node.widgets?.find((widget) => widget.name === "checkPoint");
    if (!checkPointWidget) return;

    const useCheckpoint = Boolean(
        checkPointWidget.value && checkPointWidget.value !== NO_CHECKPOINT,
    );
    for (const name of SEPARATE_COMPONENT_WIDGETS) {
        const widget = node.widgets?.find((candidate) => candidate.name === name);
        setWidgetVisible(widget, !useCheckpoint);
    }
    resizeNode(node);
}

function migrateWidgetValues(info) {
    if (!info || !Array.isArray(info.widgets_values)) return;
    const version = Number(info.properties?.easyAnimaLoaderWidgetLayoutVersion || 0);
    if (version >= WIDGET_LAYOUT_VERSION) return;

    const oldValues = [...info.widgets_values];
    if (oldValues.length === 9) {
        // Layout before full-checkpoint support.
        info.widgets_values = [NO_CHECKPOINT, ...oldValues];
    } else if (oldValues.length >= 10) {
        // Previous layout placed the checkpoint selector after batch_size.
        info.widgets_values = [oldValues[9], ...oldValues.slice(0, 9), ...oldValues.slice(10)];
    }

    info.properties ||= {};
    info.properties.easyAnimaLoaderWidgetLayoutVersion = WIDGET_LAYOUT_VERSION;
}

function installLoaderUi(node) {
    if (node.__easyAnimaLoaderUiInstalled) return;
    node.__easyAnimaLoaderUiInstalled = true;

    const originalConfigure = node.configure;
    node.configure = function (info) {
        migrateWidgetValues(info);
        const result = originalConfigure?.apply(this, arguments);
        this.properties ||= {};
        this.properties.easyAnimaLoaderWidgetLayoutVersion = WIDGET_LAYOUT_VERSION;
        queueMicrotask(() => applyCheckpointVisibility(this));
        setTimeout(() => applyCheckpointVisibility(this), 50);
        return result;
    };

    node.properties ||= {};
    node.properties.easyAnimaLoaderWidgetLayoutVersion = WIDGET_LAYOUT_VERSION;

    const checkPointWidget = node.widgets?.find((widget) => widget.name === "checkPoint");
    if (checkPointWidget && !checkPointWidget.__easyAnimaVisibilityCallback) {
        checkPointWidget.__easyAnimaVisibilityCallback = true;
        const originalCallback = checkPointWidget.callback;
        checkPointWidget.callback = function (value) {
            const result = originalCallback?.apply(this, arguments);
            queueMicrotask(() => applyCheckpointVisibility(node));
            return result ?? value;
        };
    }

    queueMicrotask(() => applyCheckpointVisibility(node));
    setTimeout(() => applyCheckpointVisibility(node), 50);
    setTimeout(() => applyCheckpointVisibility(node), 250);
}

app.registerExtension({
    name: "easy-use-anima.AnimaLoader",
    nodeCreated(node) {
        if (node.comfyClass === NODE_NAME || node.type === NODE_NAME) {
            installLoaderUi(node);
        }
    },
});
