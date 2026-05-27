(function () {
  const config = window.ParklDrawing || {};
  const canvas = new fabric.Canvas("drawingCanvas", {
    preserveObjectStacking: true,
    selection: true,
    fireRightClick: true
  });
  fabric.Object.prototype.cornerColor = "#6f42c1";
  fabric.Object.prototype.cornerStrokeColor = "#ffffff";
  fabric.Object.prototype.borderColor = "#6f42c1";
  fabric.Object.prototype.cornerStyle = "circle";
  fabric.Object.prototype.transparentCorners = false;

  const customProps = [
    "objectId", "objectType", "label", "notes", "status", "lineType",
    "x", "y", "rotation", "scale"
  ];
  const gridSize = 20;
  const saveStatus = document.querySelector("#saveStatus");
  const zoomValue = document.querySelector("#zoomValue");
  const modeIndicator = document.querySelector("#modeIndicator");
  const objectLabel = document.querySelector("#objectLabel");
  const objectStatus = document.querySelector("#objectStatus");
  const objectNotes = document.querySelector("#objectNotes");
  const objectType = document.querySelector("#objectType");
  const objectX = document.querySelector("#objectX");
  const objectY = document.querySelector("#objectY");
  const objectRotation = document.querySelector("#objectRotation");
  const objectScale = document.querySelector("#objectScale");
  const lineType = document.querySelector("#lineType");
  const snapToGrid = document.querySelector("#snapToGrid");
  const modeButtons = {
    select: document.querySelector("#selectMode"),
    pan: document.querySelector("#panMode"),
    text: document.querySelector("#textMode"),
    line: document.querySelector("#lineMode")
  };

  let mode = "select";
  let isPanning = false;
  let lastPosX = 0;
  let lastPosY = 0;
  let isDrawingLine = false;
  let activeLine = null;
  let history = [];
  let redoStack = [];
  let loadingHistory = false;
  let dirty = false;

  function uid(prefix) {
    return `${prefix}-${Date.now()}-${Math.floor(Math.random() * 100000)}`;
  }

  function snap(value) {
    return snapToGrid && snapToGrid.checked ? Math.round(value / gridSize) * gridSize : value;
  }

  function selectedLineDefinition() {
    const selected = lineType.options[lineType.selectedIndex];
    return {
      key: lineType.value,
      label: selected.textContent,
      color: selected.dataset.color || "#2563eb"
    };
  }

  function lineStyle(key) {
    const styles = {
      cat5e: { width: 3, dash: null },
      power: { width: 4, dash: null },
      dlm: { width: 3, dash: [12, 8] },
      barrier_control: { width: 3, dash: null },
      camera_network: { width: 3, dash: [10, 6] },
      main_supply: { width: 5, dash: null },
      spare_conduit: { width: 3, dash: [8, 8] }
    };
    return styles[key] || { width: 3, dash: null };
  }

  function syncObjectGeometry(object) {
    if (!object) return;
    object.set({
      x: Math.round(object.left || 0),
      y: Math.round(object.top || 0),
      rotation: Math.round(object.angle || 0),
      scale: Number((((object.scaleX || 1) + (object.scaleY || 1)) / 2).toFixed(2))
    });
  }

  function prepareObjectsForSave() {
    canvas.getObjects().forEach(syncObjectGeometry);
  }

  function markDirty() {
    dirty = true;
    if (saveStatus) saveStatus.textContent = "Mentetlen változás.";
  }

  function pushHistory() {
    if (loadingHistory) return;
    prepareObjectsForSave();
    history.push(JSON.stringify(canvas.toJSON(customProps)));
    if (history.length > 60) history.shift();
    redoStack = [];
  }

  function restoreFromJson(json) {
    loadingHistory = true;
    canvas.loadFromJSON(JSON.parse(json), () => {
      loadBackground();
      canvas.requestRenderAll();
      loadingHistory = false;
      updateSelectedFields();
    });
  }

  function undo() {
    if (history.length < 2) return;
    const current = history.pop();
    redoStack.push(current);
    restoreFromJson(history[history.length - 1]);
    markDirty();
  }

  function redo() {
    const next = redoStack.pop();
    if (!next) return;
    history.push(next);
    restoreFromJson(next);
    markDirty();
  }

  function setObjectMeta(object, type, label) {
    object.set({
      objectId: object.objectId || uid(type),
      objectType: type,
      label: label,
      notes: object.notes || "",
      status: object.status || "planned"
    });
    syncObjectGeometry(object);
  }

  function setObjectSelectability(selectable) {
    canvas.getObjects().forEach((object) => {
      if (object !== activeLine) {
        object.selectable = selectable;
        object.evented = selectable;
      }
    });
  }

  function setMode(nextMode) {
    mode = nextMode;
    isDrawingLine = nextMode === "line";
    activeLine = null;
    canvas.discardActiveObject();
    canvas.selection = nextMode === "select";
    setObjectSelectability(nextMode === "select");
    canvas.defaultCursor = {
      select: "default",
      pan: "grab",
      line: "crosshair",
      text: "text"
    }[nextMode];
    modeIndicator.textContent = {
      select: "Select",
      pan: "Pan",
      line: "Draw cable",
      text: "Text"
    }[nextMode];
    Object.entries(modeButtons).forEach(([key, button]) => {
      button.classList.toggle("active", key === nextMode);
      button.classList.toggle("btn-purple", key === nextMode);
      button.classList.toggle("btn-outline-secondary", key !== nextMode);
    });
    canvas.requestRenderAll();
  }

  function addIcon(type, label) {
    setMode("select");
    const icon = makeIcon(type, label);
    canvas.add(icon);
    canvas.setActiveObject(icon);
    pushHistory();
    markDirty();
  }

  function makeIcon(type, label) {
    const color = iconColor(type);
    const parts = [
      new fabric.Rect({
        width: 96,
        height: 64,
        rx: 14,
        ry: 14,
        fill: color.fill,
        stroke: color.stroke,
        strokeWidth: 2,
        shadow: new fabric.Shadow({ color: "rgba(15,23,42,0.16)", blur: 10, offsetY: 4 }),
        originX: "center",
        originY: "center"
      }),
      ...symbolFor(type, color),
      new fabric.Text(label, {
        top: 46,
        fontFamily: "Arial",
        fontSize: 11,
        fontWeight: "bold",
        fill: color.text,
        textAlign: "center",
        originX: "center",
        originY: "center"
      })
    ];
    const group = new fabric.Group(parts, {
      left: 180,
      top: 140,
      objectCaching: false
    });
    setObjectMeta(group, type, label);
    return group;
  }

  function symbolFor(type, color) {
    const stroke = color.stroke;
    const fill = color.text;
    if (type.includes("charger")) {
      return [
        new fabric.Rect({ width: 28, height: 34, rx: 5, ry: 5, fill: "white", stroke, strokeWidth: 2, originX: "center", originY: "center", top: -10 }),
        new fabric.Polyline([{ x: -5, y: -18 }, { x: 3, y: -8 }, { x: -2, y: -8 }, { x: 6, y: 4 }], { stroke, strokeWidth: 3, fill: "", originX: "center", originY: "center" })
      ];
    }
    if (type.includes("camera")) {
      return [
        new fabric.Circle({ radius: 16, fill: "white", stroke, strokeWidth: 2, originX: "center", originY: "center", top: -10 }),
        new fabric.Circle({ radius: 7, fill: stroke, originX: "center", originY: "center", top: -10 }),
        new fabric.Triangle({ width: 14, height: 12, fill: stroke, angle: 90, left: 22, top: -10, originX: "center", originY: "center" })
      ];
    }
    if (type.includes("barrier")) {
      return [
        new fabric.Rect({ width: 10, height: 38, fill: stroke, originX: "center", originY: "center", left: -28, top: -4 }),
        new fabric.Rect({ width: 56, height: 8, fill: stroke, angle: -12, originX: "center", originY: "center", left: 4, top: -16 })
      ];
    }
    if (type.includes("loop")) {
      return [new fabric.Rect({ width: 52, height: 30, rx: 16, ry: 16, fill: "", stroke, strokeWidth: 4, originX: "center", originY: "center", top: -8 })];
    }
    if (type.includes("rack") || type.includes("switch") || type.includes("router") || type.includes("teltonika") || type.includes("box") || type.includes("dlm")) {
      return [
        new fabric.Rect({ width: 52, height: 32, rx: 5, ry: 5, fill: "white", stroke, strokeWidth: 2, originX: "center", originY: "center", top: -10 }),
        new fabric.Circle({ radius: 3, fill, left: -16, top: -10, originX: "center", originY: "center" }),
        new fabric.Circle({ radius: 3, fill, left: 0, top: -10, originX: "center", originY: "center" }),
        new fabric.Circle({ radius: 3, fill, left: 16, top: -10, originX: "center", originY: "center" })
      ];
    }
    if (type.includes("board") || type.includes("supply") || type.includes("breaker")) {
      return [
        new fabric.Rect({ width: 38, height: 40, rx: 4, ry: 4, fill: "white", stroke, strokeWidth: 2, originX: "center", originY: "center", top: -8 }),
        new fabric.Line([-12, -16, 12, -16], { stroke, strokeWidth: 3 }),
        new fabric.Line([-12, -6, 12, -6], { stroke, strokeWidth: 3 }),
        new fabric.Line([-12, 4, 12, 4], { stroke, strokeWidth: 3 })
      ];
    }
    if (type.includes("tray") || type.includes("busbar")) {
      return [
        new fabric.Line([-28, -18, 28, -18], { stroke, strokeWidth: 5 }),
        new fabric.Line([-28, -6, 28, -6], { stroke, strokeWidth: 5 }),
        new fabric.Line([-28, 6, 28, 6], { stroke, strokeWidth: 5 })
      ];
    }
    if (type.includes("penetration")) {
      return [
        new fabric.Circle({ radius: 18, fill: "white", stroke, strokeWidth: 3, originX: "center", originY: "center", top: -8 }),
        new fabric.Line([-16, -24, 16, 8], { stroke, strokeWidth: 3 }),
        new fabric.Line([16, -24, -16, 8], { stroke, strokeWidth: 3 })
      ];
    }
    return [
      new fabric.Circle({ radius: 18, fill: "white", stroke, strokeWidth: 2, originX: "center", originY: "center", top: -10 }),
      new fabric.Text("P", { fontFamily: "Arial", fontSize: 20, fontWeight: "bold", fill, originX: "center", originY: "center", top: -10 })
    ];
  }

  function iconColor(type) {
    if (type.includes("camera")) return { fill: "#f4eafe", stroke: "#6f42c1", text: "#3b1d73" };
    if (type.includes("charger") || type.includes("meter") || type === "ct") return { fill: "#e8f7ef", stroke: "#14a05f", text: "#064e33" };
    if (type.includes("barrier") || type.includes("parking") || type.includes("rfid") || type.includes("loop")) return { fill: "#fff7e6", stroke: "#f59e0b", text: "#7a4b00" };
    if (type.includes("rack") || type.includes("switch") || type.includes("router") || type.includes("teltonika") || type.includes("box") || type.includes("dlm")) return { fill: "#e8f1ff", stroke: "#2364d2", text: "#153e86" };
    return { fill: "#f1f5f9", stroke: "#64748b", text: "#1f2937" };
  }

  function addTextLabel(point) {
    const text = new fabric.Textbox("Új címke", {
      left: snap(point.x),
      top: snap(point.y),
      width: 180,
      fontFamily: "Arial",
      fontSize: 22,
      fill: "#162033",
      backgroundColor: "rgba(255,255,255,0.78)"
    });
    setObjectMeta(text, "text_label", "Új címke");
    canvas.add(text);
    canvas.setActiveObject(text);
    setMode("select");
    pushHistory();
    markDirty();
  }

  function updateSelectedFields() {
    const object = canvas.getActiveObject();
    if (!object) {
      objectLabel.value = "";
      objectNotes.value = "";
      objectStatus.value = "planned";
      objectType.textContent = "-";
      objectX.textContent = "-";
      objectY.textContent = "-";
      objectRotation.textContent = "-";
      objectScale.textContent = "-";
      return;
    }
    syncObjectGeometry(object);
    objectLabel.value = object.label || object.text || "";
    objectNotes.value = object.notes || "";
    objectStatus.value = object.status || "planned";
    objectType.textContent = object.objectType || object.type || "-";
    objectX.textContent = object.x;
    objectY.textContent = object.y;
    objectRotation.textContent = `${object.rotation}°`;
    objectScale.textContent = object.scale;
  }

  function applySelectedFields() {
    const object = canvas.getActiveObject();
    if (!object) return;
    object.set({
      label: objectLabel.value,
      notes: objectNotes.value,
      status: objectStatus.value
    });
    if (object.type === "textbox") object.set("text", objectLabel.value || "Címke");
    if (object.type === "group" && object._objects && object._objects[object._objects.length - 1]) {
      object._objects[object._objects.length - 1].set("text", objectLabel.value || object.label || "");
      object.addWithUpdate();
    }
    canvas.requestRenderAll();
    markDirty();
  }

  function duplicateObject() {
    const object = canvas.getActiveObject();
    if (!object) return;
    object.clone((clone) => {
      clone.set({
        left: object.left + 24,
        top: object.top + 24,
        objectId: uid(object.objectType || "object")
      });
      canvas.add(clone);
      canvas.setActiveObject(clone);
      pushHistory();
      markDirty();
    }, customProps);
  }

  function deleteObject() {
    const objects = canvas.getActiveObjects();
    if (!objects.length) return;
    objects.forEach((object) => canvas.remove(object));
    canvas.discardActiveObject();
    canvas.requestRenderAll();
    pushHistory();
    markDirty();
  }

  function beginCableLine(event) {
    const pointer = canvas.getPointer(event.e);
    const definition = selectedLineDefinition();
    const style = lineStyle(definition.key);
    activeLine = new fabric.Line(
      [snap(pointer.x), snap(pointer.y), snap(pointer.x), snap(pointer.y)],
      {
        stroke: definition.color,
        strokeWidth: style.width,
        strokeDashArray: style.dash,
        strokeLineCap: "round",
        selectable: false,
        evented: false,
        objectCaching: false
      }
    );
    setObjectMeta(activeLine, definition.key, definition.label);
    activeLine.set({ lineType: definition.key });
    canvas.add(activeLine);
  }

  function updateCableLine(event) {
    if (!activeLine) return;
    const pointer = canvas.getPointer(event.e);
    activeLine.set({ x2: snap(pointer.x), y2: snap(pointer.y) });
    canvas.requestRenderAll();
  }

  function finishCableLine() {
    if (!activeLine) return;
    activeLine.set({ selectable: true, evented: true });
    canvas.setActiveObject(activeLine);
    activeLine = null;
    setMode("select");
    pushHistory();
    markDirty();
  }

  function saveDrawing() {
    prepareObjectsForSave();
    const json = JSON.stringify(canvas.toJSON(customProps));
    fetch(config.saveUrl, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ canvas_json: json })
    })
      .then((response) => response.json())
      .then((data) => {
        if (!data.ok) throw new Error(data.error || "Mentési hiba");
        dirty = false;
        saveStatus.textContent = "Mentve.";
      })
      .catch((error) => {
        saveStatus.textContent = `Hiba: ${error.message}`;
      });
  }

  function exportPng() {
    const link = document.createElement("a");
    link.href = canvas.toDataURL({ format: "png", multiplier: 2 });
    link.download = "parkl-rajz.png";
    link.click();
  }

  function exportPdf() {
    const image = canvas.toDataURL({ format: "png", multiplier: 2 });
    const pdf = new window.jspdf.jsPDF({ orientation: "landscape", unit: "px", format: [canvas.width, canvas.height] });
    pdf.addImage(image, "PNG", 0, 0, canvas.width, canvas.height);
    pdf.save("parkl-rajz.pdf");
  }

  function setZoom(zoom) {
    zoom = Math.max(0.25, Math.min(zoom, 4));
    canvas.zoomToPoint({ x: canvas.width / 2, y: canvas.height / 2 }, zoom);
    zoomValue.textContent = `${Math.round(zoom * 100)}%`;
  }

  function fitToScreen() {
    const wrapper = document.querySelector(".drawing-canvas-wrap");
    const zoom = Math.min((wrapper.clientWidth - 40) / canvas.width, (wrapper.clientHeight || 700) / canvas.height);
    canvas.setViewportTransform([1, 0, 0, 1, 0, 0]);
    setZoom(zoom);
  }

  function loadInitialCanvas() {
    if (!config.canvasJson) {
      loadBackground();
      pushHistory();
      return;
    }
    try {
      canvas.loadFromJSON(JSON.parse(config.canvasJson), () => {
        loadBackground();
        canvas.requestRenderAll();
        pushHistory();
      });
    } catch (_error) {
      loadBackground();
      pushHistory();
    }
  }

  function loadBackground() {
    if (!config.backgroundUrl) return;
    fabric.Image.fromURL(config.backgroundUrl, (image) => {
      const scale = Math.min(canvas.width / image.width, canvas.height / image.height);
      image.set({
        originX: "left",
        originY: "top",
        left: 0,
        top: 0,
        scaleX: scale,
        scaleY: scale,
        selectable: false,
        evented: false
      });
      canvas.setBackgroundImage(image, canvas.requestRenderAll.bind(canvas));
    });
  }

  canvas.on("mouse:wheel", (event) => {
    const delta = event.e.deltaY;
    let zoom = canvas.getZoom();
    zoom *= 0.999 ** delta;
    zoom = Math.max(0.25, Math.min(zoom, 4));
    canvas.zoomToPoint({ x: event.e.offsetX, y: event.e.offsetY }, zoom);
    zoomValue.textContent = `${Math.round(zoom * 100)}%`;
    event.e.preventDefault();
    event.e.stopPropagation();
  });

  canvas.on("mouse:down", (event) => {
    if (mode === "line") {
      isDrawingLine = true;
      beginCableLine(event);
      event.e.preventDefault();
      return;
    }
    if (mode === "text") {
      addTextLabel(canvas.getPointer(event.e));
      return;
    }
    if (mode !== "pan") return;
    isPanning = true;
    canvas.selection = false;
    lastPosX = event.e.clientX;
    lastPosY = event.e.clientY;
  });

  canvas.on("mouse:move", (event) => {
    if (isDrawingLine && mode === "line") {
      updateCableLine(event);
      return;
    }
    if (!isPanning || mode !== "pan") return;
    const viewport = canvas.viewportTransform;
    viewport[4] += event.e.clientX - lastPosX;
    viewport[5] += event.e.clientY - lastPosY;
    canvas.requestRenderAll();
    lastPosX = event.e.clientX;
    lastPosY = event.e.clientY;
  });

  canvas.on("mouse:up", () => {
    if (isDrawingLine && mode === "line") {
      isDrawingLine = false;
      finishCableLine();
      return;
    }
    isPanning = false;
  });

  canvas.on("selection:created", updateSelectedFields);
  canvas.on("selection:updated", updateSelectedFields);
  canvas.on("selection:cleared", updateSelectedFields);
  canvas.on("object:modified", (event) => {
    if (event.target) {
      event.target.set({ left: snap(event.target.left), top: snap(event.target.top) });
      syncObjectGeometry(event.target);
    }
    updateSelectedFields();
    pushHistory();
    markDirty();
  });
  canvas.on("object:moving", (event) => {
    if (!event.target || !snapToGrid.checked) return;
    event.target.set({ left: snap(event.target.left), top: snap(event.target.top) });
  });

  document.querySelectorAll(".drawing-icon-button").forEach((button) => {
    button.addEventListener("click", () => addIcon(button.dataset.type, button.dataset.label));
  });
  document.querySelector("#iconSearch").addEventListener("input", (event) => {
    const term = event.target.value.trim().toLowerCase();
    document.querySelectorAll(".drawing-icon-button").forEach((button) => {
      const match = button.textContent.toLowerCase().includes(term);
      button.hidden = term && !match;
    });
  });
  document.querySelector("#duplicateObject").addEventListener("click", duplicateObject);
  document.querySelector("#deleteObject").addEventListener("click", deleteObject);
  document.querySelector("#saveDrawing").addEventListener("click", saveDrawing);
  document.querySelector("#exportPng").addEventListener("click", exportPng);
  document.querySelector("#exportPdf").addEventListener("click", exportPdf);
  document.querySelector("#undoDrawing").addEventListener("click", undo);
  document.querySelector("#redoDrawing").addEventListener("click", redo);
  document.querySelector("#zoomIn").addEventListener("click", () => setZoom(canvas.getZoom() * 1.2));
  document.querySelector("#zoomOut").addEventListener("click", () => setZoom(canvas.getZoom() / 1.2));
  document.querySelector("#fitScreen").addEventListener("click", fitToScreen);
  modeButtons.select.addEventListener("click", () => setMode("select"));
  modeButtons.pan.addEventListener("click", () => setMode("pan"));
  modeButtons.text.addEventListener("click", () => setMode("text"));
  modeButtons.line.addEventListener("click", () => setMode("line"));
  [objectLabel, objectStatus, objectNotes].forEach((input) => {
    input.addEventListener("input", applySelectedFields);
    input.addEventListener("change", applySelectedFields);
  });

  document.addEventListener("keydown", (event) => {
    if (event.target.matches("input, textarea")) return;
    if (event.key === "Delete" || event.key === "Backspace") deleteObject();
    if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === "d") {
      event.preventDefault();
      duplicateObject();
    }
    if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === "s") {
      event.preventDefault();
      saveDrawing();
    }
    if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === "z") {
      event.preventDefault();
      event.shiftKey ? redo() : undo();
    }
  });

  window.addEventListener("beforeunload", (event) => {
    if (!dirty) return;
    event.preventDefault();
    event.returnValue = "";
  });

  setMode("select");
  loadInitialCanvas();
})();
