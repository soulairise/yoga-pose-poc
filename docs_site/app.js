const slides = [...document.querySelectorAll(".slide")];
const currentNumber = document.getElementById("currentNumber");
const totalNumber = document.getElementById("totalNumber");
const progressBar = document.getElementById("progressBar");
const chapterPill = document.getElementById("chapterPill");
const slideTitle = document.getElementById("slideTitle");
const prevButton = document.getElementById("prevButton");
const nextButton = document.getElementById("nextButton");
const notesButton = document.getElementById("notesButton");
const themeButton = document.getElementById("themeButton");
const fullscreenButton = document.getElementById("fullscreenButton");
const overviewButton = document.getElementById("overviewButton");
const overviewDialog = document.getElementById("overviewDialog");
const overviewClose = document.getElementById("overviewClose");
const overviewGrid = document.getElementById("overviewGrid");

let index = Math.max(0, Math.min(slides.length - 1, Number(location.hash.replace("#slide-", "")) - 1 || 0));
let touchStartX = 0;

totalNumber.textContent = String(slides.length).padStart(2, "0");

const savedTheme = localStorage.getItem("deck-theme");
if (savedTheme) document.documentElement.dataset.theme = savedTheme;

function showSlide(nextIndex, updateHash = true) {
  index = Math.max(0, Math.min(slides.length - 1, nextIndex));
  slides.forEach((slide, slideIndex) => {
    const active = slideIndex === index;
    slide.classList.toggle("active", active);
    slide.setAttribute("aria-hidden", String(!active));
  });

  const activeSlide = slides[index];
  currentNumber.textContent = String(index + 1).padStart(2, "0");
  progressBar.style.width = `${((index + 1) / slides.length) * 100}%`;
  chapterPill.textContent = activeSlide.dataset.chapter;
  slideTitle.textContent = activeSlide.dataset.title;
  prevButton.disabled = index === 0;
  nextButton.disabled = index === slides.length - 1;
  document.title = `${activeSlide.dataset.title} | 요가 아사나 반복 판정 PoC`;

  if (updateHash) history.replaceState(null, "", `#slide-${index + 1}`);
  overviewGrid.querySelectorAll("button").forEach((button, buttonIndex) => {
    button.classList.toggle("current", buttonIndex === index);
  });
}

function toggleNotes() {
  const visible = document.body.classList.toggle("show-notes");
  notesButton.setAttribute("aria-pressed", String(visible));
}

function toggleTheme() {
  const current = document.documentElement.dataset.theme;
  const next = current === "dark" ? "light" : "dark";
  document.documentElement.dataset.theme = next;
  localStorage.setItem("deck-theme", next);
}

slides.forEach((slide, slideIndex) => {
  const button = document.createElement("button");
  button.innerHTML = `<b>${String(slideIndex + 1).padStart(2, "0")}</b><span>${slide.dataset.chapter}</span><strong>${slide.dataset.title}</strong>`;
  button.addEventListener("click", () => {
    showSlide(slideIndex);
    overviewDialog.close();
  });
  overviewGrid.appendChild(button);
});

document.querySelectorAll(".reveal-button").forEach((button) => {
  button.addEventListener("click", () => {
    const target = document.getElementById(button.dataset.reveal);
    const revealed = target.classList.toggle("revealed");
    button.textContent = revealed ? "정답 닫기" : button.classList.contains("large") ? "모범답안 열기" : "정답 보기";
    button.setAttribute("aria-expanded", String(revealed));
  });
});

prevButton.addEventListener("click", () => showSlide(index - 1));
nextButton.addEventListener("click", () => showSlide(index + 1));
notesButton.addEventListener("click", toggleNotes);
themeButton.addEventListener("click", toggleTheme);
overviewButton.addEventListener("click", () => overviewDialog.showModal());
overviewClose.addEventListener("click", () => overviewDialog.close());
fullscreenButton.addEventListener("click", () => {
  if (!document.fullscreenElement) document.documentElement.requestFullscreen?.();
  else document.exitFullscreen?.();
});

overviewDialog.addEventListener("click", (event) => {
  if (event.target === overviewDialog) overviewDialog.close();
});

document.addEventListener("keydown", (event) => {
  if (event.target.matches("summary, button") && ["Enter", " "].includes(event.key)) return;
  if (["ArrowRight", "PageDown", " "].includes(event.key)) {
    event.preventDefault();
    showSlide(index + 1);
  } else if (["ArrowLeft", "PageUp"].includes(event.key)) {
    event.preventDefault();
    showSlide(index - 1);
  } else if (event.key === "Home") {
    showSlide(0);
  } else if (event.key === "End") {
    showSlide(slides.length - 1);
  } else if (event.key.toLowerCase() === "o") {
    overviewDialog.open ? overviewDialog.close() : overviewDialog.showModal();
  } else if (event.key.toLowerCase() === "n") {
    toggleNotes();
  } else if (event.key.toLowerCase() === "t") {
    toggleTheme();
  } else if (event.key === "Escape" && overviewDialog.open) {
    overviewDialog.close();
  }
});

document.addEventListener("touchstart", (event) => {
  touchStartX = event.changedTouches[0].screenX;
}, { passive: true });

document.addEventListener("touchend", (event) => {
  const delta = event.changedTouches[0].screenX - touchStartX;
  if (Math.abs(delta) > 60) showSlide(index + (delta < 0 ? 1 : -1));
}, { passive: true });

window.addEventListener("hashchange", () => {
  const hashIndex = Number(location.hash.replace("#slide-", "")) - 1;
  if (Number.isFinite(hashIndex)) showSlide(hashIndex, false);
});

showSlide(index, false);
