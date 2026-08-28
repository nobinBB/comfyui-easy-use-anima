// SPDX-License-Identifier: GPL-3.0-only

import { app } from "../../../scripts/app.js";

const NODE_NAME = "easy animaDynamicTextHub";
const MAX_TEXT_INPUTS = 20;
const TEXTBOX_HEIGHT = 110;
const TEXT_NAME_PATTERN = /^text_(\d+)$/;
const MODE_LINE_BY_LINE = "line_by_line";
const MODE_JOIN_WITH_DELIMITER = "join_with_delimiter";
const SUPPORTED_MODES = new Set([
    MODE_LINE_BY_LINE,
    MODE_JOIN_WITH_DELIMITER,
]);

function clampCount(value) {
    const parsed = Math.round(Number(value) || 1);
    return Math.max(1, Math.min(MAX_TEXT_INPUTS, parsed));
}

function resizeNode(node) {
    const computed = node.computeSize?.() || [360, 240];
    const currentWidth = Number(node.size?.[0]) || 360;
    node.setSize?.([Math.max(360, currentWidth, computed[0]), computed[1]]);
    node.updateConnectionsPos?.();
    node.setDirtyCanvas?.(true, true);
}

function setTextboxElementStyle(widget, visible) {
    const element = widget.inputEl || widget.input || widget.element || widget.textarea;
    if (!element?.style) return;

    element.style.display = visible ? "" : "none";
    if (!visible) return;

    element.style.height = `${TEXTBOX_HEIGHT - 10}px`;
    element.style.minHeight = `${TEXTBOX_HEIGHT - 10}px`;
    element.style.maxHeight = `${TEXTBOX_HEIGHT - 10}px`;
    element.style.boxSizing = "border-box";
    element.style.resize = "none";
    element.style.overflowY = "auto";
}

function prepareTextboxWidget(widget) {
    if (widget.__dynamicTextTextbox) return;
    widget.__dynamicTextTextbox = true;

    widget.computeSize = function (width) {
        return this.hidden ? [Number(width) || 0, 0] : [Number(width) || 320, TEXTBOX_HEIGHT];
    };

    // ComfyUI's current Vue/LiteGraph layout reads this API for DOM widgets.
    // Keeping computeSize above also supports older frontend releases.
    widget.computeLayoutSize = function () {
        const height = this.hidden ? 0 : TEXTBOX_HEIGHT;
        return { minHeight: height, maxHeight: height, minWidth: 0 };
    };
}

function setWidgetVisible(widget, visible) {
    prepareTextboxWidget(widget);
    widget.hidden = !visible;
    widget.options ||= {};
    widget.options.noDraw = !visible;
    widget.computedHeight = visible ? TEXTBOX_HEIGHT : 0;
    setTextboxElementStyle(widget, visible);
}

function addTextInputSlot(node, template, widget) {
    const {
        name,
        type,
        link,
        pos,
        boundingRect,
        ...options
    } = template;
    const input = node.addInput(name, type, options);
    input.widget ||= { name };
    // The current frontend keeps a weak reference from widget input slots to
    // their widget. Reconnect it when a slot is restored after count grows.
    if ("_widget" in input) input._widget = widget;
    return input;
}

function syncTextInputSlots(node, count) {
    const templates = node.__dynamicTextInputTemplates;

    // Removing the inactive slots also removes their hit targets. Merely
    // hiding their textareas leaves connectable circles below the node.
    for (let index = MAX_TEXT_INPUTS; index > count; index--) {
        const name = `text_${index}`;
        const inputIndex = node.inputs.findIndex((input) => input.name === name);
        if (inputIndex >= 0) node.removeInput(inputIndex);
    }

    for (let index = 1; index <= count; index++) {
        const name = `text_${index}`;
        if (node.inputs.some((input) => input.name === name)) continue;

        const template = templates.get(name);
        if (!template) continue;
        // Keep addInput's append position. Moving the slot afterward leaves
        // ComfyUI's index-keyed Vue layout cache pointing at the old index,
        // which makes the connection circle drift to a different textbox.
        // Widget input slots are positioned by widget.name, so array order is
        // not required to match the visual textbox order.
        addTextInputSlot(node, template, node.__dynamicTextWidgets[index - 1]);
    }
}

