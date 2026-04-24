let assignSessionPk: string | null = null;
let assignDuration: number = 0;

const banner = (): HTMLElement =>
  document.getElementById("assign-mode-banner")!;

const drawer = (): HTMLElement =>
  document.getElementById("session-drawer")!;

const grid = (): HTMLElement =>
  document.getElementById("timetable-grid")!;

const calendar = (): HTMLElement =>
  document.getElementById("timetable-calendar")!;

const columns = (): NodeListOf<HTMLElement> =>
  document.querySelectorAll<HTMLElement>(".timetable-column");

const csrfToken = (): string =>
  (document.querySelector("[name=csrfmiddlewaretoken]") as HTMLInputElement)
    .value;

function enterAssignMode(sessionPk: string, duration: number): void {
  assignSessionPk = sessionPk;
  assignDuration = duration;

  banner().classList.remove("hidden");
  drawer().classList.add("hidden");
  columns().forEach((col) => col.classList.add("assign-mode-active"));
}

function exitAssignMode(): void {
  assignSessionPk = null;
  assignDuration = 0;

  banner().classList.add("hidden");
  columns().forEach((col) => col.classList.remove("assign-mode-active"));
}

// Delegate click on Assign buttons inside the drawer
document.addEventListener("click", (e) => {
  const target = e.target as Element;

  const assignBtn = target.closest<HTMLElement>("[data-assign-session-pk]");
  if (assignBtn) {
    const pk = assignBtn.dataset.assignSessionPk!;
    const duration = Number(assignBtn.dataset.assignDuration) || 60;
    enterAssignMode(pk, duration);
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

      exitAssignMode();

      fetch(assignUrl, { method: "POST", body })
        .then((resp) => {
          if (resp.ok) {
            document.body.dispatchEvent(
              new CustomEvent("timetableChanged"),
            );
          }
        });
      return;
    }
  }
});

// Cancel button
document.getElementById("assign-mode-cancel")?.addEventListener("click", () => {
  exitAssignMode();
});

// Escape key
document.addEventListener("keydown", (e) => {
  if (e.key === "Escape" && assignSessionPk) {
    exitAssignMode();
  }
});
