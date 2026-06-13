(function () {
  const config = window.ParklDrawing || {};
  document.body.classList.add("drawing-editor-active");

  const canvas = new fabric.Canvas("drawingCanvas", {
    preserveObjectStacking: true,
    selection: true,
    fireRightClick: true,
    stopContextMenu: true
  });
  fabric.Object.prototype.cornerColor = "#7047eb";
  fabric.Object.prototype.cornerStrokeColor = "#ffffff";
  fabric.Object.prototype.borderColor = "#7047eb";
  fabric.Object.prototype.cornerSize = 11;
  fabric.Object.prototype.cornerStyle = "circle";
  fabric.Object.prototype.transparentCorners = false;
  fabric.Object.prototype.borderScaleFactor = 1.5;

  const customProps = [
    "objectId", "objectType", "label", "identifier", "notes", "status",
    "lineType", "sourceObjectId", "targetObjectId", "arrowEnd",
    "locked", "hidden", "accentColor", "erpKind", "erpDeviceId",
    "erpUnitId", "erpBalanceId", "erpCode", "erpName", "projectId",
    "x", "y", "rotation", "scale"
  ];
  const $ = (selector) => document.querySelector(selector);
  const $$ = (selector) => Array.from(document.querySelectorAll(selector));
  const controls = {
    saveStatus: $("#saveStatus"),
    zoomValue: $("#zoomValue"),
    modeIndicator: $("#modeIndicator"),
    snap: $("#snapToGrid"),
    showGrid: $("#showGrid"),
    gridSize: $("#gridSize"),
    lineType: $("#lineType"),
    workspace: $(".drawing-workspace"),
    rightPanel: $("#drawingRightPanel"),
    objectLabel: $("#objectLabel"),
    objectIdentifier: $("#objectIdentifier"),
    objectStatus: $("#objectStatus"),
    objectNotes: $("#objectNotes"),
    objectColor: $("#objectColor"),
    objectSize: $("#objectSize"),
    objectScale: $("#objectScale"),
    objectX: $("#objectX"),
    objectY: $("#objectY"),
    objectRotation: $("#objectRotation"),
    erpData: $("#erpObjectData"),
    erpName: $("#erpObjectName"),
    erpId: $("#erpObjectId"),
    layerList: $("#layerList"),
    layerCount: $("#layerCount"),
    objectCount: $("#objectCount"),
    backgroundOpacity: $("#backgroundOpacity"),
    backgroundOpacityValue: $("#backgroundOpacityValue"),
    backgroundLocked: $("#backgroundLocked"),
    contextMenu: $("#drawingContextMenu"),
    dropZone: $("#drawingDropZone")
  };
  const modeButtons = {
    select: $("#selectMode"),
    pan: $("#panMode"),
    connector: $("#lineMode"),
    text: $("#textMode")
  };

  let mode = "select";
  let isPanning = false;
  let spacePressed = false;
  let lastPosX = 0;
  let lastPosY = 0;
  let connectorSource = null;
  let connectorPreview = null;
  let history = [];
  let redoStack = [];
  let loadingHistory = false;
  let dirty = false;
  let settings = {
    gridSize: 20,
    showGrid: true,
    snapToGrid: true,
    backgroundOpacity: 1,
    backgroundLocked: true
  };

  function uid(prefix) {
    return `${prefix}-${Date.now()}-${Math.floor(Math.random() * 100000)}`;
  }

  function gridSize() {
    return Math.max(5, Math.min(100, Number(controls.gridSize.value) || 20));
  }

  function snap(value) {
    return controls.snap.checked ? Math.round(value / gridSize()) * gridSize() : value;
  }

  function selectedLineDefinition() {
    const option = controls.lineType.options[controls.lineType.selectedIndex];
    return {
      key: controls.lineType.value,
      label: option.textContent,
      color: option.dataset.color || "#2563eb"
    };
  }

  function lineStyle(key) {
    return {
      cat5e: { width: 2, dash: null },
      power: { width: 3, dash: null },
      dlm: { width: 2, dash: [10, 7] },
      barrier_control: { width: 2, dash: null },
      camera_network: { width: 2, dash: [8, 5] },
      main_supply: { width: 4, dash: null },
      spare_conduit: { width: 2, dash: [7, 7] }
    }[key] || { width: 2, dash: null };
  }

  function syncObjectGeometry(object) {
    if (!object || object.objectType === "connector") return;
    object.set({
      x: Math.round(object.left || 0),
      y: Math.round(object.top || 0),
      rotation: Math.round(object.angle || 0),
      scale: Number((((object.scaleX || 1) + (object.scaleY || 1)) / 2).toFixed(2))
    });
  }

  function objectCenter(object) {
    const center = object.getCenterPoint();
    return { x: center.x, y: center.y };
  }

  function setObjectMeta(object, type, label, extra) {
    object.set(Object.assign({
      objectId: object.objectId || uid(type),
      objectType: type,
      label: label || type,
      identifier: object.identifier || "",
      notes: object.notes || "",
      status: object.status || "planned",
      locked: Boolean(object.locked),
      hidden: Boolean(object.hidden),
      accentColor: object.accentColor || iconColor(type).stroke,
      projectId: config.project ? config.project.id : null
    }, extra || {}));
    syncObjectGeometry(object);
  }

  function serializeCanvas() {
    canvas.getObjects().forEach(syncObjectGeometry);
    const data = canvas.toJSON(customProps);
    settings = readSettings();
    data.parklSettings = settings;
    return JSON.stringify(data);
  }

  function markDirty() {
    dirty = true;
    controls.saveStatus.textContent = "Mentetlen változás";
    controls.saveStatus.classList.add("is-dirty");
  }

  function pushHistory() {
    if (loadingHistory) return;
    history.push(serializeCanvas());
    if (history.length > 60) history.shift();
    redoStack = [];
    refreshLayers();
  }

  function restoreFromJson(json) {
    loadingHistory = true;
    const parsed = JSON.parse(json);
    applySettings(parsed.parklSettings || settings);
    canvas.loadFromJSON(parsed, () => {
      normalizeLoadedObjects();
      loadBackground();
      updateAllConnectors();
      canvas.requestRenderAll();
      loadingHistory = false;
      updateSelectionPanel();
      refreshLayers();
    });
  }

  function undo() {
    if (history.length < 2) return;
    redoStack.push(history.pop());
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

  function normalizeLoadedObjects() {
    canvas.getObjects().forEach((object) => {
      object.objectId = object.objectId || uid(object.objectType || object.type);
      object.visible = object.hidden !== true;
      applyLockedState(object, object.locked === true);
    });
  }

  function setMode(nextMode) {
    mode = nextMode;
    cancelConnector();
    canvas.discardActiveObject();
    canvas.selection = nextMode === "select";
    canvas.defaultCursor = {
      select: "default",
      pan: "grab",
      connector: "crosshair",
      text: "text"
    }[nextMode];
    canvas.getObjects().forEach((object) => {
      const selectable = nextMode === "select" && !object.locked;
      object.selectable = selectable;
      object.evented = nextMode === "connector" || selectable;
    });
    controls.modeIndicator.textContent = {
      select: "Kijelölés",
      pan: "Vászon mozgatása",
      connector: "Kapcsolat: válassz két eszközt",
      text: "Szöveg elhelyezése"
    }[nextMode];
    Object.entries(modeButtons).forEach(([key, button]) => {
      button.classList.toggle("active", key === nextMode);
    });
    canvas.requestRenderAll();
  }

  function addIcon(type, label, point, metadata) {
    const icon = makeIcon(type, label, point, metadata);
    setMode("select");
    canvas.add(icon);
    canvas.setActiveObject(icon);
    updateSelectionPanel();
    pushHistory();
    markDirty();
    return icon;
  }

  function makeIcon(type, label, point, metadata) {
    const color = iconColor(type, metadata && metadata.category);
    const parts = [
      new fabric.Rect({
        width: 92, height: 66, rx: 12, ry: 12,
        fill: color.fill, stroke: color.stroke, strokeWidth: 2,
        shadow: new fabric.Shadow({ color: "rgba(29,20,56,.16)", blur: 9, offsetY: 3 }),
        originX: "center", originY: "center"
      }),
      ...symbolFor(type, color),
      new fabric.Text(shortLabel(label), {
        top: 47, fontFamily: "Arial", fontSize: 10, fontWeight: "bold",
        fill: color.text, textAlign: "center", originX: "center", originY: "center"
      })
    ];
    const group = new fabric.Group(parts, {
      left: snap(point ? point.x : 220),
      top: snap(point ? point.y : 160),
      objectCaching: false
    });
    setObjectMeta(group, type, label, Object.assign({
      accentColor: color.stroke
    }, metadata || {}));
    return group;
  }

  function shortLabel(value) {
    const text = String(value || "");
    return text.length > 18 ? `${text.slice(0, 16)}…` : text;
  }

  function symbolFor(type, color) {
    const stroke = color.stroke;
    const fill = color.text;
    if (type.includes("charger")) {
      return [
        new fabric.Rect({ width: 27, height: 35, rx: 5, ry: 5, fill: "#fff", stroke, strokeWidth: 2, originX: "center", originY: "center", top: -9 }),
        new fabric.Polyline([{ x: -5, y: -19 }, { x: 3, y: -9 }, { x: -2, y: -9 }, { x: 6, y: 3 }], { stroke, strokeWidth: 3, fill: "", originX: "center", originY: "center" })
      ];
    }
    if (type.includes("camera")) {
      return [
        new fabric.Rect({ width: 38, height: 20, rx: 5, ry: 5, fill: "#fff", stroke, strokeWidth: 2, originX: "center", originY: "center", top: -10 }),
        new fabric.Circle({ radius: 6, fill: stroke, left: 11, top: -10, originX: "center", originY: "center" }),
        new fabric.Line([-15, 1, -23, 12], { stroke, strokeWidth: 3 })
      ];
    }
    if (type.includes("barrier")) {
      return [
        new fabric.Rect({ width: 9, height: 37, rx: 3, ry: 3, fill: stroke, originX: "center", originY: "center", left: -28, top: -3 }),
        new fabric.Rect({ width: 58, height: 7, rx: 3, ry: 3, fill: stroke, angle: -10, originX: "center", originY: "center", left: 4, top: -17 })
      ];
    }
    if (type.includes("loop")) {
      return [new fabric.Rect({ width: 50, height: 28, rx: 14, ry: 14, fill: "", stroke, strokeWidth: 4, originX: "center", originY: "center", top: -8 })];
    }
    if (["rack", "switch", "router", "teltonika", "box", "dlm", "erp_device"].some((key) => type.includes(key))) {
      return [
        new fabric.Rect({ width: 50, height: 31, rx: 5, ry: 5, fill: "#fff", stroke, strokeWidth: 2, originX: "center", originY: "center", top: -10 }),
        new fabric.Circle({ radius: 3, fill, left: -15, top: -10, originX: "center", originY: "center" }),
        new fabric.Circle({ radius: 3, fill, left: 0, top: -10, originX: "center", originY: "center" }),
        new fabric.Circle({ radius: 3, fill, left: 15, top: -10, originX: "center", originY: "center" })
      ];
    }
    if (type.includes("board") || type.includes("supply") || type.includes("breaker")) {
      return [
        new fabric.Rect({ width: 38, height: 39, rx: 4, ry: 4, fill: "#fff", stroke, strokeWidth: 2, originX: "center", originY: "center", top: -8 }),
        new fabric.Line([-12, -16, 12, -16], { stroke, strokeWidth: 3 }),
        new fabric.Line([-12, -6, 12, -6], { stroke, strokeWidth: 3 }),
        new fabric.Line([-12, 4, 12, 4], { stroke, strokeWidth: 3 })
      ];
    }
    if (type.includes("tray") || type.includes("busbar")) {
      return [-18, -7, 4].map((top) => new fabric.Line([-27, top, 27, top], { stroke, strokeWidth: 4 }));
    }
    if (type.includes("penetration")) {
      return [
        new fabric.Circle({ radius: 18, fill: "#fff", stroke, strokeWidth: 3, originX: "center", originY: "center", top: -8 }),
        new fabric.Line([-15, -23, 15, 7], { stroke, strokeWidth: 3 }),
        new fabric.Line([15, -23, -15, 7], { stroke, strokeWidth: 3 })
      ];
    }
    return [
      new fabric.Circle({ radius: 18, fill: "#fff", stroke, strokeWidth: 2, originX: "center", originY: "center", top: -10 }),
      new fabric.Text("P", { fontFamily: "Arial", fontSize: 19, fontWeight: "bold", fill, originX: "center", originY: "center", top: -10 })
    ];
  }

  function iconColor(type, category) {
    const subject = `${type} ${category || ""}`.toLowerCase();
    if (subject.includes("camera")) return { fill: "#f3eefe", stroke: "#7047eb", text: "#38206f" };
    if (subject.includes("charger") || subject.includes("töltő") || subject.includes("meter") || subject.includes("ct")) return { fill: "#e8f8ef", stroke: "#159b5c", text: "#075237" };
    if (subject.includes("barrier") || subject.includes("sorompó") || subject.includes("parking") || subject.includes("rfid") || subject.includes("loop")) return { fill: "#fff5df", stroke: "#e79208", text: "#704500" };
    if (subject.includes("rack") || subject.includes("switch") || subject.includes("router") || subject.includes("teltonika") || subject.includes("box") || subject.includes("dlm") || type === "erp_device") return { fill: "#eaf1ff", stroke: "#3167ce", text: "#163e83" };
    return { fill: "#f1f4f8", stroke: "#64748b", text: "#263548" };
  }

  function addTextLabel(point) {
    const text = new fabric.Textbox("Új címke", {
      left: snap(point.x), top: snap(point.y), width: 180,
      fontFamily: "Arial", fontSize: 22, fill: "#172033",
      backgroundColor: "rgba(255,255,255,.82)"
    });
    setObjectMeta(text, "text_label", "Új címke");
    setMode("select");
    canvas.add(text);
    canvas.setActiveObject(text);
    updateSelectionPanel();
    pushHistory();
    markDirty();
  }

  function connectorPoints(source, target) {
    const a = objectCenter(source);
    const b = objectCenter(target);
    const middleX = a.x + ((b.x - a.x) / 2);
    return [
      { x: a.x, y: a.y },
      { x: middleX, y: a.y },
      { x: middleX, y: b.y },
      { x: b.x, y: b.y }
    ];
  }

  function createConnector(source, target) {
    const definition = selectedLineDefinition();
    const style = lineStyle(definition.key);
    const path = connectorPath(connectorPoints(source, target));
    path.set({
      stroke: definition.color,
      strokeWidth: style.width,
      strokeDashArray: style.dash,
      fill: "",
      selectable: true,
      evented: true,
      perPixelTargetFind: true,
      objectCaching: false
    });
    setObjectMeta(path, "connector", definition.label, {
      lineType: definition.key,
      sourceObjectId: source.objectId,
      targetObjectId: target.objectId,
      arrowEnd: true,
      accentColor: definition.color
    });
    canvas.add(path);
    canvas.sendToBack(path);
    canvas.setActiveObject(path);
    pushHistory();
    markDirty();
    return path;
  }

  function connectorPath(points) {
    return new fabric.Path(
      `M ${points[0].x} ${points[0].y} L ${points[1].x} ${points[1].y} L ${points[2].x} ${points[2].y} L ${points[3].x} ${points[3].y}`,
      { fill: "", objectCaching: false }
    );
  }

  function updateConnector(connector) {
    const source = findObject(connector.sourceObjectId);
    const target = findObject(connector.targetObjectId);
    if (!source || !target) return;
    const replacement = connectorPath(connectorPoints(source, target));
    connector.set({
      path: replacement.path,
      pathOffset: replacement.pathOffset,
      left: replacement.left,
      top: replacement.top,
      width: replacement.width,
      height: replacement.height,
      dirty: true
    });
    connector.setCoords();
  }

  function updateAllConnectors(objectId) {
    canvas.getObjects().forEach((object) => {
      if (object.objectType !== "connector") return;
      if (!objectId || object.sourceObjectId === objectId || object.targetObjectId === objectId) {
        updateConnector(object);
      }
    });
    canvas.requestRenderAll();
  }

  function findObject(objectId) {
    return canvas.getObjects().find((object) => object.objectId === objectId);
  }

  function startConnector(target) {
    if (!target || target.objectType === "connector") return;
    if (!connectorSource) {
      connectorSource = target;
      controls.modeIndicator.textContent = "Kapcsolat: válaszd ki a céleszközt";
      canvas.requestRenderAll();
      return;
    }
    if (connectorSource !== target) createConnector(connectorSource, target);
    connectorSource = null;
    setMode("select");
  }

  function cancelConnector() {
    connectorSource = null;
    if (connectorPreview) {
      canvas.remove(connectorPreview);
      connectorPreview = null;
    }
  }

  function drawConnectorDecorations(context) {
    canvas.getObjects().filter((object) => object.objectType === "connector" && object.visible !== false).forEach((connector) => {
      const source = findObject(connector.sourceObjectId);
      const target = findObject(connector.targetObjectId);
      if (!source || !target) return;
      const points = connectorPoints(source, target).map((point) => (
        fabric.util.transformPoint(new fabric.Point(point.x, point.y), canvas.viewportTransform)
      ));
      const endpoint = points[points.length - 1];
      const previous = points[points.length - 2];
      const angle = Math.atan2(endpoint.y - previous.y, endpoint.x - previous.x);
      const size = 8;

      if (connector.arrowEnd !== false) {
        context.save();
        context.translate(endpoint.x, endpoint.y);
        context.rotate(angle);
        context.beginPath();
        context.moveTo(0, 0);
        context.lineTo(-size, size * 0.55);
        context.lineTo(-size, -size * 0.55);
        context.closePath();
        context.fillStyle = connector.stroke || connector.accentColor || "#7047eb";
        context.fill();
        context.restore();
      }

      if (connector.label) {
        const middle = points[1];
        context.save();
        context.font = "600 11px Arial";
        const width = context.measureText(connector.label).width;
        context.fillStyle = "rgba(255,255,255,.94)";
        context.fillRect(middle.x - 4, middle.y - 17, width + 8, 17);
        context.fillStyle = "#4b4657";
        context.fillText(connector.label, middle.x, middle.y - 5);
        context.restore();
      }
    });
  }

  function updateSelectionPanel() {
    const object = canvas.getActiveObject();
    const hasObject = object && object.type !== "activeSelection";
    controls.rightPanel.classList.toggle("is-empty", !hasObject);
    controls.workspace.classList.toggle("has-selection", Boolean(hasObject));
    if (!hasObject) return;
    syncObjectGeometry(object);
    controls.objectLabel.value = object.label || object.text || "";
    controls.objectIdentifier.value = object.identifier || object.erpCode || "";
    controls.objectStatus.value = object.status || "planned";
    controls.objectNotes.value = object.notes || "";
    controls.objectColor.value = normalizeHex(object.accentColor || object.stroke || "#7047eb");
    controls.objectSize.value = Math.round((((object.scaleX || 1) + (object.scaleY || 1)) / 2) * 100);
    controls.objectScale.textContent = `${controls.objectSize.value}%`;
    controls.objectX.textContent = Math.round(object.left || 0);
    controls.objectY.textContent = Math.round(object.top || 0);
    controls.objectRotation.textContent = Math.round(object.angle || 0);
    const isErp = Boolean(object.erpDeviceId);
    controls.erpData.hidden = !isErp;
    controls.erpName.textContent = object.erpName || "-";
    controls.erpId.textContent = object.erpUnitId || object.erpBalanceId || object.erpDeviceId || "-";
  }

  function applySelectedFields() {
    const object = canvas.getActiveObject();
    if (!object || object.type === "activeSelection") return;
    object.set({
      label: controls.objectLabel.value,
      identifier: controls.objectIdentifier.value,
      notes: controls.objectNotes.value,
      status: controls.objectStatus.value,
      accentColor: controls.objectColor.value
    });
    if (object.type === "textbox") object.set("text", controls.objectLabel.value || "Címke");
    if (object.type === "group" && object._objects) {
      const label = object._objects[object._objects.length - 1];
      if (label && label.type === "text") label.set("text", shortLabel(controls.objectLabel.value));
      const background = object._objects[0];
      if (background) background.set("stroke", controls.objectColor.value);
      object.addWithUpdate();
    }
    if (object.objectType === "connector") object.set("stroke", controls.objectColor.value);
    canvas.requestRenderAll();
    refreshLayers();
    markDirty();
  }

  function applyObjectSize() {
    const object = canvas.getActiveObject();
    if (!object) return;
    const scale = Number(controls.objectSize.value) / 100;
    object.scale(scale);
    object.setCoords();
    controls.objectScale.textContent = `${controls.objectSize.value}%`;
    updateAllConnectors(object.objectId);
    markDirty();
  }

  function duplicateObject() {
    const object = canvas.getActiveObject();
    if (!object || object.objectType === "connector") return;
    object.clone((clone) => {
      clone.set({ left: object.left + 24, top: object.top + 24, objectId: uid(object.objectType || "object") });
      canvas.add(clone);
      canvas.setActiveObject(clone);
      pushHistory();
      markDirty();
    }, customProps);
  }

  function deleteObject() {
    const objects = canvas.getActiveObjects();
    if (!objects.length) return;
    const ids = objects.map((object) => object.objectId);
    canvas.getObjects().slice().forEach((object) => {
      if (objects.includes(object) || ids.includes(object.sourceObjectId) || ids.includes(object.targetObjectId)) {
        canvas.remove(object);
      }
    });
    canvas.discardActiveObject();
    canvas.requestRenderAll();
    pushHistory();
    markDirty();
    updateSelectionPanel();
  }

  function applyLockedState(object, locked) {
    object.locked = locked;
    object.lockMovementX = locked;
    object.lockMovementY = locked;
    object.lockRotation = locked;
    object.lockScalingX = locked;
    object.lockScalingY = locked;
    object.selectable = mode === "select" && !locked;
  }

  function refreshLayers() {
    const objects = canvas.getObjects().filter((object) => object.objectType !== "connector").slice().reverse();
    controls.layerCount.textContent = objects.length;
    controls.objectCount.textContent = `${canvas.getObjects().length} objektum`;
    controls.layerList.innerHTML = "";
    objects.forEach((object) => {
      const row = document.createElement("div");
      row.className = "drawing-layer-row";
      if (canvas.getActiveObject() === object) row.classList.add("active");
      row.innerHTML = `
        <button class="layer-name" type="button"><i class="bi bi-${object.objectType === "text_label" ? "fonts" : "bounding-box"}"></i><span>${escapeHtml(object.label || object.objectType || "Objektum")}</span></button>
        <button class="layer-action" type="button" data-layer-action="visible" title="Megjelenítés"><i class="bi bi-${object.visible === false ? "eye-slash" : "eye"}"></i></button>
        <button class="layer-action" type="button" data-layer-action="lock" title="Zárolás"><i class="bi bi-${object.locked ? "lock-fill" : "unlock"}"></i></button>`;
      row.querySelector(".layer-name").addEventListener("click", () => {
        if (object.visible === false) return;
        canvas.setActiveObject(object);
        canvas.requestRenderAll();
        updateSelectionPanel();
      });
      row.querySelector('[data-layer-action="visible"]').addEventListener("click", () => {
        object.visible = object.visible === false;
        object.hidden = !object.visible;
        canvas.requestRenderAll();
        refreshLayers();
        markDirty();
      });
      row.querySelector('[data-layer-action="lock"]').addEventListener("click", () => {
        applyLockedState(object, !object.locked);
        canvas.discardActiveObject();
        canvas.requestRenderAll();
        refreshLayers();
        markDirty();
      });
      controls.layerList.appendChild(row);
    });
  }

  function readSettings() {
    return {
      gridSize: gridSize(),
      showGrid: controls.showGrid.checked,
      snapToGrid: controls.snap.checked,
      backgroundOpacity: Number(controls.backgroundOpacity.value) / 100,
      backgroundLocked: controls.backgroundLocked.checked
    };
  }

  function applySettings(next) {
    settings = Object.assign(settings, next || {});
    controls.gridSize.value = settings.gridSize || 20;
    controls.showGrid.checked = settings.showGrid !== false;
    controls.snap.checked = settings.snapToGrid !== false;
    controls.backgroundOpacity.value = Math.round((settings.backgroundOpacity == null ? 1 : settings.backgroundOpacity) * 100);
    controls.backgroundOpacityValue.textContent = `${controls.backgroundOpacity.value}%`;
    controls.backgroundLocked.checked = settings.backgroundLocked !== false;
    updateGrid();
  }

  function updateGrid() {
    const size = gridSize();
    controls.dropZone.style.setProperty("--drawing-grid-size", `${size}px`);
    controls.dropZone.classList.toggle("grid-hidden", !controls.showGrid.checked);
  }

  function saveDrawing() {
    fetch(config.saveUrl, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ canvas_json: serializeCanvas() })
    })
      .then((response) => response.json())
      .then((data) => {
        if (!data.ok) throw new Error(data.error || "Mentési hiba");
        dirty = false;
        controls.saveStatus.textContent = "Mentve";
        controls.saveStatus.classList.remove("is-dirty");
      })
      .catch((error) => {
        controls.saveStatus.textContent = `Hiba: ${error.message}`;
      });
  }

  function exportPng() {
    const link = document.createElement("a");
    link.href = canvas.toDataURL({ format: "png", multiplier: 2 });
    link.download = "parkl-helyszini-rajz.png";
    link.click();
  }

  function exportPdf() {
    const image = canvas.toDataURL({ format: "png", multiplier: 2 });
    const pdf = new window.jspdf.jsPDF({ orientation: "landscape", unit: "px", format: [canvas.width, canvas.height] });
    pdf.addImage(image, "PNG", 0, 0, canvas.width, canvas.height);
    pdf.save("parkl-helyszini-rajz.pdf");
  }

  function exportSvg() {
    const blob = new Blob([canvas.toSVG()], { type: "image/svg+xml;charset=utf-8" });
    const link = document.createElement("a");
    link.href = URL.createObjectURL(blob);
    link.download = "parkl-helyszini-rajz.svg";
    link.click();
    URL.revokeObjectURL(link.href);
  }

  function setZoom(zoom) {
    const next = Math.max(0.2, Math.min(zoom, 4));
    canvas.zoomToPoint({ x: canvas.width / 2, y: canvas.height / 2 }, next);
    controls.zoomValue.textContent = `${Math.round(next * 100)}%`;
  }

  function fitToScreen() {
    const width = controls.dropZone.clientWidth - 48;
    const height = controls.dropZone.clientHeight - 48;
    const zoom = Math.min(width / canvas.width, height / canvas.height);
    canvas.setViewportTransform([1, 0, 0, 1, 0, 0]);
    setZoom(zoom);
  }

  function loadInitialCanvas() {
    let parsed = null;
    try {
      parsed = config.canvasJson ? JSON.parse(config.canvasJson) : null;
    } catch (_error) {
      parsed = null;
    }
    applySettings(parsed && parsed.parklSettings);
    if (!parsed) {
      loadBackground();
      pushHistory();
      window.setTimeout(fitToScreen, 100);
      return;
    }
    canvas.loadFromJSON(parsed, () => {
      normalizeLoadedObjects();
      loadBackground();
      updateAllConnectors();
      canvas.requestRenderAll();
      pushHistory();
      refreshLayers();
      window.setTimeout(fitToScreen, 100);
    });
  }

  function loadBackground() {
    if (!config.backgroundUrl) return;
    if (config.backgroundIsPdf && window.pdfjsLib) {
      window.pdfjsLib.GlobalWorkerOptions.workerSrc = "https://cdn.jsdelivr.net/npm/pdfjs-dist@3.11.174/build/pdf.worker.min.js";
      window.pdfjsLib.getDocument(config.backgroundUrl).promise
        .then((pdf) => pdf.getPage(1))
        .then((page) => {
          const viewport = page.getViewport({ scale: 2 });
          const source = document.createElement("canvas");
          source.width = viewport.width;
          source.height = viewport.height;
          return page.render({ canvasContext: source.getContext("2d"), viewport }).promise.then(() => source);
        })
        .then((source) => fabric.Image.fromURL(source.toDataURL("image/png"), applyBackgroundImage));
      return;
    }
    fabric.Image.fromURL(config.backgroundUrl, applyBackgroundImage);
  }

  function applyBackgroundImage(image) {
    const scale = Math.min(canvas.width / image.width, canvas.height / image.height);
    image.set({
      originX: "left", originY: "top", left: 0, top: 0,
      scaleX: scale, scaleY: scale,
      opacity: Number(controls.backgroundOpacity.value) / 100,
      selectable: false, evented: false
    });
    canvas.setBackgroundImage(image, canvas.requestRenderAll.bind(canvas));
  }

  function updateBackground() {
    settings = readSettings();
    controls.backgroundOpacityValue.textContent = `${controls.backgroundOpacity.value}%`;
    if (canvas.backgroundImage) {
      canvas.backgroundImage.set("opacity", Number(controls.backgroundOpacity.value) / 100);
      canvas.requestRenderAll();
    }
    markDirty();
  }

  function paletteIconSvg(type) {
    const common = 'viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"';
    let path = '<rect x="5" y="4" width="14" height="16" rx="3"/><path d="M9 9h6M9 13h6"/>';
    if (type.includes("charger")) path = '<rect x="6" y="3" width="10" height="18" rx="2"/><path d="m11 7-2 5h3l-2 5M16 8h2v8a2 2 0 0 0 2 2"/>';
    else if (type.includes("camera")) path = '<path d="M4 8h11a3 3 0 0 1 3 3v3H7a3 3 0 0 1-3-3z"/><circle cx="14" cy="11" r="2"/><path d="m8 14-2 5M18 11l3-2v6l-3-1"/>';
    else if (type.includes("barrier")) path = '<path d="M5 21V9h4v12M7 9V5"/><path d="m7 5 14 5"/><path d="M12 7v3M17 9v3"/>';
    else if (type.includes("switch") || type.includes("router") || type.includes("teltonika")) path = '<rect x="3" y="7" width="18" height="10" rx="2"/><circle cx="7" cy="12" r="1"/><circle cx="11" cy="12" r="1"/><path d="M15 11h3M15 14h3"/>';
    else if (type.includes("parking")) path = '<rect x="5" y="3" width="14" height="18" rx="3"/><path d="M10 17V7h3a3 3 0 0 1 0 6h-3"/>';
    else if (type.includes("arrow")) path = '<path d="M5 12h14M14 7l5 5-5 5"/>';
    return `<svg ${common}>${path}</svg>`;
  }

  function escapeHtml(value) {
    const div = document.createElement("div");
    div.textContent = value;
    return div.innerHTML;
  }

  function normalizeHex(value) {
    return /^#[0-9a-f]{6}$/i.test(value || "") ? value : "#7047eb";
  }

  function showContextMenu(event, target) {
    if (!target) return;
    canvas.setActiveObject(target);
    updateSelectionPanel();
    controls.contextMenu.style.left = `${event.e.clientX}px`;
    controls.contextMenu.style.top = `${event.e.clientY}px`;
    controls.contextMenu.classList.add("show");
  }

  function hideContextMenu() {
    controls.contextMenu.classList.remove("show");
  }

  canvas.on("mouse:wheel", (event) => {
    const zoom = Math.max(0.2, Math.min(canvas.getZoom() * (0.999 ** event.e.deltaY), 4));
    canvas.zoomToPoint({ x: event.e.offsetX, y: event.e.offsetY }, zoom);
    controls.zoomValue.textContent = `${Math.round(zoom * 100)}%`;
    event.e.preventDefault();
    event.e.stopPropagation();
  });

  canvas.on("mouse:down", (event) => {
    hideContextMenu();
    if (event.button === 3) {
      showContextMenu(event, event.target);
      return;
    }
    if (mode === "connector") {
      startConnector(event.target);
      return;
    }
    if (mode === "text") {
      addTextLabel(canvas.getPointer(event.e));
      return;
    }
    if (mode !== "pan" && !spacePressed) return;
    isPanning = true;
    canvas.selection = false;
    canvas.defaultCursor = "grabbing";
    lastPosX = event.e.clientX;
    lastPosY = event.e.clientY;
  });

  canvas.on("mouse:move", (event) => {
    if (!isPanning) return;
    const viewport = canvas.viewportTransform;
    viewport[4] += event.e.clientX - lastPosX;
    viewport[5] += event.e.clientY - lastPosY;
    lastPosX = event.e.clientX;
    lastPosY = event.e.clientY;
    canvas.requestRenderAll();
  });

  canvas.on("mouse:up", () => {
    isPanning = false;
    canvas.defaultCursor = mode === "pan" ? "grab" : "default";
  });

  canvas.on("after:render", () => {
    const context = canvas.getContext();
    drawConnectorDecorations(context);
    if (mode !== "connector") return;
    canvas.getObjects().filter((object) => object.objectType !== "connector" && object.visible !== false).forEach((object) => {
      const point = fabric.util.transformPoint(objectCenter(object), canvas.viewportTransform);
      context.save();
      context.beginPath();
      context.arc(point.x, point.y, connectorSource === object ? 7 : 5, 0, Math.PI * 2);
      context.fillStyle = connectorSource === object ? "#7047eb" : "#ffffff";
      context.strokeStyle = "#7047eb";
      context.lineWidth = 2;
      context.fill();
      context.stroke();
      context.restore();
    });
  });

  canvas.on("selection:created", () => { updateSelectionPanel(); refreshLayers(); });
  canvas.on("selection:updated", () => { updateSelectionPanel(); refreshLayers(); });
  canvas.on("selection:cleared", () => { updateSelectionPanel(); refreshLayers(); });
  canvas.on("object:moving", (event) => {
    if (!event.target) return;
    if (controls.snap.checked) event.target.set({ left: snap(event.target.left), top: snap(event.target.top) });
    updateAllConnectors(event.target.objectId);
  });
  canvas.on("object:scaling", (event) => updateAllConnectors(event.target && event.target.objectId));
  canvas.on("object:rotating", (event) => updateAllConnectors(event.target && event.target.objectId));
  canvas.on("object:modified", (event) => {
    if (event.target) syncObjectGeometry(event.target);
    updateAllConnectors(event.target && event.target.objectId);
    updateSelectionPanel();
    pushHistory();
    markDirty();
  });

  $$(".drawing-icon-button, .drawing-erp-item").forEach((button) => {
    const icon = button.querySelector(".mini-icon");
    if (icon) icon.innerHTML = paletteIconSvg(button.dataset.type);
    button.addEventListener("click", () => {
      const point = canvas.getVpCenter();
      const placedCount = canvas.getObjects().filter((object) => object.objectType !== "connector").length;
      point.x += ((placedCount % 3) - 1) * 160;
      point.y += (Math.floor(placedCount / 3) % 3) * 120;
      addIcon(button.dataset.type, button.dataset.label, point, metadataFromButton(button));
    });
    button.addEventListener("dragstart", (event) => {
      event.dataTransfer.setData("application/x-parkl-drawing", JSON.stringify({
        type: button.dataset.type,
        label: button.dataset.label,
        metadata: metadataFromButton(button)
      }));
      event.dataTransfer.effectAllowed = "copy";
    });
  });

  function metadataFromButton(button) {
    const sourceStatus = (button.dataset.status || "").toUpperCase();
    return {
      erpKind: button.dataset.erpKind || null,
      erpDeviceId: button.dataset.deviceId || null,
      erpUnitId: button.dataset.unitId || null,
      erpBalanceId: button.dataset.balanceId || null,
      erpCode: button.dataset.erpCode || null,
      erpName: button.dataset.label || null,
      identifier: button.dataset.erpCode || "",
      status: sourceStatus === "INSTALLED" ? "installed" : "planned"
    };
  }

  controls.dropZone.addEventListener("dragover", (event) => {
    event.preventDefault();
    controls.dropZone.classList.add("is-dragover");
  });
  controls.dropZone.addEventListener("dragleave", () => controls.dropZone.classList.remove("is-dragover"));
  controls.dropZone.addEventListener("drop", (event) => {
    event.preventDefault();
    controls.dropZone.classList.remove("is-dragover");
    try {
      const data = JSON.parse(event.dataTransfer.getData("application/x-parkl-drawing"));
      const rect = canvas.upperCanvasEl.getBoundingClientRect();
      const screenPoint = new fabric.Point(event.clientX - rect.left, event.clientY - rect.top);
      const point = fabric.util.transformPoint(
        screenPoint,
        fabric.util.invertTransform(canvas.viewportTransform)
      );
      addIcon(data.type, data.label, point, data.metadata);
    } catch (_error) {
      // Ignore foreign drag payloads.
    }
  });

  $("#iconSearch").addEventListener("input", (event) => {
    const term = event.target.value.trim().toLowerCase();
    $$(".drawing-icon-button, .drawing-erp-item").forEach((button) => {
      button.hidden = Boolean(term && !button.textContent.toLowerCase().includes(term));
    });
  });

  [controls.objectLabel, controls.objectIdentifier, controls.objectStatus, controls.objectNotes, controls.objectColor].forEach((input) => {
    input.addEventListener("input", applySelectedFields);
    input.addEventListener("change", applySelectedFields);
  });
  controls.objectSize.addEventListener("input", applyObjectSize);
  controls.objectSize.addEventListener("change", () => { pushHistory(); markDirty(); });
  controls.backgroundOpacity.addEventListener("input", updateBackground);
  controls.backgroundLocked.addEventListener("change", updateBackground);
  controls.showGrid.addEventListener("change", () => { updateGrid(); markDirty(); });
  controls.snap.addEventListener("change", markDirty);
  controls.gridSize.addEventListener("change", () => { updateGrid(); markDirty(); });

  $("#duplicateObject").addEventListener("click", duplicateObject);
  $("#deleteObject").addEventListener("click", deleteObject);
  $("#saveDrawing").addEventListener("click", saveDrawing);
  $("#exportPng").addEventListener("click", exportPng);
  $("#exportPdf").addEventListener("click", exportPdf);
  $("#exportSvg").addEventListener("click", exportSvg);
  $("#undoDrawing").addEventListener("click", undo);
  $("#redoDrawing").addEventListener("click", redo);
  $("#zoomIn").addEventListener("click", () => setZoom(canvas.getZoom() * 1.2));
  $("#zoomOut").addEventListener("click", () => setZoom(canvas.getZoom() / 1.2));
  $("#fitScreen").addEventListener("click", fitToScreen);
  modeButtons.select.addEventListener("click", () => setMode("select"));
  modeButtons.pan.addEventListener("click", () => setMode("pan"));
  modeButtons.text.addEventListener("click", () => setMode("text"));
  modeButtons.connector.addEventListener("click", () => setMode("connector"));

  $$("[data-collapse-panel]").forEach((button) => {
    button.addEventListener("click", () => {
      $(".drawing-workspace").classList.toggle(`collapse-${button.dataset.collapsePanel}`);
      window.setTimeout(fitToScreen, 220);
    });
  });

  $$("[data-context-action]").forEach((button) => {
    button.addEventListener("click", () => {
      const object = canvas.getActiveObject();
      if (!object) return;
      const action = button.dataset.contextAction;
      if (action === "duplicate") duplicateObject();
      if (action === "delete") deleteObject();
      if (action === "front") { canvas.bringForward(object); pushHistory(); markDirty(); }
      if (action === "back") { canvas.sendBackwards(object); pushHistory(); markDirty(); }
      if (action === "lock") { applyLockedState(object, true); canvas.discardActiveObject(); refreshLayers(); markDirty(); }
      hideContextMenu();
    });
  });

  document.addEventListener("click", (event) => {
    if (!controls.contextMenu.contains(event.target)) hideContextMenu();
  });
  document.addEventListener("keydown", (event) => {
    if (event.target.matches("input, textarea, select")) return;
    if (event.code === "Space") { spacePressed = true; event.preventDefault(); }
    if (event.key === "Escape") setMode("select");
    if (event.key.toLowerCase() === "v") setMode("select");
    if (event.key.toLowerCase() === "h") setMode("pan");
    if (event.key.toLowerCase() === "c") setMode("connector");
    if (event.key.toLowerCase() === "t") setMode("text");
    if (event.key === "Delete" || event.key === "Backspace") deleteObject();
    if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === "d") { event.preventDefault(); duplicateObject(); }
    if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === "s") { event.preventDefault(); saveDrawing(); }
    if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === "z") { event.preventDefault(); event.shiftKey ? redo() : undo(); }
  });
  document.addEventListener("keyup", (event) => {
    if (event.code === "Space") spacePressed = false;
  });
  window.addEventListener("resize", () => window.setTimeout(fitToScreen, 100));
  window.addEventListener("beforeunload", (event) => {
    if (!dirty) return;
    event.preventDefault();
    event.returnValue = "";
  });

  setMode("select");
  loadInitialCanvas();
})();
