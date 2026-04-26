// src/tabs.ts
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
  trigger.focus();
}
document.addEventListener("click", (e) => {
  const trigger = e.target?.closest(".tab-trigger");
  if (trigger) activateTab(trigger);
});
document.addEventListener("keydown", (e) => {
  const trigger = e.target?.closest(".tab-trigger");
  if (!trigger) return;
  const tablist = trigger.closest(".tab-list");
  if (!tablist) return;
  const tabs = [...tablist.querySelectorAll(".tab-trigger")];
  const idx = tabs.indexOf(trigger);
  let next = -1;
  if (e.key === "ArrowRight") next = (idx + 1) % tabs.length;
  else if (e.key === "ArrowLeft") next = (idx - 1 + tabs.length) % tabs.length;
  else if (e.key === "Home") next = 0;
  else if (e.key === "End") next = tabs.length - 1;
  else return;
  e.preventDefault();
  activateTab(tabs[next]);
});
