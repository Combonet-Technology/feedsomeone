(function () {
  "use strict";
  var stageForm = document.getElementById("oef-stage-form");
  var input = document.getElementById("oef-images");
  var dropzone = document.getElementById("oef-dropzone");
  var status = document.getElementById("oef-upload-status");
  var review = document.getElementById("oef-review");
  var reviewForm = document.getElementById("oef-review-form");
  var itemList = document.getElementById("oef-review-items");
  var batchInput = document.getElementById("oef-batch-id");
  var cancelButton = document.getElementById("oef-cancel-batch");
  if (!stageForm || !input || !dropzone || !status || !review || !reviewForm) return;
  // Baton animates its content container with transforms. Keeping this fixed
  // dialog under that container makes it size against the page instead of the
  // viewport, so mount it directly under body before it is shown.
  document.body.appendChild(review);

  function csrf() { return stageForm.querySelector("[name=csrfmiddlewaretoken]").value; }
  function post(url, data) {
    return fetch(url, {method: "POST", headers: {"X-CSRFToken": csrf(), "X-Requested-With": "XMLHttpRequest"}, body: data});
  }
  function message(text, failed) { status.textContent = text; status.style.color = failed ? "#a51d2d" : "#3d4855"; }
  function makeItem(item) {
    var row = document.createElement("div"); row.className = "oef-review__item"; row.dataset.itemId = item.id;
    var image = document.createElement("img"); image.src = item.preview_url; image.alt = "Preview of " + item.name;
    var details = document.createElement("div");
    var filename = document.createElement("strong"); filename.className = "oef-review__filename"; filename.textContent = item.name;
    var label = document.createElement("label"); label.htmlFor = "alt-" + item.id; label.textContent = "Alternative text (optional)";
    var alt = document.createElement("input"); alt.type = "text"; alt.id = "alt-" + item.id; alt.name = "alt_text_" + item.id; alt.maxLength = 255; alt.placeholder = "Describe what is visible in the photograph";
    details.appendChild(filename); details.appendChild(label); details.appendChild(alt);
    var remove = document.createElement("button"); remove.type = "button"; remove.className = "oef-review__remove"; remove.textContent = "Remove";
    remove.addEventListener("click", function () {
      var data = new FormData(); data.append("batch_id", batchInput.value); data.append("item_id", item.id);
      post(window.OEFGalleryUpload.removeUrl, data).then(function (response) { if (!response.ok) throw new Error(); row.remove(); if (!itemList.children.length) closeReview(false); }).catch(function () { message("The image could not be removed. Try again.", true); });
    });
    row.appendChild(image); row.appendChild(details); row.appendChild(remove); return row;
  }
  function openReview(payload) {
    batchInput.value = payload.batch_id; itemList.replaceChildren(); payload.items.forEach(function (item) { itemList.appendChild(makeItem(item)); }); review.hidden = false; document.body.style.overflow = "hidden"; document.getElementById("oef-event").focus();
  }
  function closeReview(cancelRemote) {
    function finish() { review.hidden = true; document.body.style.overflow = ""; itemList.replaceChildren(); batchInput.value = ""; input.value = ""; }
    if (!cancelRemote || !batchInput.value) { finish(); return; }
    var data = new FormData(); data.append("batch_id", batchInput.value);
    post(window.OEFGalleryUpload.cancelUrl, data).then(finish).catch(function () { message("The staged batch could not be cancelled. Try again.", true); });
  }
  function stage(files) {
    if (!files || !files.length) return;
    var data = new FormData(); Array.from(files).forEach(function (file) { data.append("images", file, file.name); });
    message("Staging " + files.length + " image(s) locally…"); dropzone.setAttribute("aria-busy", "true");
    post(stageForm.action, data).then(function (response) { return response.json().then(function (payload) { if (!response.ok) throw payload; return payload; }); }).then(function (payload) { message("Images are ready for review."); openReview(payload); }).catch(function (payload) { message((payload.errors && payload.errors.join(" ")) || payload.error || "The images could not be staged.", true); }).finally(function () { dropzone.removeAttribute("aria-busy"); });
  }
  input.addEventListener("change", function () { stage(input.files); });
  dropzone.addEventListener("click", function (event) { if (event.target !== input) input.click(); });
  dropzone.addEventListener("keydown", function (event) { if (event.key === "Enter" || event.key === " ") { event.preventDefault(); input.click(); } });
  ["dragenter", "dragover"].forEach(function (name) { dropzone.addEventListener(name, function (event) { event.preventDefault(); dropzone.classList.add("is-dragging"); }); });
  ["dragleave", "drop"].forEach(function (name) { dropzone.addEventListener(name, function (event) { event.preventDefault(); dropzone.classList.remove("is-dragging"); }); });
  dropzone.addEventListener("drop", function (event) { stage(event.dataTransfer.files); });
  stageForm.addEventListener("submit", function (event) { event.preventDefault(); });
  cancelButton.addEventListener("click", function () { closeReview(true); });
  reviewForm.addEventListener("submit", function () { reviewForm.querySelector("button[type=submit]").disabled = true; });
}());
