/**
 * Universal Form Persistence - Multi-page/sessionStorage
 * Supports checkboxes, radios, selects across pages
 * Auto-generates page keys, validates restores, tiny footprint
 */

// Config: Change per page/app section
const PERSIST_CONFIG = {
  storageKey: 'formStates',  // Base key
  pageId: window.location.pathname.replace(/\//g, '_') || 'home',  // Auto-page ID
  debug: false  // Set true to console.log saves/restores
};

// Get elements
const checkboxes = document.querySelectorAll('input[type="checkbox"]');
const radios = document.querySelectorAll('input[type="radio"]');
const selects = document.querySelectorAll('select');

// Full key for this page
const fullKey = `${PERSIST_CONFIG.storageKey}_${PERSIST_CONFIG.pageId}`;

// Collect state for both sessionStorage + backend sync
function collectFormState() {
  const state = { checkboxes: {}, radios: {}, selects: {} };

  checkboxes.forEach(cb => {
    if (cb.id) state.checkboxes[cb.id] = cb.checked;
  });
<<<<<<< HEAD

  const radioGroups = {};
=======
  
  // Radios: selected value per name group
 const radioGroups = {};
>>>>>>> d561d6edf2de1d533eefecc9c2ef8d1490b22ec3
  radios.forEach(r => {
    if (r.checked && r.name && r.id) {
      radioGroups[r.name] = r.value;
    }
  });
  Object.assign(state.radios, radioGroups);
<<<<<<< HEAD

  selects.forEach(s => {
=======
  
  // Selects by ID (only if changed from default)
 selects.forEach(s => {
>>>>>>> d561d6edf2de1d533eefecc9c2ef8d1490b22ec3
    if (s.id) state.selects[s.id] = s.value;
  });

  return state;
}

async function syncToBackend(state, isFinal = false) {
  try {
    const endpoint = isFinal ? '/submit-final' : '/save-step';
    const payload = isFinal
      ? { finalData: state }
      : { pageId: PERSIST_CONFIG.pageId, formData: state };

    await fetch(endpoint, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    });
  } catch (err) {
    if (PERSIST_CONFIG.debug) {
      console.warn('Backend sync failed:', err);
    }
  }
}

// Save handler
function saveFormState() {
  if (typeof(Storage) === 'undefined') return;

  const state = collectFormState();
  sessionStorage.setItem(fullKey, JSON.stringify(state));
  syncToBackend(state, false);

  if (PERSIST_CONFIG.debug) {
    console.log(`✅ Saved ${fullKey}:`, state);
  }
}

// Restore handler
function restoreFormState() {
  if (typeof(Storage) === 'undefined') return;
  
  const saved = sessionStorage.getItem(fullKey);
  if (!saved) return;
  
  const state = JSON.parse(saved);
  
  // Checkboxes
  checkboxes.forEach(cb => {
    if (cb.id && state.checkboxes[cb.id] !== undefined) {
      cb.checked = state.checkboxes[cb.id];
    }
  });
  
  // Radios
  radios.forEach(r => {
    if (r.name && state.radios[r.name] === r.value) {
      r.checked = true;
    }
  });
  
  // Selects - VALIDATED restore
  selects.forEach(s => {
    if (s.id && state.selects[s.id]) {
      const option = s.querySelector(`option[value="${state.selects[s.id]}"]`);
      if (option) {
        s.value = state.selects[s.id];
      } else if (PERSIST_CONFIG.debug) {
        console.warn(`⚠️ Invalid select value "${state.selects[s.id]}" for #${s.id}`);
      }
    }
  });
  
  if (PERSIST_CONFIG.debug) {
    console.log(`🔄 Restored ${fullKey}:`, state);
  }
}

// Auto-bind events
function initPersistence() {
  checkboxes.forEach(cb => cb.addEventListener('change', saveFormState));
  radios.forEach(r => r.addEventListener('change', saveFormState));
  selects.forEach(s => s.addEventListener('change', saveFormState));

  // Restore immediately
  restoreFormState();

  const continueBtn = document.getElementById('continueBtn');
  if (continueBtn) {
    continueBtn.addEventListener('click', async (e) => {
      e.preventDefault();
      saveFormState();

      const state = collectFormState();
      await syncToBackend(state, false);

<<<<<<< HEAD
=======
      const isValid = window.FormValidator.validateForm();
      if (!isValid) {
        window.FormValidator.scrollToFirstError();
        return;
      }

>>>>>>> d561d6edf2de1d533eefecc9c2ef8d1490b22ec3
      const nextUrl = continueBtn.dataset.nextUrl || continueBtn.getAttribute('href');
      if (nextUrl) {
        window.location.href = nextUrl;
      }
    });
  }

  const finalSubmitBtn = document.getElementById('finalSubmitBtn');
  if (finalSubmitBtn) {
    finalSubmitBtn.addEventListener('click', async (e) => {
      e.preventDefault();
      const state = collectFormState();
      await syncToBackend(state, true);
      const nextUrl = finalSubmitBtn.dataset.nextUrl || finalSubmitBtn.getAttribute('href');
      if (nextUrl) {
        window.location.href = nextUrl;
      }
    });
  }
}

// Init when DOM ready
if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', initPersistence);
} else {
  initPersistence();
}

// Export for manual use (optional)
window.persistForm = { save: saveFormState, restore: restoreFormState };

window.addEventListener('beforeunload', function () {
<<<<<<< HEAD
=======
  
>>>>>>> d561d6edf2de1d533eefecc9c2ef8d1490b22ec3
  navigator.sendBeacon('/clear-session');
});
