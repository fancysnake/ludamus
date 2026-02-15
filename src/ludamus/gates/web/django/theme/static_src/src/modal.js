// @ts-check

/**
 * @typedef {{
 *  addEventListener: (type: 'navigate', handler: (e: { canIntercept: boolean, hashChange: boolean, destination: { url: string }, intercept: () => void }) => void) => void }} Navigation
 */

/** ~16% lack Navigation API (Firefox on Android, IE11, older Safari). Click interception only in old browsers. */
const navigation = /** @type {{ navigation?: Navigation }} */ (globalThis).navigation;

/**
 * @param {string} id
 * @returns {HTMLDialogElement}
 */
const getDialog = (id) => {
  const element = document.getElementById(id);
  if (!(element instanceof HTMLDialogElement)) {
    throw new Error(`Modal "${id}" is not a <dialog> element`);
  }
  return element;
};

/**
 * @param {string} paramName
 * @param {string | null} value
 * @param {{ replaceHistory?: boolean }} [options]
 * @returns void
 */
const updateQueryParam = (paramName, value, { replaceHistory = false } = {}) => {
  const url = new URL(window.location.href);
  const current = url.searchParams.get(paramName);

  if (value === null) {
    if (!current) {
      return;
    }
    url.searchParams.delete(paramName);
  } else {
    const next = String(value);
    if (current === next) {
      return;
    }
    url.searchParams.set(paramName, next);
  }

  if (replaceHistory) {
    window.history.replaceState({}, "", url);
    return;
  }
  window.history.pushState({}, "", url);
};

/**
 * @param {string} id
 * @returns {{ paramName: string, paramValue: string } | null}
 */
const getLinkableByModalId = (id) => {
  const link = document.querySelector(`a[href][aria-controls="${id}"]`);
  if (!link) {
    return null;
  }
  const href = link.getAttribute("href");
  if (!href) {
    return null;
  }
  const hrefUrl = new URL(href, window.location.href);
  const first = hrefUrl.searchParams.entries().next();
  if (first.done) {
    return null;
  }
  const [paramName, paramValue] = first.value;
  return { paramName, paramValue };
};

/**
 * @param {string} id
 * @param {{ updateUrl?: boolean, replaceHistory?: boolean }} [options]
 * @returns void
 */
const openModal = (id, { updateUrl = true, replaceHistory = false } = {}) => {
  const dialog = getDialog(id);
  if (!dialog.open) {
    dialog.showModal();
  }

  if (updateUrl) {
    const linkable = getLinkableByModalId(id);
    if (linkable) {
      updateQueryParam(linkable.paramName, linkable.paramValue, { replaceHistory });
    }
  }
};

/**
 * 
 * @param {string} id 
 * @param {{ updateUrl?: boolean, replaceHistory?: boolean }} [options]
 * @returns void
 */
const closeModal = (id, { updateUrl = true, replaceHistory = false } = {}) => {
  const dialog = getDialog(id);
  if (dialog.open) {
    dialog.close();
  }

  if (updateUrl) {
    const linkable = getLinkableByModalId(id);
    if (!linkable) {
      return;
    }
    const current = new URLSearchParams(window.location.search).get(linkable.paramName);
    if (current === linkable.paramValue) {
      updateQueryParam(linkable.paramName, null, { replaceHistory });
    }
  }
};

const syncModalsFromUrl = () => {
  const searchParams = new URLSearchParams(window.location.search);

  document.querySelectorAll("dialog.modal[open]").forEach((dialog) => {
    closeModal(dialog.id, { updateUrl: false });
  });

  document.querySelectorAll("a[href][aria-controls]").forEach((link) => {
    const href = link.getAttribute("href");
    const modalId = link.getAttribute("aria-controls");
    if (!href || !modalId) {
      return;
    }
    const target = document.getElementById(modalId);
    if (!(target instanceof HTMLDialogElement) || !target.classList.contains("modal")) {
      return;
    }
    const hrefUrl = new URL(href, window.location.href);
    for (const [paramName, paramValue] of hrefUrl.searchParams) {
      if (searchParams.get(paramName) === paramValue) {
        openModal(modalId, { updateUrl: false });
        return;
      }
    }
  });
};

document.addEventListener(
  "cancel",
  (event) => {
    const target = event.target;
    if (!(target instanceof HTMLDialogElement) || !target.classList.contains("modal")) {
      return;
    }
    event.preventDefault();
    closeModal(target.id);
  },
  true,
);

if (navigation) {
  navigation.addEventListener("navigate", (e) => {
    if (!e.canIntercept || e.hashChange) {
      return;
    }
    const url = new URL(e.destination.url);
    if (url.origin !== location.origin || url.pathname !== location.pathname) {
      return;
    }

    for (const link of document.querySelectorAll("a[href][aria-controls]")) {
      const href = link.getAttribute("href");
      const modalId = link.getAttribute("aria-controls");
      if (!href || !modalId) {
        continue;
      }
      const hrefUrl = new URL(href, location.href);
      if (hrefUrl.pathname !== url.pathname) {
        continue;
      }
      const matches =
        hrefUrl.searchParams.size > 0 &&
        [...hrefUrl.searchParams].every(([k, v]) => url.searchParams.get(k) === v);
      if (!matches) {
        continue;
      }
      const target = document.getElementById(modalId);
      if (!(target instanceof HTMLDialogElement) || !target.classList.contains("modal")) {
        continue;
      }
      e.intercept();
      openModal(modalId, { updateUrl: false });
      return;
    }
  });
}

document.addEventListener("click", (event) => {
  const eventTarget = event.target;
  if (!(eventTarget instanceof Element)) {
    return;
  }

  const closeTrigger = eventTarget.closest("[data-modal-close]");
  if (closeTrigger) {
    const id = closeTrigger.getAttribute("data-modal-close");
    if (id) {
      closeModal(id);
      return;
    }
  }

  // Fallback to click interception in Firefox on Android, IE11, older Safari.
  if (!navigation) {
    const link = eventTarget.closest("a[href][aria-controls]");
    if (link instanceof HTMLAnchorElement) {
      const modalId = link.getAttribute("aria-controls");
      if (modalId) {
        const target = document.getElementById(modalId);
        if (target instanceof HTMLDialogElement && target.classList.contains("modal")) {
          event.preventDefault();
          openModal(modalId);
          return;
        }
      }
    }
  }

  if (!(eventTarget instanceof HTMLDialogElement) || !eventTarget.classList.contains("modal")) {
    return;
  }

  const rect = eventTarget.getBoundingClientRect();
  const isInside =
    event.clientX >= rect.left &&
    event.clientX <= rect.right &&
    event.clientY >= rect.top &&
    event.clientY <= rect.bottom;

  if (!isInside) closeModal(eventTarget.id);
});

window.addEventListener("popstate", syncModalsFromUrl);

syncModalsFromUrl();

export { closeModal };

