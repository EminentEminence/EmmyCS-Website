function initializeProjectSlideshows() {
  const slideshows = document.querySelectorAll("[data-project-slideshow]");

  for (const slideshow of slideshows) {
    const slides = Array.from(slideshow.querySelectorAll(".slideshow-slide"));
    const dotsWrap = slideshow.parentElement?.querySelector(".slideshow-dots");
    const dots = dotsWrap ? Array.from(dotsWrap.querySelectorAll(".slideshow-dot")) : [];
    const prevButton = slideshow.querySelector('[data-slide="prev"]');
    const nextButton = slideshow.querySelector('[data-slide="next"]');

    if (slides.length <= 1) {
      prevButton?.setAttribute("disabled", "disabled");
      nextButton?.setAttribute("disabled", "disabled");
      continue;
    }

    const intervalMs = Number(slideshow.getAttribute("data-interval")) || 4500;
    let activeIndex = slides.findIndex((slide) => slide.classList.contains("is-active"));
    if (activeIndex < 0) {
      activeIndex = 0;
      slides[0]?.classList.add("is-active");
      dots[0]?.classList.add("is-active");
    }

    let timerId;

    function render(index) {
      activeIndex = (index + slides.length) % slides.length;
      slides.forEach((slide, i) => {
        slide.classList.toggle("is-active", i === activeIndex);
      });
      dots.forEach((dot, i) => {
        dot.classList.toggle("is-active", i === activeIndex);
      });
    }

    function next() {
      render(activeIndex + 1);
    }

    function prev() {
      render(activeIndex - 1);
    }

    function startAutoPlay() {
      stopAutoPlay();
      timerId = window.setInterval(next, intervalMs);
    }

    function stopAutoPlay() {
      if (timerId) {
        window.clearInterval(timerId);
      }
    }

    prevButton?.addEventListener("click", () => {
      prev();
      startAutoPlay();
    });

    nextButton?.addEventListener("click", () => {
      next();
      startAutoPlay();
    });

    dots.forEach((dot) => {
      dot.addEventListener("click", () => {
        const index = Number(dot.getAttribute("data-dot-index"));
        render(index);
        startAutoPlay();
      });
    });

    slideshow.addEventListener("mouseenter", stopAutoPlay);
    slideshow.addEventListener("mouseleave", startAutoPlay);
    slideshow.addEventListener("focusin", stopAutoPlay);
    slideshow.addEventListener("focusout", startAutoPlay);

    startAutoPlay();
  }
}

initializeProjectSlideshows();
