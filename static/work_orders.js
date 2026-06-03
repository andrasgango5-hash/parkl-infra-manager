(() => {
  const form = document.querySelector("[data-work-order-form]");
  if (!form) return;

  const rowTemplates = {
    materials: `
      <tr>
        <td><input class="form-control form-control-sm" name="material_name[]" placeholder="pl. UTP kábel"></td>
        <td><input class="form-control form-control-sm" name="material_item_number[]"></td>
        <td><input class="form-control form-control-sm" name="material_quantity[]" type="number" step="0.01"></td>
        <td><input class="form-control form-control-sm" name="material_unit[]" placeholder="db / m"></td>
        <td><input class="form-control form-control-sm" name="material_notes[]"></td>
        <td><button class="btn btn-outline-danger btn-sm" type="button" data-remove-row><i class="bi bi-trash"></i></button></td>
      </tr>`,
    measurements: `
      <tr>
        <td><input class="form-control form-control-sm" name="measurement_name[]" placeholder="pl. feszültség"></td>
        <td><input class="form-control form-control-sm" name="measurement_value[]"></td>
        <td><input class="form-control form-control-sm" name="measurement_unit[]" placeholder="V / A / Ω"></td>
        <td><input class="form-control form-control-sm" name="measurement_notes[]"></td>
        <td><button class="btn btn-outline-danger btn-sm" type="button" data-remove-row><i class="bi bi-trash"></i></button></td>
      </tr>`,
  };

  document.querySelectorAll("[data-add-row]").forEach((button) => {
    button.addEventListener("click", () => {
      const type = button.dataset.addRow;
      const container = document.querySelector(`[data-row-container="${type}"]`);
      if (container && rowTemplates[type]) container.insertAdjacentHTML("beforeend", rowTemplates[type]);
    });
  });

  document.addEventListener("click", (event) => {
    const removeButton = event.target.closest("[data-remove-row]");
    if (removeButton) removeButton.closest("tr").remove();
  });

  const arrival = form.querySelector("[name='arrival_time']");
  const departure = form.querySelector("[name='departure_time']");
  const durationOutput = form.querySelector("[data-duration-output]");
  const updateDuration = () => {
    if (!arrival || !departure || !durationOutput || !arrival.value || !departure.value) {
      if (durationOutput) durationOutput.value = "-";
      return;
    }
    const [startHour, startMinute] = arrival.value.split(":").map(Number);
    const [endHour, endMinute] = departure.value.split(":").map(Number);
    const minutes = endHour * 60 + endMinute - (startHour * 60 + startMinute);
    if (minutes < 0) {
      durationOutput.value = "Érvénytelen időtartam";
      return;
    }
    const hours = Math.floor(minutes / 60);
    const remaining = minutes % 60;
    durationOutput.value = `${hours ? `${hours} óra ` : ""}${remaining ? `${remaining} perc` : ""}`.trim() || "0 perc";
  };
  [arrival, departure].forEach((input) => input && input.addEventListener("input", updateDuration));

  const signatures = [];
  document.querySelectorAll("[data-signature-canvas]").forEach((canvas) => {
    const fieldName = canvas.dataset.signatureCanvas;
    const hidden = form.querySelector(`[name="${fieldName}"]`);
    const context = canvas.getContext("2d");
    const resize = () => {
      const ratio = window.devicePixelRatio || 1;
      const width = canvas.clientWidth;
      const height = canvas.clientHeight;
      canvas.width = width * ratio;
      canvas.height = height * ratio;
      context.setTransform(ratio, 0, 0, ratio, 0, 0);
      context.lineWidth = 2;
      context.lineCap = "round";
      context.strokeStyle = "#21182f";
    };
    resize();
    let drawing = false;
    let touched = false;
    const point = (event) => {
      const rect = canvas.getBoundingClientRect();
      const source = event.touches ? event.touches[0] : event;
      return { x: source.clientX - rect.left, y: source.clientY - rect.top };
    };
    const start = (event) => {
      event.preventDefault();
      drawing = true;
      touched = true;
      const p = point(event);
      context.beginPath();
      context.moveTo(p.x, p.y);
    };
    const move = (event) => {
      if (!drawing) return;
      event.preventDefault();
      const p = point(event);
      context.lineTo(p.x, p.y);
      context.stroke();
    };
    const stop = () => { drawing = false; };
    canvas.addEventListener("mousedown", start);
    canvas.addEventListener("mousemove", move);
    canvas.addEventListener("mouseup", stop);
    canvas.addEventListener("mouseleave", stop);
    canvas.addEventListener("touchstart", start, { passive: false });
    canvas.addEventListener("touchmove", move, { passive: false });
    canvas.addEventListener("touchend", stop);
    const clearButton = document.querySelector(`[data-clear-signature="${fieldName}"]`);
    if (clearButton) clearButton.addEventListener("click", () => {
      context.clearRect(0, 0, canvas.width, canvas.height);
      touched = false;
      if (hidden) hidden.value = "";
    });
    signatures.push({ canvas, hidden, touched: () => touched });
  });

  form.addEventListener("submit", () => {
    signatures.forEach(({ canvas, hidden, touched }) => {
      if (hidden && touched()) hidden.value = canvas.toDataURL("image/png");
    });
  });
})();
