// SPDX-License-Identifier: GPL-3.0-only

import { app } from "../../../scripts/app.js";

const NODE_NAME = "easy animaLatentUpscaleWithVAEBy";

function resizeNode(node) {
    const computed = node.computeSize?.() || [320, 160];
    const currentWidth = Number(node.size?.[0]) || 320;
    node.setSize?.([Math.max(320, currentWidth, computed[0]), computed[1]]);
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

function setupRatioVisibility(node) {
    if (node.__easyAnimaRatioReady) return;
    const methodWidget = (node.widgets || []).find(
        (widget) => widget.name === "upscale_method",
    );
    const ratioWidget = (node.widgets || []).find(
        (widget) => widget.name === "bislerp_ratio",
    );
    if (!methodWidget || !ratioWidget) return;

    node.__easyAnimaRatioReady = true;
    node.__easyAnimaMethodWidget = methodWidget;
    node.__easyAnimaRatioWidget = ratioWidget;
    node.__applyEasyAnimaRatioVisibility = (method) => {
        const visible = method === "bislerp";
        setWidgetVisible(ratioWidget, visible);
        resizeNode(node);
        requestAnimationFrame(() => {
            setWidgetVisible(ratioWidget, visible);
            resizeNode(node);
        });
    };

    const originalCallback = methodWidget.callback;
    methodWidget.callback = function (value) {
        const result = originalCallback?.apply(this, arguments);
        const nextValue = result ?? value;
        node.__applyEasyAnimaRatioVisibility(nextValue);
        return nextValue;
    };

    node.__applyEasyAnimaRatioVisibility(methodWidget.value);
}

function scheduleSetup(node) {
    const apply = () => {
        setupRatioVisibility(node);
        if (node.__easyAnimaRatioReady) {
            node.__applyEasyAnimaRatioVisibility(node.__easyAnimaMethodWidget.value);
        }
    };
    queueMicrotask(apply);
    setTimeout(apply, 50);
    setTimeout(apply, 250);
}

app.registerExtension({
    name: "easy-use-anima.LatentUpscaleWithVAEBy",
    async beforeRegisterNodeDef(nodeType, nodeData) {
        if (nodeData.name !== NODE_NAME) return;

        const originalOnNodeCreated = nodeType.prototype.onNodeCreated;
        nodeType.prototype.onNodeCreated = function () {
            const result = originalOnNodeCreated?.apply(this, arguments);
            scheduleSetup(this);
            return result;
        };

        const originalOnAdded = nodeType.prototype.onAdded;
        nodeType.prototype.onAdded = function () {
            const result = originalOnAdded?.apply(this, arguments);
            scheduleSetup(this);
            return result;
        };

        const originalOnConfigure = nodeType.prototype.onConfigure;
        nodeType.prototype.onConfigure = function () {
            const result = originalOnConfigure?.apply(this, arguments);
            scheduleSetup(this);
            return result;
        };
    },
    nodeCreated(node) {
        if (node.comfyClass === NODE_NAME || node.type === NODE_NAME) {
            scheduleSetup(node);
        }
    },
});
