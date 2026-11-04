/* AI image analysis suggests details; original selected files are saved through normal image review. */
'use strict';

document.querySelectorAll('[data-image-analysis]').forEach((panel) => {
  const form = panel.closest('form');
  const input = form.querySelector('#images');
  const analyse = panel.querySelector('[data-analyse-image]');
  const apply = panel.querySelector('[data-apply-analysis]');
  const status = panel.querySelector('[data-analysis-status]');
  const preview = panel.querySelector('[data-analysis-preview]');
  let suggestion = null;
  let request = null;
  let generation = 0;

  function reset() {
    generation += 1;
    if (request) { request.abort(); request = null; }
    suggestion = null;
    preview.hidden = true;
    analyse.disabled = false;
    panel.removeAttribute('aria-busy');
    status.textContent = '';
  }
  input.addEventListener('change', reset);

  analyse.addEventListener('click', async () => {
    const file = input.files[0];
    if (!file) { status.textContent = 'Choose an image in Add images first.'; return; }
    reset();
    const revision = generation;
    const controller = new AbortController();
    request = controller;
    const timeout = setTimeout(() => controller.abort(), 25000);
    analyse.disabled = true;
    panel.setAttribute('aria-busy', 'true');
    status.textContent = 'Analysing the first selected image...';
    const data = new FormData();
    data.append('image', file);
    data.append('form_token', panel.dataset.formToken);
    try {
      const response = await fetch(panel.dataset.endpoint, {
        method: 'POST', body: data, credentials: 'same-origin', signal: controller.signal,
        headers: { Accept: 'application/json' },
      });
      const result = await response.json();
      if (revision !== generation) { return; }
      if (!response.ok) { throw new Error(result.error || 'Image analysis could not finish.'); }
      if (typeof result.title !== 'string' || typeof result.description !== 'string') {
        throw new Error('The image suggestions were invalid. Try again.');
      }
      suggestion = result;
      panel.querySelector('[data-analysis-title]').textContent = result.title;
      panel.querySelector('[data-analysis-description]').textContent = result.description;
      panel.querySelector('[data-analysis-category]').textContent = result.category || 'No confident style match';
      preview.hidden = false;
      status.textContent = 'Suggestions are ready. Review them, then choose Use these suggestions.';
    } catch (error) {
      if (revision !== generation) { return; }
      status.textContent = error.name === 'AbortError'
        ? 'Analysis timed out. Try again or enter the details manually.'
        : (error instanceof SyntaxError ? 'The server could not finish analysis. Try again.' : error.message);
    } finally {
      clearTimeout(timeout);
      if (revision === generation) {
        request = null;
        analyse.disabled = false;
        panel.removeAttribute('aria-busy');
      }
    }
  });

  apply.addEventListener('click', () => {
    if (!suggestion) { return; }
    if (suggestion.category) {
      const boxes = Array.from(form.querySelectorAll('input[name="category_ids"]'));
      const selected = boxes.find((box) => box.closest('label').textContent.trim() === suggestion.category);
      if (!selected) {
        status.textContent = 'The suggested category is no longer available. Analyse again or select a style manually.';
        return;
      }
      boxes.forEach((box) => { box.checked = box === selected; });
    }
    form.querySelector('#title').value = suggestion.title;
    form.querySelector('#description').value = suggestion.description;
    status.textContent = 'Suggestions applied. You can edit the details before saving.';
    form.querySelector('#title').focus();
  });
});
