let assignSessionPk: string | null = null;
let assignDuration: number = 0;
let assignBackUrl: string | null = null;

declare const htmx: {
  ajax: (
    method: string,
    url: string,
    opts: { target: string; swap: string },
  ) => void;
};

const banner = (): HTMLElement =>
  document.getElementById("assign-mode-banner")!;

const grid = (): HTMLElement =>
  document.getElementById("timetable-grid")!;

const calendar = (): HTMLElement =>
  document.getElementById("timetable-calendar")!;

const columns = (): NodeListOf<HTMLElement> =>
  document.querySelectorAll<HTMLElement>(".timetable-column");

const csrfToken = (): string =>
  (document.querySelector("[name=csrfmiddlewaretoken]") as HTMLInputElement)
    .value;

function enterAssignMode(
  sessionPk: string,
  duration: number,
  backUrl: string | null,
): void {
  assignSessionPk = sessionPk;
  assignDuration = duration;
  assignBackUrl = backUrl;

  banner().classList.remove("hidden");
  columns().forEach((col) => col.classList.add("assign-mode-active"));
}

function exitAssignMode(): void {
  assignSessionPk = null;
  assignDuration = 0;
  assignBackUrl = null;

  banner().classList.add("hidden");
  columns().forEach((col) => col.classList.remove("assign-mode-active"));
}

// Delegate click on Assign buttons inside the left pane
document.addEventListener("click", (e) => {
  const target = e.target as Element;

  const assignBtn = target.closest<HTMLElement>("[data-assign-session-pk]");
  if (assignBtn) {
    const pk = assignBtn.dataset.assignSessionPk!;
    const duration = Number(assignBtn.dataset.assignDuration) || 60;
    const backUrl = assignBtn.dataset.assignBackUrl ?? null;
    enterAssignMode(pk, duration, backUrl);
    return;
  }

  // Grid column click during assignment mode
  if (assignSessionPk) {
    const col = target.closest<HTMLElement>(".timetable-column.assign-mode-active");
    if (col) {
      const spacePk = col.dataset.spacePk!;
      const cal = calendar();
      const eventStart = cal.dataset.eventStart!;
      const slotMinutes = Number(cal.dataset.slotMinutes);
      const slotHeight = Number(cal.dataset.slotHeight);

      const rect = col.getBoundingClientRect();
      const yOffset = e instanceof MouseEvent ? e.clientY - rect.top : 0;
      const slotIndex = Math.floor(yOffset / slotHeight);
      const offsetMinutes = slotIndex * slotMinutes;

      const startDt = new Date(eventStart);
      startDt.setMinutes(startDt.getMinutes() + offsetMinutes);
      const endDt = new Date(startDt.getTime() + assignDuration * 60_000);

      const assignUrl = grid().dataset.assignUrl!;
      const body = new FormData();
      body.append("session_pk", assignSessionPk);
      body.append("space_pk", spacePk);
      body.append("start_time", startDt.toISOString());
      body.append("end_time", endDt.toISOString());
      body.append("csrfmiddlewaretoken", csrfToken());

      const sessionPkAtClick = assignSessionPk;
      const durationAtClick = assignDuration;
      const backUrlAtClick = assignBackUrl;
      exitAssignMode();

      fetch(assignUrl, { method: "POST", body })
        .then((resp) => {
          if (resp.ok) {
            document.body.dispatchEvent(
              new CustomEvent("timetableChanged"),
            );
            if (backUrlAtClick) {
              htmx.ajax("GET", backUrlAtClick, {
                target: "#left-pane",
                swap: "outerHTML",
              });
            }
          } else {
            alert(
              `Could not place session (server returned ${resp.status}). ` +
              `Please try again.`,
            );
            enterAssignMode(sessionPkAtClick, durationAtClick, backUrlAtClick);
          }
        })
        .catch(() => {
          alert("Network error placing session. Please try again.");
          enterAssignMode(sessionPkAtClick, durationAtClick, backUrlAtClick);
        });
      return;
    }
  }
});

// Re-apply assignment mode UI after HTMX swaps the grid (e.g. room pagination).
// Module state survives HTMX swaps but DOM classes do not.
document.body.addEventListener("htmx:afterSwap", () => {
  if (assignSessionPk) {
    banner().classList.remove("hidden");
    columns().forEach((col) => col.classList.add("assign-mode-active"));
  }
});

// Keep #timetable-grid's auto-refresh URL aligned with the current browser URL,
// so an assign/unassign after pagination reloads the page the user is viewing
// (not the page that was originally rendered).
document.body.addEventListener("htmx:pushedIntoHistory", () => {
  const gridEl = grid();
  const hxGet = gridEl.getAttribute("hx-get") ?? "";
  const baseUrl = hxGet.split("?")[0];
  gridEl.setAttribute("hx-get", baseUrl + window.location.search);
});

// Cancel button — delegated so it survives HTMX swaps of any ancestor
document.addEventListener("click", (e) => {
  const target = e.target as Element;
  if (target.closest("#assign-mode-cancel")) {
    exitAssignMode();
  }
});

// Escape key
document.addEventListener("keydown", (e) => {
  if (e.key === "Escape" && assignSessionPk) {
    exitAssignMode();
  }
});
