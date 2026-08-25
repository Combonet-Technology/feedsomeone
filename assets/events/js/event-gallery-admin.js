(function () {
  "use strict";

  var input = document.getElementById("event-images");
  var dropzone = document.getElementById("event-dropzone");
  var list = document.getElementById("event-upload-list");
  var form = document.getElementById("event-gallery-upload");
  var startButton = document.getElementById("event-start-upload");
  var stopButton = document.getElementById("event-stop-upload");
  var cancelButton = document.getElementById("event-cancel-upload");
  var deleteButton = document.getElementById("event-delete-selected");
  var selectAll = document.getElementById("event-select-all");
  var globalStatus = document.getElementById("event-upload-status");
  if (!input || !dropzone || !list || !form || !startButton) return;

  var queue = [];
  var running = false;
  var stopRequested = false;
  var nextId = 1;
  var acceptedTypes = ["image/jpeg", "image/png", "image/webp"];

  function queuedItems() {
    return queue.filter(function (item) { return item.state === "queued"; });
  }

  function updateControls() {
    var hasQueued = queuedItems().length > 0;
    var hasSelected = queue.some(function (item) { return item.selected && item.state === "queued"; });
    startButton.disabled = running || !hasQueued;
    stopButton.disabled = !running;
    cancelButton.disabled = !running && !hasQueued;
    deleteButton.disabled = running || !hasSelected;
    selectAll.disabled = running || !hasQueued;
    selectAll.checked = hasQueued && queuedItems().every(function (item) { return item.selected; });
  }

  function setItemState(item, state, message) {
    item.state = state;
    item.card.dataset.state = state;
    item.status.textContent = message;
    item.progress.hidden = state !== "uploading";
    Array.from(item.card.querySelectorAll("input")).forEach(function (field) {
      field.disabled = state !== "queued";
    });
    updateControls();
  }

  function escapeAttribute(value) {
    return String(value).replace(/&/g, "&amp;").replace(/"/g, "&quot;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
  }

  function addFiles(files) {
    Array.from(files).forEach(function (file) {
      if (acceptedTypes.indexOf(file.type) === -1) {
        globalStatus.textContent = file.name + " is not a supported JPEG, PNG or WebP image.";
        return;
      }
      var item = { id: nextId++, file: file, state: "queued", selected: false };
      var card = document.createElement("article");
      card.className = "oef-upload-card";
      card.dataset.state = item.state;
      card.dataset.queueId = String(item.id);
      var image = document.createElement("img");
      image.src = URL.createObjectURL(file);
      image.alt = "Preview of " + file.name;
      image.onload = function () { URL.revokeObjectURL(image.src); };
      card.appendChild(image);
      card.insertAdjacentHTML("beforeend", '<div class="oef-card-head"><input class="oef-queue-select" type="checkbox" aria-label="Select ' + escapeAttribute(file.name) + '"><strong></strong></div><label>Alternative text *</label><input class="oef-alt" maxlength="255" required placeholder="Describe the image"><label>Caption</label><input class="oef-caption" maxlength="500" placeholder="Optional public caption"><label>Additional tags</label><input class="oef-tags" placeholder="volunteers, food-relief"><label><input class="oef-publish" type="checkbox" value="1"> Approved for public gallery</label><progress max="100" value="0" hidden></progress><small class="oef-card-status">Queued</small>');
      card.querySelector("strong").textContent = file.name;
      item.card = card;
      item.status = card.querySelector(".oef-card-status");
      item.progress = card.querySelector("progress");
      card.querySelector(".oef-queue-select").addEventListener("change", function (event) {
        item.selected = event.target.checked;
        updateControls();
      });
      queue.push(item);
      list.appendChild(card);
    });
    input.value = "";
    if (queuedItems().length) globalStatus.textContent = queuedItems().length + " image(s) ready to upload.";
    updateControls();
  }

  function formDataFor(item) {
    var data = new FormData();
    data.append("csrfmiddlewaretoken", form.querySelector('[name="csrfmiddlewaretoken"]').value);
    data.append("images", item.file, item.file.name);
    data.append("alt_text_0", item.card.querySelector(".oef-alt").value);
    data.append("caption_0", item.card.querySelector(".oef-caption").value);
    data.append("tags_0", item.card.querySelector(".oef-tags").value);
    if (item.card.querySelector(".oef-publish").checked) data.append("publish_0", "1");
    return data;
  }

  function uploadItem(item) {
    return new Promise(function (resolve) {
      var request = new XMLHttpRequest();
      setItemState(item, "uploading", "Uploading…");
      request.open("POST", form.action);
      request.setRequestHeader("X-Requested-With", "XMLHttpRequest");
      request.upload.addEventListener("progress", function (event) {
        if (event.lengthComputable) item.progress.value = Math.round((event.loaded / event.total) * 100);
      });
      request.addEventListener("load", function () {
        var payload = {};
        try { payload = JSON.parse(request.responseText); } catch (error) { payload = {}; }
        if (request.status >= 200 && request.status < 300 && payload.uploaded) {
          item.progress.value = 100;
          setItemState(item, "uploaded", "Uploaded");
        } else {
          var detail = (payload.errors && payload.errors[0]) || (payload.results && payload.results[0] && payload.results[0].error) || "Upload failed. Please try again.";
          setItemState(item, "failed", detail);
        }
        resolve();
      });
      request.addEventListener("error", function () { setItemState(item, "failed", "Network error. Please try again."); resolve(); });
      request.send(formDataFor(item));
    });
  }

  async function startUpload() {
    if (running || !queuedItems().length) return;
    var invalid = queuedItems().some(function (item) { return !item.card.querySelector(".oef-alt").reportValidity(); });
    if (invalid) {
      globalStatus.textContent = "Add alternative text for every queued image before uploading.";
      return;
    }
    running = true;
    stopRequested = false;
    updateControls();
    globalStatus.textContent = "Uploading queued images…";
    while (!stopRequested && queuedItems().length) await uploadItem(queuedItems()[0]);
    running = false;
    updateControls();
    var failed = queue.filter(function (item) { return item.state === "failed"; }).length;
    if (stopRequested && queuedItems().length) globalStatus.textContent = "Upload stopped. Remaining images are still queued.";
    else if (failed) globalStatus.textContent = "Upload finished with " + failed + " failed image(s).";
    else {
      globalStatus.textContent = "All images uploaded. Refreshing the gallery…";
      window.setTimeout(function () { window.location.reload(); }, 500);
    }
  }

  function cancelPending() {
    stopRequested = true;
    queue.filter(function (item) { return item.state === "queued"; }).forEach(function (item) {
      setItemState(item, "cancelled", "Cancelled");
    });
    globalStatus.textContent = running ? "Pending uploads cancelled; the current image will finish safely." : "Queued uploads cancelled.";
    updateControls();
  }

  function deleteSelected() {
    queue.filter(function (item) { return item.selected && item.state === "queued"; }).forEach(function (item) {
      item.card.remove();
      queue = queue.filter(function (candidate) { return candidate !== item; });
    });
    globalStatus.textContent = queuedItems().length + " image(s) ready to upload.";
    updateControls();
  }

  input.addEventListener("change", function () { addFiles(input.files); });
  dropzone.addEventListener("click", function (event) { if (event.target !== input) input.click(); });
  dropzone.addEventListener("keydown", function (event) { if (event.key === "Enter" || event.key === " ") { event.preventDefault(); input.click(); } });
  ["dragenter", "dragover"].forEach(function (name) { dropzone.addEventListener(name, function (event) { event.preventDefault(); dropzone.classList.add("is-dragging"); }); });
  ["dragleave", "drop"].forEach(function (name) { dropzone.addEventListener(name, function (event) { event.preventDefault(); dropzone.classList.remove("is-dragging"); }); });
  dropzone.addEventListener("drop", function (event) { addFiles(event.dataTransfer.files); });
  startButton.addEventListener("click", startUpload);
  stopButton.addEventListener("click", function () { stopRequested = true; globalStatus.textContent = "Stopping after the current image…"; updateControls(); });
  cancelButton.addEventListener("click", cancelPending);
  deleteButton.addEventListener("click", deleteSelected);
  selectAll.addEventListener("change", function () {
    queuedItems().forEach(function (item) { item.selected = selectAll.checked; item.card.querySelector(".oef-queue-select").checked = selectAll.checked; });
    updateControls();
  });
  form.addEventListener("submit", function (event) { event.preventDefault(); startUpload(); });
  updateControls();
})();
