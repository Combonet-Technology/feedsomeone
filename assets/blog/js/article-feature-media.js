(function () {
  "use strict";
  function initialise() {
    var control = document.querySelector(".oef-feature-image");
    if (!control || !window.OEFMediaManager) return;
    var mediaInput = document.querySelector("#id_feature_media");
    var cropInput = document.querySelector("#id_feature_crop");
    var clearInput = document.querySelector("#id_clear_feature_image");
    var preview = control.querySelector(".oef-feature-image__preview");
    var name = control.querySelector(".oef-feature-image__name");
    var source = control.querySelector(".oef-feature-image__source");
    var empty = control.querySelector(".oef-feature-image__empty");
    var remove = control.querySelector('[data-feature-action="remove"]');
    var libraryButton = control.querySelector('[data-feature-action="library"]');

    function applyAsset(asset) {
      mediaInput.value = asset.id;
      cropInput.value = JSON.stringify(asset.crop || {});
      clearInput.value = "";
      preview.src = asset.url;
      preview.alt = asset.alt_text || "";
      preview.hidden = false;
      name.textContent = asset.filename || "Editorial image";
      source.textContent = "Managed OEF media · custom 16:9 crop";
      empty.hidden = true;
      remove.hidden = false;
      libraryButton.textContent = "Replace Image";
    }

    libraryButton.addEventListener("click", function () {
      window.OEFMediaManager.open({ mode: "library", libraryUrl: control.dataset.libraryUrl, eventLibraryUrl: control.dataset.eventLibraryUrl, uploadUrl: control.dataset.uploadUrl, usage: "feature", onSelect: applyAsset });
    });
    remove.addEventListener("click", function () {
      mediaInput.value = "";
      cropInput.value = "{}";
      clearInput.value = "1";
      preview.removeAttribute("src");
      preview.alt = "";
      preview.hidden = true;
      name.textContent = "";
      source.textContent = "";
      empty.hidden = false;
      remove.hidden = true;
      libraryButton.textContent = "Add Image";
    });
  }
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", initialise);
  else initialise();
})();
