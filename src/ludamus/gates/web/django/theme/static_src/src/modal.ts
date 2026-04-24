interface NavigateEvent {
  canIntercept: boolean;
  hashChange: boolean;
  destination: { url: string };
  intercept: () => void;
}

interface Navigation {
  addEventListener(
    type: "navigate",
    handler: (e: NavigateEvent) => void,
  ): void;
}

/** ~16% lack Navigation API (Firefox on Android, IE11, older Safari). Click interception only in old browsers. */
const navigation = (globalThis as { navigation?: Navigation }).navigation;

const getDialog = (id: string): HTMLDialogElement => {
  const element = document.getElementById(id);
  if (!(element instanceof HTMLDialogElement)) {
    throw new Error(`Modal "${id}" is not a <dialog> element`);
  }
  return element;
};

const updateQueryParam = (
  paramName: string,
  value: string | null,
  { replaceHistory = false } = {},
): void => {
  const url = new URL(window.location.href);
  const current = url.searchParams.get(paramName);

  if (value === null) {
    if (!current) return;
    url.searchParams.delete(paramName);
  } else {
    const next = String(value);
    if (current === next) return;
    url.searchParams.set(paramName, next);
  }

  if (replaceHistory) {
    window.history.replaceState({}, "", url);
    return;
  }
  window.history.pushState({}, "", url);
};

const getLinkableByModalId = (
  id: string,
): { paramName: string; paramValue: string } | null => {
  const link = document.querySelector(`a[href][aria-controls="${id}"]`);
  if (!link) return null;

  const href = link.getAttribute("href");
  if (!href) return null;

  const hrefUrl = new URL(href, window.location.href);
  const first = hrefUrl.searchParams.entries().next();
  if (first.done) return null;

  const [paramName, paramValue] = first.value;
  return { paramName, paramValue };
};

const openModal = (
  id: string,
  { updateUrl = true, replaceHistory = false } = {},
): void => {
  const dialog = getDialog(id);
  if (!dialog.open) {
    dialog.showModal();
  }

  if (updateUrl) {
    const linkable = getLinkableByModalId(id);
    if (linkable) {
      updateQueryParam(linkable.paramName, linkable.paramValue, {
        replaceHistory,
      });
    }
  }
};

const closeModal = (
  id: string,
  { updateUrl = true, replaceHistory = true } = {},
): void => {
  const dialog = getDialog(id);
  if (dialog.open) {
    dialog.close();
  }

  if (updateUrl) {
    const linkable = getLinkableByModalId(id);
    if (!linkable) return;

    const current = new URLSearchParams(window.location.search).get(
      linkable.paramName,
    );
    if (current === linkable.paramValue) {
      updateQueryParam(linkable.paramName, null, { replaceHistory });
    }
  }
};

const syncModalsFromUrl = (): void => {
  const searchParams = new URLSearchParams(window.location.search);

  document.querySelectorAll("dialog.modal[open]").forEach((dialog) => {
    closeModal(dialog.id, { updateUrl: false });
  });

  document.querySelectorAll("a[href][aria-controls]").forEach((link) => {
    const href = link.getAttribute("href");
    const modalId = link.getAttribute("aria-controls");
    if (!href || !modalId) return;

    const target = document.getElementById(modalId);
    if (
      !(target instanceof HTMLDialogElement) ||
      !target.classList.contains("modal")
    )
      return;

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
    if (
      !(target instanceof HTMLDialogElement) ||
      !target.classList.contains("modal")
    )
      return;

    event.preventDefault();
    closeModal(target.id);
  },
  true,
);

if (navigation) {
  navigation.addEventListener("navigate", (e) => {
    if (!e.canIntercept || e.hashChange) return;

    const url = new URL(e.destination.url);
    if (url.origin !== location.origin || url.pathname !== location.pathname)
      return;

    for (const link of document.querySelectorAll("a[href][aria-controls]")) {
      const href = link.getAttribute("href");
      const modalId = link.getAttribute("aria-controls");
      if (!href || !modalId) continue;

      const hrefUrl = new URL(href, location.href);
      if (hrefUrl.pathname !== url.pathname) continue;

      const matches =
        hrefUrl.searchParams.size > 0 &&
        [...hrefUrl.searchParams].every(
          ([k, v]) => url.searchParams.get(k) === v,
        );
      if (!matches) continue;

      const target = document.getElementById(modalId);
      if (
        !(target instanceof HTMLDialogElement) ||
        !target.classList.contains("modal")
      )
        continue;

      e.intercept();
      openModal(modalId, { updateUrl: false });
      return;
    }
  });
}

document.addEventListener("click", (event) => {
  const eventTarget = event.target;
  if (!(eventTarget instanceof Element)) return;

  const closeTrigger = eventTarget.closest("[data-modal-close]");
  if (closeTrigger) {
    const id = closeTrigger.getAttribute("data-modal-close");
    if (id) {
      closeModal(id);
      return;
    }
  }

  // Fallback link interception handled by setupFallbackLinkHandlers below.

  if (
    !(eventTarget instanceof HTMLDialogElement) ||
    !eventTarget.classList.contains("modal")
  )
    return;

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

// In browsers without Navigation API (WebKit, older Firefox), attach click
// handlers directly to modal-trigger links so preventDefault fires before
// the browser starts navigation.
const setupFallbackLinkHandlers = (): void => {

  document.querySelectorAll("a[href][aria-controls]").forEach((link) => {
    const modalId = link.getAttribute("aria-controls");
    if (!modalId) return;

    const target = document.getElementById(modalId);
    if (
      !(target instanceof HTMLDialogElement) ||
      !target.classList.contains("modal")
    )
      return;

    link.addEventListener("click", (e) => {
      e.preventDefault();
      openModal(modalId);
    });
  });
};

setupFallbackLinkHandlers();

export { closeModal };
