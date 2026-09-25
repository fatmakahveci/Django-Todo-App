// Modified shortcuts leave ordinary typing and assistive navigation untouched.
document.addEventListener("keydown", (event) => {
  if (!event.altKey || !event.shiftKey || event.ctrlKey || event.metaKey || event.repeat || event.isComposing || event.defaultPrevented) return;
  if (event.target?.closest?.("input, textarea, select, [contenteditable]:not([contenteditable='false'])")) return;
  const targetId = { KeyN: "quick-title", KeyF: "search" }[event.code];
  const field = targetId && document.getElementById(targetId);
  if (!field) return;
  event.preventDefault();
  field.focus();
});
