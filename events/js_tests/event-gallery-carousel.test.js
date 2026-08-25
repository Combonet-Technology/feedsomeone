'use strict';

const assert = require('node:assert/strict');
const test = require('node:test');

class FakeClassList {
  constructor() {
    this.values = new Set();
  }

  toggle(name, enabled) {
    if (enabled) {
      this.values.add(name);
    } else {
      this.values.delete(name);
    }
  }

  contains(name) {
    return this.values.has(name);
  }
}

class FakeElement {
  constructor(attributes) {
    this.attributes = Object.assign({}, attributes);
    this.classList = new FakeClassList();
    this.listeners = {};
    this.scrollLeft = 0;
    this.textContent = '';
    this.disabled = false;
  }

  addEventListener(name, callback) {
    this.listeners[name] = callback;
  }

  click() {
    if (this.listeners.click) {
      this.listeners.click({ preventDefault() {} });
    }
  }

  focus() {}

  getAttribute(name) {
    return this.attributes[name] === undefined ? null : this.attributes[name];
  }

  setAttribute(name, value) {
    this.attributes[name] = String(value);
  }
}

test('next navigation updates the preview beyond the tenth image', () => {
  const root = new FakeElement({ 'data-active-index': '0' });
  const preview = new FakeElement();
  const previewImage = new FakeElement();
  const counter = new FakeElement();
  const strip = new FakeElement();
  const previous = new FakeElement();
  const next = new FakeElement();
  const thumbnails = Array.from({ length: 12 }, (_, index) => {
    const thumbnail = new FakeElement({
      'data-index': String(index),
      'data-full-url': `https://example.com/photo-${index}.jpg`,
      'data-alt': `Photograph ${index}`,
    });
    thumbnail.getBoundingClientRect = () => ({
      left: index * 106 - strip.scrollLeft,
      right: index * 106 - strip.scrollLeft + 96,
    });
    return thumbnail;
  });
  const lightboxLinks = thumbnails.map(() => new FakeElement());

  strip.getBoundingClientRect = () => ({ left: 0, right: 1000 });
  const singles = {
    '[data-gallery-preview]': preview,
    '[data-gallery-preview-image]': previewImage,
    '[data-gallery-counter]': counter,
    '[data-gallery-thumbnails]': strip,
    '[data-gallery-previous]': previous,
    '[data-gallery-next]': next,
  };
  root.querySelector = selector => singles[selector] || null;
  root.querySelectorAll = selector => (
    selector === '[data-gallery-thumbnail]' ? thumbnails : lightboxLinks
  );

  global.document = {
    addEventListener(name, callback) {
      if (name === 'DOMContentLoaded') {
        callback();
      }
    },
    querySelectorAll() {
      return [root];
    },
  };

  require('../../assets/events/js/event-gallery-carousel.js');
  for (let index = 0; index < 11; index += 1) {
    next.click();
  }

  assert.equal(root.getAttribute('data-active-index'), '11');
  assert.equal(previewImage.getAttribute('src'), 'https://example.com/photo-11.jpg');
  assert.equal(counter.textContent, '12 / 12');
  assert.equal(thumbnails[11].getAttribute('aria-current'), 'true');
  assert.equal(thumbnails[11].classList.contains('is-active'), true);
  assert.ok(strip.scrollLeft > 0);

  delete global.document;
});
