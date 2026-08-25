(function () {
  "use strict";

  function normalise(value) {
    return value.trim().replace(/\s+/g, " ");
  }

  function parse(value) {
    return value.split(",").map(normalise).filter(Boolean).filter(function (tag, index, tags) {
      return tags.findIndex(function (candidate) {
        return candidate.toLowerCase() === tag.toLowerCase();
      }) === index;
    });
  }

  function enhance(original) {
    if (!original || original.dataset.oefTagEditor === "ready") return;
    original.dataset.oefTagEditor = "ready";
    original.hidden = true;

    var tags = parse(original.value);
    var editor = document.createElement("div");
    editor.className = "oef-tag-editor";
    editor.setAttribute("role", "group");
    editor.setAttribute("aria-label", "Article tags");

    var input = document.createElement("input");
    input.type = "text";
    input.className = "oef-tag-editor__input";
    input.placeholder = original.placeholder || "Add a tag and press Enter";
    input.autocomplete = "off";
    input.setAttribute("aria-label", "Add an article tag");

    function sync() {
      original.value = tags.join(", ");
      original.dispatchEvent(new Event("change", { bubbles: true }));
    }

    function render() {
      editor.querySelectorAll(".oef-tag-editor__chip").forEach(function (chip) { chip.remove(); });
      tags.forEach(function (tag, index) {
        var chip = document.createElement("span");
        chip.className = "oef-tag-editor__chip";
        chip.append(document.createTextNode(tag));

        var remove = document.createElement("button");
        remove.type = "button";
        remove.className = "oef-tag-editor__remove";
        remove.textContent = "×";
        remove.setAttribute("aria-label", "Remove tag " + tag);
        remove.addEventListener("click", function () {
          tags.splice(index, 1);
          sync();
          render();
          input.focus();
        });

        chip.append(remove);
        editor.insertBefore(chip, input);
      });
    }

    function commit() {
      parse(input.value).forEach(function (candidate) {
        if (!tags.some(function (tag) { return tag.toLowerCase() === candidate.toLowerCase(); })) {
          tags.push(candidate);
        }
      });
      input.value = "";
      sync();
      render();
    }

    input.addEventListener("keydown", function (event) {
      if (event.key === "Enter" || event.key === ",") {
        event.preventDefault();
        commit();
      } else if (event.key === "Backspace" && !input.value && tags.length) {
        tags.pop();
        sync();
        render();
      }
    });
    input.addEventListener("blur", commit);
    editor.addEventListener("click", function () { input.focus(); });

    original.insertAdjacentElement("afterend", editor);
    editor.append(input);
    render();
  }

  function initialise() { enhance(document.querySelector("#id_tags")); }

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", initialise);
  else initialise();
})();
