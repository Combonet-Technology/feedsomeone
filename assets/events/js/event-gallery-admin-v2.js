(function () {
  "use strict";

  var input = document.getElementById("event-images");
  var dropzone = document.getElementById("event-dropzone");
  var list = document.getElementById("event-upload-list");
  var form = document.getElementById("event-gallery-upload");
  var status = document.getElementById("event-upload-status");
  if (!input || !dropzone || !list || !form || !status) return;

  var acceptedTypes = ["image/jpeg", "image/png", "image/webp"];
  var pending = 0;
  var failed = 0;

  function createCard(file) {
    var card = document.createElement("article");
    card.className = "oef-upload-card";
    card.dataset.state = "uploading";
    var image = document.createElement("img");
    image.src = URL.createObjectURL(file);
    image.alt = "Preview of " + file.name;
    image.onload = function () { URL.revokeObjectURL(image.src); };
    var name = document.createElement("strong");
    name.textContent = file.name;
    var progress = document.createElement("progress");
    progress.max = 100;
    progress.value = 0;
    var message = document.createElement("small");
    message.className = "oef-card-status";
    message.textContent = "Uploading…";
    card.appendChild(image);
    card.appendChild(name);
    card.appendChild(progress);
    card.appendChild(message);
    list.appendChild(card);
    return { card: card, progress: progress, message: message };
  }

  function upload(file) {
    var ui = createCard(file);
    var data = new FormData();
    data.append("csrfmiddlewaretoken", form.querySelector('[name="csrfmiddlewaretoken"]').value);
    data.append("images", file, file.name);
    var request = new XMLHttpRequest();
    request.open("POST", form.action);
    request.setRequestHeader("X-Requested-With", "XMLHttpRequest");
    request.upload.addEventListener("progress", function (event) {
      if (event.lengthComputable) ui.progress.value = Math.round((event.loaded / event.total) * 100);
    });
    request.addEventListener("load", function () {
      var payload = {};
      try { payload = JSON.parse(request.responseText); } catch (error) { payload = {}; }
      if (request.status >= 200 && request.status < 300 && payload.uploaded) {
        ui.progress.value = 100;
        ui.card.dataset.state = "uploaded";
        ui.message.textContent = "Uploaded";
      } else {
        failed += 1;
        ui.card.dataset.state = "failed";
        ui.message.textContent = (payload.errors && payload.errors[0]) || "Upload failed. Please try again.";
      }
      finishOne();
    });
    request.addEventListener("error", function () {
      failed += 1;
      ui.card.dataset.state = "failed";
      ui.message.textContent = "Network error. Please try again.";
      finishOne();
    });
    request.send(data);
  }

  function finishOne() {
    pending -= 1;
    if (pending > 0) {
      status.textContent = pending + " image(s) still uploading…";
      return;
    }
    if (failed) {
      status.textContent = "Upload finished with " + failed + " failed image(s). Successful images are available below after refresh.";
      return;
    }
    status.textContent = "Upload complete. Opening image details…";
    window.setTimeout(function () { window.location.reload(); }, 500);
  }

  function addFiles(files) {
    var valid = Array.from(files).filter(function (file) {
      if (acceptedTypes.indexOf(file.type) !== -1) return true;
      status.textContent = file.name + " is not a supported JPEG, PNG or WebP image.";
      return false;
    });
    if (!valid.length) return;
    pending += valid.length;
    failed = 0;
    status.textContent = "Uploading " + valid.length + " image(s)…";
    valid.forEach(upload);
    input.value = "";
  }

  input.addEventListener("change", function () { addFiles(input.files); });
  dropzone.addEventListener("click", function (event) { if (event.target !== input) input.click(); });
  dropzone.addEventListener("keydown", function (event) { if (event.key === "Enter" || event.key === " ") { event.preventDefault(); input.click(); } });
  ["dragenter", "dragover"].forEach(function (name) { dropzone.addEventListener(name, function (event) { event.preventDefault(); dropzone.classList.add("is-dragging"); }); });
  ["dragleave", "drop"].forEach(function (name) { dropzone.addEventListener(name, function (event) { event.preventDefault(); dropzone.classList.remove("is-dragging"); }); });
  dropzone.addEventListener("drop", function (event) { addFiles(event.dataTransfer.files); });
  form.addEventListener("submit", function (event) { event.preventDefault(); });
}());
