async function loadItems() {
  const items = await window.__TAURI_INTERNALS__.invoke('load_items', {});
  const list = document.getElementById('items');
  list.innerHTML = '';
  (items || []).forEach((item) => {
    const li = document.createElement('li');
    li.textContent = item.label;
    list.appendChild(li);
  });
}

async function saveNote() {
  const text = document.getElementById('note-text').value;
  try {
    await window.__TAURI_INTERNALS__.invoke('save_note', { text });
    // Planted bug (A-36): a successful save is never distinguished from a swallowed
    // failure in the UI either -- there is no success feedback path here on purpose,
    // matching the "no UI feedback" bug this fixture exists to expose.
  } catch (err) {
    // Planted bug (A-36): the rejection is swallowed into console.error with no UI
    // feedback -- the user sees nothing happen when save_note fails server-side.
    console.error(err);
  }
}

document.getElementById('load-items').addEventListener('click', loadItems);
document.getElementById('save-note-button').addEventListener('click', saveNote);
