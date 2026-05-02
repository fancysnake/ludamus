const start = document.getElementById(
  "id_start_time",
) as HTMLInputElement | null;
const end = document.getElementById(
  "id_end_time",
) as HTMLInputElement | null;

const DEFAULT_DURATION_HOURS = 3;

const pad = (n: number): string => String(n).padStart(2, "0");

const toLocalDatetimeValue = (d: Date): string =>
  `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}` +
  `T${pad(d.getHours())}:${pad(d.getMinutes())}`;

if (start && end) {
  start.addEventListener("change", () => {
    if (end.value || !start.value) return;
    const d = new Date(start.value);
    if (Number.isNaN(d.getTime())) return;
    d.setHours(d.getHours() + DEFAULT_DURATION_HOURS);
    end.value = toLocalDatetimeValue(d);
  });
}

const formatBytes = (bytes: number): string => {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
};

const initDropzone = (label: HTMLLabelElement): void => {
  const input = label.querySelector<HTMLInputElement>("[data-dropzone-input]");
  const empty = label.querySelector<HTMLElement>("[data-dropzone-empty]");
  const selected = label.querySelector<HTMLElement>("[data-dropzone-selected]");
  const nameEl = label.querySelector<HTMLElement>("[data-dropzone-name]");
  const sizeEl = label.querySelector<HTMLElement>("[data-dropzone-size]");
  const preview = label.querySelector<HTMLImageElement>(
    "[data-dropzone-preview]",
  );
  const clearBtn = label.querySelector<HTMLButtonElement>(
    "[data-dropzone-clear]",
  );
  if (!input || !empty || !selected || !nameEl || !sizeEl || !clearBtn) return;

  let previewUrl: string | null = null;
  const revokePreview = (): void => {
    if (previewUrl) {
      URL.revokeObjectURL(previewUrl);
      previewUrl = null;
    }
  };

  const showFile = (file: File): void => {
    nameEl.textContent = file.name;
    sizeEl.textContent = formatBytes(file.size);
    if (preview && file.type.startsWith("image/")) {
      revokePreview();
      previewUrl = URL.createObjectURL(file);
      preview.src = previewUrl;
    }
    empty.classList.add("hidden");
    selected.classList.remove("hidden");
  };

  const showEmpty = (): void => {
    revokePreview();
    selected.classList.add("hidden");
    empty.classList.remove("hidden");
  };

  input.addEventListener("change", () => {
    const file = input.files?.[0];
    if (file) showFile(file);
    else showEmpty();
  });

  clearBtn.addEventListener("click", (e) => {
    e.preventDefault();
    e.stopPropagation();
    input.value = "";
    showEmpty();
  });

  const setDragover = (on: boolean): void => {
    label.classList.toggle("border-primary", on);
    label.classList.toggle("bg-primary-light", on);
  };

  label.addEventListener("dragover", (e) => {
    e.preventDefault();
    setDragover(true);
  });
  label.addEventListener("dragleave", (e) => {
    if (e.target === label) setDragover(false);
  });
  label.addEventListener("drop", (e) => {
    e.preventDefault();
    setDragover(false);
    const file = e.dataTransfer?.files?.[0];
    if (!file) return;
    const dt = new DataTransfer();
    dt.items.add(file);
    input.files = dt.files;
    input.dispatchEvent(new Event("change", { bubbles: true }));
  });
};

document
  .querySelectorAll<HTMLLabelElement>("[data-dropzone]")
  .forEach(initDropzone);
