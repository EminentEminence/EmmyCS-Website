const root = document.documentElement;
const toggle = document.getElementById("theme-toggle");
const storageKey = "portfolio-theme";

function detectPreferredTheme() {
  return window.matchMedia("(prefers-color-scheme: dark)").matches
    ? "dark"
    : "light";
}

function setTheme(theme) {
  root.setAttribute("data-theme", theme);
  window.localStorage.setItem(storageKey, theme);
}

function initializeTheme() {
  const savedTheme = window.localStorage.getItem(storageKey);
  const initialTheme = savedTheme || detectPreferredTheme();
  setTheme(initialTheme);
}

function toggleTheme() {
  const activeTheme = root.getAttribute("data-theme") || "light";
  setTheme(activeTheme === "light" ? "dark" : "light");
}

initializeTheme();

toggle?.addEventListener("click", toggleTheme);
