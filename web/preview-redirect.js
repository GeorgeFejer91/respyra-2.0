if (location.protocol === 'file:') {
  const livePreview = 'http://127.0.0.1:8765/experiment-hub-preview.html';
  fetch(livePreview, { mode: 'no-cors', cache: 'no-store' })
    .then(() => location.replace(livePreview))
    .catch(() => {});
} else location.replace('./index.html?preview=1');
