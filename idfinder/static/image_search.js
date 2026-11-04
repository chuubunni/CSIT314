// Keep only a resized thumbnail in this browser tab, never the source upload.
// The server continues to process uploads normally and does not store photos.
(() => {
  const input = document.querySelector('#photo');
  const preview = document.querySelector('#photo-preview');
  const form = input?.closest('form');
  const currentLabel = document.querySelector('#image-current-photo');
  if (!input || !preview || !form) return;

  const key = 'find-your-id:image-search-preview';
  const supported = ['image/jpeg', 'image/png'];
  let thumbnailTask = Promise.resolve();
  let temporaryUrl = null;

  function getSavedPreview() {
    try { return sessionStorage.getItem(key); } catch (_) { return null; }
  }
  function savePreview(dataUrl) {
    try { sessionStorage.setItem(key, dataUrl); } catch (_) { /* Private mode / quota */ }
  }
  function forgetPreview() {
    try { sessionStorage.removeItem(key); } catch (_) { /* Storage unavailable */ }
  }
  function showPreview(url) {
    preview.src = url;
    preview.hidden = false;
    if (currentLabel) currentLabel.hidden = false;
  }
  function clearPreview() {
    preview.removeAttribute('src');
    preview.hidden = true;
    if (currentLabel) currentLabel.hidden = true;
  }

  // Reloading after POST or following a filter/style link keeps the last photo.
  // It is scoped to this tab, and is not uploaded to or stored by the server.
  if (form.dataset.hasResults !== 'true') forgetPreview();
  const saved = getSavedPreview();
  if (saved && saved.startsWith('data:image/')) showPreview(saved);

  input.addEventListener('change', () => {
    if (temporaryUrl) URL.revokeObjectURL(temporaryUrl);
    const file = input.files?.[0];
    if (!file) {
      const last = getSavedPreview();
      if (last) showPreview(last); else clearPreview();
      thumbnailTask = Promise.resolve();
      return;
    }
    // Clear the old thumbnail immediately: a new photo means a new search.
    forgetPreview();
    clearPreview();
    if (!supported.includes(file.type) || file.size > 5 * 1024 * 1024) {
      thumbnailTask = Promise.resolve();
      return;
    }

    temporaryUrl = URL.createObjectURL(file);
    const source = temporaryUrl;
    showPreview(source);
    thumbnailTask = new Promise(resolve => {
      const image = new Image();
      image.onload = () => {
        try {
          const scale = Math.min(1, 320 / Math.max(image.naturalWidth, image.naturalHeight));
          const canvas = document.createElement('canvas');
          canvas.width = Math.max(1, Math.round(image.naturalWidth * scale));
          canvas.height = Math.max(1, Math.round(image.naturalHeight * scale));
          canvas.getContext('2d').drawImage(image, 0, 0, canvas.width, canvas.height);
          const thumbnail = canvas.toDataURL('image/jpeg', 0.78);
          savePreview(thumbnail);
          showPreview(thumbnail);
        } catch (_) { /* The upload can still be processed without a preview. */ }
        URL.revokeObjectURL(source);
        if (temporaryUrl === source) temporaryUrl = null;
        resolve();
      };
      image.onerror = () => {
        URL.revokeObjectURL(source);
        if (temporaryUrl === source) temporaryUrl = null;
        clearPreview();
        resolve();
      };
      image.src = source;
    });
  });

  form.addEventListener('submit', event => {
    if (!input.files?.length) return;
    // Finish creating the small thumbnail before the browser navigates away.
    event.preventDefault();
    const submitButton = form.querySelector('button[type="submit"]');
    if (submitButton) submitButton.disabled = true;
    thumbnailTask.finally(() => form.submit());
  });
})();
