export let language = localStorage.getItem("catchy-language") || "en";
export let languages = [];
let messages = {},
  fallback = {};
export async function loadLanguage(code = language) {
  languages = await fetch("/locales/languages.json").then((r) => r.json());
  const item = languages.find((l) => l.code === code) || languages[0];
  language = item.code;
  fallback = await fetch("/locales/en.json").then((r) => r.json());
  messages =
    item.ui === "en"
      ? fallback
      : await fetch(`/locales/${item.ui}.json`).then((r) => r.json());
  document.documentElement.lang = item.code;
  document.documentElement.dir = item.direction;
  localStorage.setItem("catchy-language", language);
  return item;
}
export function t(key) {
  return messages[key] || fallback[key] || key;
}
export function translate(root = document) {
  root.querySelectorAll("[data-t]").forEach((el) => {
    el.textContent = t(el.dataset.t);
  });
  root
    .querySelectorAll("[data-t-aria]")
    .forEach((el) => el.setAttribute("aria-label", t(el.dataset.tAria)));
}
export const languageInfo = () =>
  languages.find((l) => l.code === language) || {
    speech: "en-IN",
    status: "beta",
    ui: "en",
  };
