(function () {
  "use strict";

  var dialog;
  var selectionCallback;
  var endpoints = {};
  var activeAsset = null;
  var cropper = null;
  var cropMode = "fixed";
  var flexibleCropValid = true;
  var lastValidCrop = null;

  function csrfToken() {
    var match = document.cookie.match(/(?:^|; )csrftoken=([^;]+)/);
    return match ? decodeURIComponent(match[1]) : "";
  }

  function validEndpoint(url) {
    return Boolean(url && url !== "null" && url !== "undefined");
  }

  async function jsonResponse(response, fallbackMessage) {
    var contentType = response.headers.get("content-type") || "";
    if (!contentType.toLowerCase().includes("application/json")) {
      if (response.redirected || response.status === 401 || response.status === 403) {
        throw new Error("Your admin session may have expired. Refresh the page and sign in again.");
      }
      throw new Error(fallbackMessage);
    }
    try {
      return await response.json();
    } catch (_error) {
      throw new Error(fallbackMessage);
    }
  }

  function element(tag, className, text) {
    var node = document.createElement(tag);
    if (className) node.className = className;
    if (text) node.textContent = text;
    return node;
  }

  function ensureDialog() {
    if (dialog) return dialog;
    dialog = document.createElement("dialog");
    dialog.className = "oef-media-dialog";
    dialog.innerHTML = [
      '<div class="oef-media-dialog__shell">',
      '  <header class="oef-media-dialog__header"><div><strong>OEF editorial media</strong><p>Originals stay unchanged. Crops apply only to the article placement.</p></div><button type="button" class="oef-media-dialog__close" aria-label="Close media library">×</button></header>',
      '  <nav class="oef-media-dialog__tabs" aria-label="Media options"><button type="button" data-media-tab="library">Media library</button><button type="button" data-media-tab="upload">Upload image</button></nav>',
      '  <section class="oef-media-dialog__panel" data-media-panel="library"><p class="oef-media-dialog__status" data-library-status role="status"></p><div class="oef-media-dialog__grid" data-media-grid></div></section>',
      '  <section class="oef-media-dialog__panel" data-media-panel="upload" hidden><form class="oef-media-upload"><label>Image<input name="image" type="file" accept="image/jpeg,image/png,image/webp" required></label><label>Alternative text<input name="alt_text" type="text" maxlength="255" required><small>Describe what matters for someone who cannot see the image.</small></label><label>Caption <span>(optional)</span><input name="caption" type="text" maxlength="500"></label><p class="oef-media-dialog__status" data-upload-status role="status"></p><button type="submit" class="button default">Upload image</button></form></section>',
      '  <section class="oef-media-dialog__panel" data-media-panel="details" hidden><button type="button" class="oef-back-button" data-detail-back>← Media library</button><div class="oef-media-detail"><div class="oef-media-detail__source"><img data-detail-image alt=""><span>Original source · unchanged</span></div><div><h2 data-detail-name></h2><p data-detail-dimensions></p><form data-metadata-form><label>Alternative text<input name="alt_text" maxlength="255" required></label><label>Caption <span>(optional)</span><input name="caption" maxlength="500"></label><p class="oef-media-dialog__status" data-metadata-status role="status"></p><button type="submit" class="button" data-save-metadata>Save metadata</button></form><button type="button" class="button default" data-open-crop>Use image</button></div></div></section>',
      '  <section class="oef-media-dialog__panel oef-crop-panel" data-media-panel="crop" hidden><div class="oef-crop-heading"><button type="button" class="oef-back-button" data-crop-back>← Media library</button><div><h2>Prepare image</h2><p data-crop-guidance></p><small>The original media-library image will not be changed.</small></div></div><div class="oef-crop-mode" data-crop-mode-controls hidden><span>Crop mode</span><button type="button" data-crop-mode="fixed">Fixed 16:9</button><button type="button" data-crop-mode="flexible">Flexible</button></div><div class="oef-crop-workspace"><div class="oef-crop-stage"><img data-crop-image alt="Image being cropped"></div><aside class="oef-placement-preview"><strong>Article preview</strong><p>This is how the image proportions will appear in the article.</p><div class="oef-placement-preview__frame"><div class="oef-crop-preview"></div></div></aside></div><p class="oef-media-dialog__status" data-crop-status role="status"></p><div class="oef-crop-actions"><button type="button" class="button" data-crop-reset>Reset</button><button type="button" class="button" data-use-original hidden>Use original</button><button type="button" class="button default" data-crop-confirm>Use this crop</button></div></section>',
      '</div>'
    ].join("");
    document.body.appendChild(dialog);
    dialog.querySelector(".oef-media-dialog__close").addEventListener("click", function () { dialog.close(); });
    dialog.addEventListener("close", function () { destroyCropper(); selectionCallback = null; activeAsset = null; });
    dialog.querySelectorAll("[data-media-tab]").forEach(function (button) { button.addEventListener("click", function () { showPanel(button.dataset.mediaTab); }); });
    dialog.querySelector(".oef-media-upload").addEventListener("submit", uploadImage);
    dialog.querySelector("[data-detail-back]").addEventListener("click", function () { showPanel("library"); });
    dialog.querySelector("[data-crop-back]").addEventListener("click", function () { destroyCropper(); showPanel("library"); });
    dialog.querySelector("[data-open-crop]").addEventListener("click", function () { openCropper(activeAsset); });
    dialog.querySelector("[data-crop-reset]").addEventListener("click", function () { if (cropper) cropper.reset(); });
    dialog.querySelector("[data-crop-confirm]").addEventListener("click", confirmCrop);
    dialog.querySelector("[data-use-original]").addEventListener("click", useOriginal);
    dialog.querySelectorAll("[data-crop-mode]").forEach(function (button) {
      button.addEventListener("click", function () { setCropMode(button.dataset.cropMode); });
    });
    dialog.querySelector("[data-metadata-form]").addEventListener("submit", saveMetadata);
    return dialog;
  }

  function showPanel(name) {
    ensureDialog().classList.toggle("is-subview", name === "details" || name === "crop");
    ensureDialog().querySelectorAll("[data-media-panel]").forEach(function (panel) { panel.hidden = panel.dataset.mediaPanel !== name; });
    dialog.querySelectorAll("[data-media-tab]").forEach(function (button) {
      var selected = button.dataset.mediaTab === name;
      button.classList.toggle("is-active", selected);
      button.setAttribute("aria-current", selected ? "page" : "false");
    });
    if (name === "library") loadLibrary();
  }

  function renderAsset(asset) {
    var card = element("article", "oef-media-card");
    var open = element("button", "oef-media-card__open");
    open.type = "button";
    open.setAttribute("aria-label", "Use " + (asset.filename || "editorial image"));
    var image = element("img");
    image.src = asset.url;
    image.alt = "";
    image.loading = "lazy";
    open.appendChild(image);
    open.addEventListener("click", function () { openCropper(asset); });
    card.appendChild(open);
    card.appendChild(element("strong", "oef-media-card__name", asset.filename || "Editorial image"));
    var actions = element("div", "oef-media-card__actions");
    var use = element("button", "button default", "Use image");
    use.type = "button";
    use.addEventListener("click", function () { openCropper(asset); });
    var details = element("button", "button", "View details");
    details.type = "button";
    details.addEventListener("click", function () { showDetails(asset); });
    actions.appendChild(use);
    actions.appendChild(details);
    card.appendChild(actions);
    return card;
  }

  async function loadLibrary() {
    var status = dialog.querySelector("[data-library-status]");
    var grid = dialog.querySelector("[data-media-grid]");
    status.textContent = "Loading media library…";
    grid.replaceChildren();
    try {
      var response = await fetch(endpoints.libraryUrl, { credentials: "same-origin" });
      var payload = await response.json();
      if (!response.ok) throw new Error(payload.error || "The media library could not be loaded.");
      status.textContent = payload.assets.length ? "Choose Use image to prepare it, or View details to edit metadata." : "No editorial images have been uploaded yet.";
      payload.assets.forEach(function (asset) { grid.appendChild(renderAsset(asset)); });
    } catch (error) { status.textContent = error.message; }
  }

  function showDetails(asset) {
    activeAsset = asset;
    showPanel("details");
    var image = dialog.querySelector("[data-detail-image]");
    image.src = asset.original_url || asset.url;
    image.alt = asset.alt_text || "";
    dialog.querySelector("[data-detail-name]").textContent = asset.filename || "Editorial image";
    dialog.querySelector("[data-detail-dimensions]").textContent = asset.width + " × " + asset.height + " pixels";
    var form = dialog.querySelector("[data-metadata-form]");
    form.elements.alt_text.value = asset.alt_text || "";
    form.elements.caption.value = asset.caption || "";
    form.querySelector("[data-save-metadata]").hidden = !asset.can_edit;
    Array.from(form.elements).forEach(function (field) { if (field.name) field.disabled = !asset.can_edit; });
    dialog.querySelector("[data-metadata-status]").textContent = asset.can_edit ? "" : "You can view this metadata but cannot edit this asset.";
  }

  async function saveMetadata(event) {
    event.preventDefault();
    if (!activeAsset || !activeAsset.can_edit) return;
    var form = event.currentTarget;
    var status = dialog.querySelector("[data-metadata-status]");
    status.textContent = "Saving metadata…";
    try {
      var response = await fetch(activeAsset.metadata_url, { method: "POST", credentials: "same-origin", headers: { "X-CSRFToken": csrfToken() }, body: new FormData(form) });
      var payload = await response.json();
      if (!response.ok) throw new Error(payload.error || "The metadata could not be saved.");
      activeAsset = payload;
      status.textContent = "Metadata saved.";
      dialog.querySelector("[data-detail-image]").alt = payload.alt_text || "";
    } catch (error) { status.textContent = error.message; }
  }

  function destroyCropper() {
    if (cropper) cropper.destroy();
    cropper = null;
  }

  function openCropper(asset) {
    if (asset) activeAsset = asset;
    if (!activeAsset || !window.Cropper) return;
    showPanel("crop");
    destroyCropper();
    cropMode = "fixed";
    flexibleCropValid = true;
    lastValidCrop = null;
    dialog.querySelector("[data-crop-mode-controls]").hidden = endpoints.usage === "feature";
    dialog.querySelector("[data-use-original]").hidden = endpoints.usage === "feature";
    dialog.querySelector("[data-crop-guidance]").textContent = endpoints.usage === "feature" ? "Move and resize the fixed 16:9 frame for the feature image." : "Start with 16:9, or choose Flexible to control the height within safe article limits.";
    setCropMode("fixed");
    var image = dialog.querySelector("[data-crop-image]");
    image.onload = function () {
      cropper = new window.Cropper(image, {
        aspectRatio: 16 / 9,
        viewMode: 1,
        dragMode: "move",
        autoCropArea: 0.82,
        background: false,
        responsive: true,
        restore: false,
        movable: true,
        zoomable: true,
        rotatable: false,
        scalable: false,
        preview: ".oef-crop-preview",
        crop: function (event) { validateLiveCrop(event.detail); },
        cropend: function () {
          if (!flexibleCropValid && lastValidCrop) cropper.setData(lastValidCrop);
        }
      });
    };
    image.src = activeAsset.original_url || activeAsset.url;
  }

  function setCropMode(mode) {
    cropMode = mode === "flexible" && endpoints.usage === "inline" ? "flexible" : "fixed";
    dialog.querySelectorAll("[data-crop-mode]").forEach(function (button) {
      var active = button.dataset.cropMode === cropMode;
      button.classList.toggle("is-active", active);
      button.setAttribute("aria-pressed", active ? "true" : "false");
    });
    flexibleCropValid = true;
    dialog.querySelector("[data-crop-status]").textContent = "";
    dialog.querySelector("[data-crop-confirm]").disabled = false;
    dialog.querySelector(".oef-placement-preview__frame").style.aspectRatio = "16 / 9";
    if (cropper) cropper.setAspectRatio(cropMode === "fixed" ? 16 / 9 : NaN);
  }

  function validateLiveCrop(data) {
    var ratio = data.width / data.height;
    var preview = dialog.querySelector(".oef-placement-preview__frame");
    preview.style.aspectRatio = String(ratio);
    if (cropMode !== "flexible" || (ratio >= 0.75 && ratio <= 2.4)) {
      flexibleCropValid = true;
      lastValidCrop = { x: data.x, y: data.y, width: data.width, height: data.height };
      dialog.querySelector("[data-crop-status]").textContent = "";
      dialog.querySelector("[data-crop-confirm]").disabled = false;
      return;
    }
    flexibleCropValid = false;
    dialog.querySelector("[data-crop-status]").textContent = "Flexible crops must stay between portrait 3:4 and wide 12:5.";
    dialog.querySelector("[data-crop-confirm]").disabled = true;
  }

  function selectAsset(selected) {
    var callback = selectionCallback;
    selectionCallback = null;
    dialog.close();
    if (callback) callback(selected);
  }

  function useOriginal() {
    if (!activeAsset || endpoints.usage !== "inline") return;
    selectAsset(Object.assign({}, activeAsset, { url: activeAsset.url, crop: {}, crop_mode: "original" }));
  }

  async function confirmCrop() {
    if (!cropper || !activeAsset) return;
    var status = dialog.querySelector("[data-crop-status]");
    var button = dialog.querySelector("[data-crop-confirm]");
    var crop = cropper.getData(true);
    var data = new FormData();
    ["x", "y", "width", "height"].forEach(function (key) { data.append(key, crop[key]); });
    data.append("usage", endpoints.usage);
    data.append("crop_mode", cropMode);
    status.textContent = "Preparing crop…";
    button.disabled = true;
    try {
      var response = await fetch(activeAsset.crop_url, { method: "POST", credentials: "same-origin", headers: { "X-CSRFToken": csrfToken() }, body: data });
      var payload = await response.json();
      if (!response.ok) throw new Error(payload.error || "The crop could not be prepared.");
      selectAsset(Object.assign({}, activeAsset, { url: payload.url, feature_url: payload.url, crop: payload.crop, crop_mode: payload.crop_mode }));
    } catch (error) { status.textContent = error.message; }
    finally { button.disabled = false; }
  }

  async function uploadImage(event) {
    event.preventDefault();
    var form = event.currentTarget;
    var status = form.querySelector("[data-upload-status]");
    var submit = form.querySelector('[type="submit"]');
    status.textContent = "Uploading image…";
    submit.disabled = true;
    try {
      if (!validEndpoint(endpoints.uploadUrl)) {
        throw new Error("Image uploading is not configured. Refresh the page and try again.");
      }
      var response = await fetch(endpoints.uploadUrl, { method: "POST", credentials: "same-origin", headers: { "X-CSRFToken": csrfToken() }, body: new FormData(form) });
      var payload = await jsonResponse(response, "The image service returned an unexpected response. Refresh the page and try again.");
      if (!response.ok) throw new Error(payload.error || "The image could not be uploaded.");
      form.reset();
      status.textContent = "";
      openCropper(payload);
    } catch (error) { status.textContent = error.message; }
    finally { submit.disabled = false; }
  }

  window.OEFMediaManager = {
    open: function (options) {
      ensureDialog();
      endpoints = { libraryUrl: options.libraryUrl, uploadUrl: options.uploadUrl, usage: options.usage || "inline" };
      selectionCallback = options.onSelect;
      activeAsset = null;
      dialog.showModal();
      if (options.asset) showDetails(options.asset);
      else showPanel(options.mode === "upload" ? "upload" : "library");
    }
  };
})();
