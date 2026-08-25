(function () {
  'use strict';

  function initialiseGallery(root) {
    var preview = root.querySelector('[data-gallery-preview]');
    var previewImage = root.querySelector('[data-gallery-preview-image]');
    var counter = root.querySelector('[data-gallery-counter]');
    var strip = root.querySelector('[data-gallery-thumbnails]');
    var thumbnails = Array.prototype.slice.call(
      root.querySelectorAll('[data-gallery-thumbnail]')
    );
    var lightboxLinks = Array.prototype.slice.call(
      root.querySelectorAll('[data-gallery-lightbox-link]')
    );
    var previous = root.querySelector('[data-gallery-previous]');
    var next = root.querySelector('[data-gallery-next]');
    if (!preview || !previewImage || !strip || !previous || !next || !thumbnails.length) {
      return;
    }

    function activeIndex() {
      var value = parseInt(root.getAttribute('data-active-index'), 10);
      return Number.isNaN(value) ? 0 : value;
    }

    function keepThumbnailVisible(thumbnail) {
      var stripRect = strip.getBoundingClientRect();
      var thumbnailRect = thumbnail.getBoundingClientRect();
      if (thumbnailRect.left < stripRect.left) {
        strip.scrollLeft -= stripRect.left - thumbnailRect.left + 10;
      } else if (thumbnailRect.right > stripRect.right) {
        strip.scrollLeft += thumbnailRect.right - stripRect.right + 10;
      }
    }

    function selectImage(index, shouldFocus) {
      index = parseInt(index, 10);
      if (Number.isNaN(index)) {
        return;
      }
      if (index < 0) {
        index = thumbnails.length - 1;
      } else if (index >= thumbnails.length) {
        index = 0;
      }

      root.setAttribute('data-active-index', String(index));
      thumbnails.forEach(function (thumbnail, thumbnailIndex) {
        var selected = thumbnailIndex === index;
        thumbnail.classList.toggle('is-active', selected);
        thumbnail.setAttribute('aria-current', selected ? 'true' : 'false');
      });

      var activeThumbnail = thumbnails[index];
      var fullUrl = activeThumbnail.getAttribute('data-full-url');
      var alt = activeThumbnail.getAttribute('data-alt') || '';
      preview.setAttribute('href', fullUrl);
      preview.setAttribute('aria-label', 'Open ' + alt + ' in full screen');
      previewImage.setAttribute('src', fullUrl);
      previewImage.setAttribute('alt', alt);
      if (counter) {
        counter.textContent = (index + 1) + ' / ' + thumbnails.length;
      }
      keepThumbnailVisible(activeThumbnail);
      if (shouldFocus) {
        activeThumbnail.focus();
      }
    }

    thumbnails.forEach(function (thumbnail, index) {
      thumbnail.addEventListener('click', function () {
        selectImage(thumbnail.getAttribute('data-index') || index, false);
      });
    });

    previous.addEventListener('click', function () {
      selectImage(activeIndex() - 1, false);
    });

    next.addEventListener('click', function () {
      selectImage(activeIndex() + 1, false);
    });

    preview.addEventListener('click', function (event) {
      var index = activeIndex();
      if (lightboxLinks[index]) {
        event.preventDefault();
        lightboxLinks[index].click();
      }
    });

    root.addEventListener('keydown', function (event) {
      if (event.key === 'ArrowLeft') {
        event.preventDefault();
        selectImage(activeIndex() - 1, true);
      } else if (event.key === 'ArrowRight') {
        event.preventDefault();
        selectImage(activeIndex() + 1, true);
      }
    });

    previous.disabled = thumbnails.length < 2;
    next.disabled = thumbnails.length < 2;
  }

  document.addEventListener('DOMContentLoaded', function () {
    Array.prototype.forEach.call(
      document.querySelectorAll('[data-event-gallery]'),
      initialiseGallery
    );
  });
}());
