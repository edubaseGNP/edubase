/**
 * Show/hide AI backend-specific fields based on the selected backend.
 * Runs on the SiteConfig change page in Django admin.
 */
(function () {
  'use strict';

  // Field rows to show per backend (by the input name attribute)
  var BACKEND_FIELDS = {
    none:      [],
    google:    ['google_ai_api_key'],
    anthropic: ['anthropic_api_key'],
    ollama:    ['ollama_base_url', 'ollama_vision_model', 'ollama_text_model'],
  };

  // All managed fields (union of all backend field lists)
  var ALL_MANAGED = [
    'google_ai_api_key',
    'anthropic_api_key',
    'ollama_base_url',
    'ollama_vision_model',
    'ollama_text_model',
  ];

  function getRow(fieldName) {
    // Works with both Unfold and classic Django admin markup
    var input = document.querySelector('[name="' + fieldName + '"]');
    if (!input) return null;
    // Walk up to the .form-row / .field-* container
    var el = input;
    for (var i = 0; i < 6; i++) {
      if (!el.parentElement) break;
      el = el.parentElement;
      if (
        el.classList.contains('form-row') ||
        el.classList.contains('field-' + fieldName) ||
        el.tagName === 'TR'
      ) {
        return el;
      }
    }
    return input.closest('.mb-4, .form-group, div') || null;
  }

  function applyVisibility(backend) {
    var visible = BACKEND_FIELDS[backend] || [];
    ALL_MANAGED.forEach(function (name) {
      var row = getRow(name);
      if (!row) return;
      row.style.display = visible.indexOf(name) !== -1 ? '' : 'none';
    });
  }

  function init() {
    var select = document.querySelector('[name="ai_backend"]');
    if (!select) return;

    applyVisibility(select.value);

    select.addEventListener('change', function () {
      applyVisibility(this.value);
    });
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
