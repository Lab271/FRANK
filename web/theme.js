// The Lab271 tokens theme on data-theme. Choice (auto|light|dark) lives in
// localStorage; auto follows the OS setting. A classic script in <head>, so
// the theme is set before the first paint; a file, not inline, so the CSP
// needs no 'unsafe-inline' (#244).
const dark = matchMedia("(prefers-color-scheme: dark)");
const modes = ["auto", "light", "dark"];
let mode = "auto";
try { mode = localStorage.getItem("frank.theme") || "auto"; } catch { /* no storage */ }
if (!modes.includes(mode)) mode = "auto";
const theme = () => {
  document.documentElement.dataset.theme = mode === "auto" ? (dark.matches ? "dark" : "light") : mode;
  const b = document.getElementById("theme");
  if (b) b.textContent = "theme: " + mode;
};
theme(); dark.addEventListener("change", theme);
// On document, not window: Obscura (the browser tests) does not always
// pass DOMContentLoaded on to window.
document.addEventListener("DOMContentLoaded", () => {
  theme();
  document.getElementById("theme").addEventListener("click", () => {
    mode = modes[(modes.indexOf(mode) + 1) % modes.length];
    try { localStorage.setItem("frank.theme", mode); } catch { /* no storage */ }
    theme();
  });
});
