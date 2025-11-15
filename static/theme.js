(() => {
  const STORAGE_KEY = "nexus-theme";
  const body = document.body;
  const toggle = document.querySelector("[data-theme-toggle]");

  if (!toggle) {
    return;
  }

  const prefersDark = window.matchMedia("(prefers-color-scheme: dark)");

  function applyTheme(theme) {
    body.setAttribute("data-theme", theme);
    toggle.textContent = theme === "dark" ? "Light mode" : "Dark mode";
  }

  function currentTheme() {
    return body.getAttribute("data-theme") || "dark";
  }

  const saved = localStorage.getItem(STORAGE_KEY);
  const initial = saved || (prefersDark.matches ? "dark" : "light");
  applyTheme(initial);

  toggle.addEventListener("click", () => {
    const nextTheme = currentTheme() === "dark" ? "light" : "dark";
    applyTheme(nextTheme);
    localStorage.setItem(STORAGE_KEY, nextTheme);
  });

  prefersDark.addEventListener("change", (event) => {
    if (!localStorage.getItem(STORAGE_KEY)) {
      applyTheme(event.matches ? "dark" : "light");
    }
  });
})();

