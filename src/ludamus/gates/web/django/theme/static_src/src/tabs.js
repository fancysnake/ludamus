// @ts-check

/**
 * Generic tabs — driven by `aria-controls` on triggers and `id` on panels.
 *
 * Usage:
 *   <div class="tab-list" role="tablist">
 *     <button class="tab-trigger" role="tab" aria-selected="true"  aria-controls="panel-a">A</button>
 *     <button class="tab-trigger" role="tab" aria-selected="false" aria-controls="panel-b">B</button>
 *   </div>
 *   <div class="tab-content">
 *     <div class="tab-panel" role="tabpanel" id="panel-a" data-active>…</div>
 *     <div class="tab-panel" role="tabpanel" id="panel-b" inert>…</div>
 *   </div>
 */
/** @param {Element} trigger */
function activateTab(trigger) {
  const tablist = trigger.closest(".tab-list");
  if (!tablist) return;

  const panelId = trigger.getAttribute("aria-controls");
  if (!panelId) return;

  tablist.querySelectorAll(".tab-trigger").forEach((t) => {
    t.setAttribute("aria-selected", "false");
    t.setAttribute("tabindex", "-1");
    const id = t.getAttribute("aria-controls");
    const panel = id && document.getElementById(id);
    if (panel) {
      panel.removeAttribute("data-active");
      panel.setAttribute("inert", "");
    }
  });

  trigger.setAttribute("aria-selected", "true");
  trigger.setAttribute("tabindex", "0");
  const active = document.getElementById(panelId);
  if (active) {
    active.setAttribute("data-active", "");
    active.removeAttribute("inert");
  }
  /** @type {HTMLElement} */ (trigger).focus();
}

document.addEventListener("click", (e) => {
  const trigger = /** @type {Element | null} */ (e.target)?.closest(".tab-trigger");
  if (trigger) activateTab(trigger);
});

document.addEventListener("keydown", (e) => {
  const trigger = /** @type {Element | null} */ (e.target)?.closest(".tab-trigger");
  if (!trigger) return;

  const tablist = trigger.closest(".tab-list");
  if (!tablist) return;

  const tabs = /** @type {HTMLElement[]} */ ([...tablist.querySelectorAll(".tab-trigger")]);
  const idx = tabs.indexOf(/** @type {HTMLElement} */ (trigger));

  let next = -1;
  if (e.key === "ArrowRight") next = (idx + 1) % tabs.length;
  else if (e.key === "ArrowLeft") next = (idx - 1 + tabs.length) % tabs.length;
  else if (e.key === "Home") next = 0;
  else if (e.key === "End") next = tabs.length - 1;
  else return;

  e.preventDefault();
  activateTab(tabs[next]);
});
