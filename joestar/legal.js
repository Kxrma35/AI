import { BUSINESS, POLICY_LAST_UPDATED } from "./legal-config.js";

// Fill every [data-biz="key"] element with the configured business detail.
document.querySelectorAll("[data-biz]").forEach((el) => {
  const value = (BUSINESS[el.dataset.biz] || "").trim();
  if (value) {
    el.textContent = value;
    if (el.dataset.biz === "email" && el.tagName === "A") el.href = `mailto:${value}`;
  } else {
    el.textContent = "[to be provided]";
    el.classList.add("todo");
  }
});
document.querySelectorAll("[data-updated]").forEach((el) => { el.textContent = POLICY_LAST_UPDATED; });