function prepareHideableControl(widget) {
    if (widget.__dynamicTextHideableControl) return;
    widget.__dynamicTextHideableControl = true;
    widget.__dynamicTextOriginalType = widget.type;
    widget.__dynamicTextOriginalComputeSize = widget.computeSize;
    widget.__dynamicTextOriginalComputeLayoutSize = widget.computeLayoutSize;
}

function setControlVisible(widget, visible) {
    if (!widget) return;
    prepareHideableControl(widget);
    widget.hidden = !visible;
    widget.options ||= {};
    widget.options.noDraw = !visible;

    if (visible) {
        widget.type = widget.__dynamicTextOriginalType;
        widget.computeSize = widget.__dynamicTextOriginalComputeSize;
        widget.computeLayoutSize = widget.__dynamicTextOriginalComputeLayoutSize;
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

function scheduleDynamicTextHubSetup(node) {
    const apply = () => {
        setupDynamicTextHub(node);
        if (!node.__dynamicTextHubReady) return;
        node.__applyDynamicTextCount(node.__dynamicTextCountWidget.value, false);
        node.__applyDynamicTextMode(node.__dynamicTextModeWidget.value);
    };

    queueMicrotask(apply);
    setTimeout(apply, 50);
    setTimeout(apply, 250);
}

function setupDynamicTextHub(node) {
    if (node.__dynamicTextHubReady) return;

    const textWidgets = (node.widgets || [])
        .filter((widget) => TEXT_NAME_PATTERN.test(widget.name))
        .sort((a, b) => Number(a.name.slice(5)) - Number(b.name.slice(5)));
    const countWidget = (node.widgets || []).find((widget) => widget.name === "count");
    const modeWidget = (node.widgets || []).find((widget) => widget.name === "mode");
    const delimiterWidget = (node.widgets || []).find((widget) => widget.name === "delimiter");
    const outputTemplates = [...(node.outputs || [])];
    const textInputTemplates = (node.inputs || [])
        .filter((input) => TEXT_NAME_PATTERN.test(input.name));

    if (
        textWidgets.length !== MAX_TEXT_INPUTS
        || !countWidget
        || !modeWidget
        || !delimiterWidget
        || textInputTemplates.length !== MAX_TEXT_INPUTS
    ) return;

    node.__dynamicTextHubReady = true;
    node.__dynamicTextWidgets = textWidgets;
    node.__dynamicTextCountWidget = countWidget;
    node.__dynamicTextModeWidget = modeWidget;
    node.__dynamicTextDelimiterWidget = delimiterWidget;
    node.__dynamicTextOutputs = outputTemplates;
    node.__dynamicTextInputTemplates = new Map(
        textInputTemplates.map((input) => [input.name, input]),
    );

    node.__applyDynamicTextMode = (mode) => {
        const normalizedMode = SUPPORTED_MODES.has(mode) ? mode : MODE_LINE_BY_LINE;
        const showDelimiter = normalizedMode === MODE_JOIN_WITH_DELIMITER;
        modeWidget.value = normalizedMode;
        setControlVisible(delimiterWidget, showDelimiter);
        resizeNode(node);
        requestAnimationFrame(() => {
            setControlVisible(delimiterWidget, showDelimiter);
            resizeNode(node);
        });
    };

    node.__applyDynamicTextCount = (requestedCount, disconnectRemoved = true) => {
        const count = clampCount(requestedCount);
        const oldCount = Math.max(0, (node.outputs?.length || 1) - 1);

        if (disconnectRemoved && count < oldCount) {
            for (let outputIndex = oldCount; outputIndex > count; outputIndex--) {
                node.disconnectOutput?.(outputIndex);
            }
        }

        countWidget.value = count;
        textWidgets.forEach((widget, index) => setWidgetVisible(widget, index < count));
        syncTextInputSlots(node, count);

        // Use LiteGraph's slot methods instead of assigning node.outputs.
        // The current Vue frontend keeps a reactive slot cache that otherwise
        // can display a stale name (for example text_20 on a two-slot node).
        while (node.outputs.length > count + 1) {
            node.removeOutput(node.outputs.length - 1);
        }
        while (node.outputs.length < count + 1) {
            const template = outputTemplates[node.outputs.length];
            const { name, type, links, ...options } = template;
            node.addOutput(name, type, options);
        }
        resizeNode(node);
        // DOM textareas are attached after node creation. Re-apply their
        // dimensions once the frontend has mounted them, then resize again.
        requestAnimationFrame(() => {
            textWidgets.forEach((widget, index) => {
                setTextboxElementStyle(widget, index < count);
            });
            resizeNode(node);
        });
    };

    const originalCountCallback = countWidget.callback;
    countWidget.callback = function (value) {
        const result = originalCountCallback?.apply(this, arguments);
        const nextValue = result ?? value;
        node.__applyDynamicTextCount(nextValue);
        return clampCount(nextValue);
    };

    const originalModeCallback = modeWidget.callback;
    modeWidget.callback = function (value) {
        const result = originalModeCallback?.apply(this, arguments);
        const nextValue = result ?? value;
        node.__applyDynamicTextMode(nextValue);
        return nextValue;
    };

    node.__applyDynamicTextCount(countWidget.value, false);
    node.__applyDynamicTextMode(modeWidget.value);
}

app.registerExtension({
    name: "easy-use-anima.DynamicTextHub",
    async beforeRegisterNodeDef(nodeType, nodeData) {
        if (nodeData.name !== NODE_NAME) return;

        const originalOnNodeCreated = nodeType.prototype.onNodeCreated;
        nodeType.prototype.onNodeCreated = function () {
            const result = originalOnNodeCreated?.apply(this, arguments);
            // The Vue frontend builds its visual slot cache immediately after
            // onNodeCreated. Trim on the next microtask so removeOutput events
            // update both LiteGraph and the rendered slot labels.
            scheduleDynamicTextHubSetup(this);
            return result;
        };

        const originalOnAdded = nodeType.prototype.onAdded;
        nodeType.prototype.onAdded = function () {
            const result = originalOnAdded?.apply(this, arguments);
            scheduleDynamicTextHubSetup(this);
            return result;
        };

        const originalOnConfigure = nodeType.prototype.onConfigure;
        nodeType.prototype.onConfigure = function (info) {
            const result = originalOnConfigure?.apply(this, arguments);
            const node = this;
            queueMicrotask(() => {
                if (!node.__dynamicTextHubReady) setupDynamicTextHub(node);
                if (!node.__dynamicTextHubReady) return;

                // Preserve serialized output objects so existing links survive
                // workflow reload before the dynamic list is trimmed again.
                for (const output of node.outputs || []) {
                    const templateIndex = node.__dynamicTextOutputs.findIndex(
                        (template) => template.name === output.name,
                    );
                    if (templateIndex >= 0) node.__dynamicTextOutputs[templateIndex] = output;
                }
                for (const input of node.inputs || []) {
                    if (TEXT_NAME_PATTERN.test(input.name)) {
                        node.__dynamicTextInputTemplates.set(input.name, input);
                    }
                }

                node.__applyDynamicTextCount(node.__dynamicTextCountWidget.value, false);
                node.__applyDynamicTextMode(node.__dynamicTextModeWidget.value);
            });
            return result;
        };
    },
    nodeCreated(node) {
        if (node.comfyClass === NODE_NAME || node.type === NODE_NAME) {
            scheduleDynamicTextHubSetup(node);
        }
    },
});
