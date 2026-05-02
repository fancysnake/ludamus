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

  input.addEventListener("change", () => {
    const file = input.files?.[0];
    if (!file) {
      revokePreview();
      selected.classList.add("hidden");
      empty.classList.remove("hidden");
      return;
    }
    nameEl.textContent = file.name;
    sizeEl.textContent = formatBytes(file.size);
    if (preview && file.type.startsWith("image/")) {
      revokePreview();
      previewUrl = URL.createObjectURL(file);
      preview.src = previewUrl;
    }
    empty.classList.add("hidden");
    selected.classList.remove("hidden");
  });

  clearBtn.addEventListener("click", (e) => {
    e.preventDefault();
    e.stopPropagation();
    input.value = "";
    input.dispatchEvent(new Event("change", { bubbles: true }));
  });
};

document
  .querySelectorAll<HTMLLabelElement>("[data-dropzone]")
  .forEach(initDropzone);
