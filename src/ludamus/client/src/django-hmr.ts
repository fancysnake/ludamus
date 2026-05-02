/// <reference types="vite/client" />

if (import.meta.hot) {
  import.meta.hot.on("django-template-reload", () => {
    window.location.reload();
  });
}
