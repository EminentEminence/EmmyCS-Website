function attachCardTilt() {
  const cards = document.querySelectorAll('.tilt-card');

  cards.forEach((card) => {
    if (card.dataset.tiltBound === 'true') {
      return;
    }

    const state = {
      currentX: 0,
      currentY: 0,
      targetX: 0,
      targetY: 0,
      targetShineX: 0,
      targetShineY: 0,
      raf: null,
    };

    const render = () => {
      const maxTilt = 5;
      state.currentX += (state.targetX - state.currentX) * 0.22;
      state.currentY += (state.targetY - state.currentY) * 0.22;
      state.currentX = Math.max(-maxTilt, Math.min(maxTilt, state.currentX));
      state.currentY = Math.max(-maxTilt, Math.min(maxTilt, state.currentY));
      state.currentShineX = state.targetShineX;
      state.currentShineY = state.targetShineY;

      const foilTiltXMultiplier = 0.18;
      const foilTiltYMultiplier = 0.14;
      const foilTiltX = state.currentX * foilTiltXMultiplier;
      const foilTiltY = state.currentY * foilTiltYMultiplier;

      card.style.setProperty('--tilt-x', `${state.currentX}deg`);
      card.style.setProperty('--tilt-y', `${state.currentY}deg`);
      card.style.setProperty('--art-tilt-x', `${state.currentX * 0.7}deg`);
      card.style.setProperty('--art-tilt-y', `${state.currentY * 0.7}deg`);
      card.style.setProperty('--foil-tilt-x', `${foilTiltX}deg`);
      card.style.setProperty('--foil-tilt-y', `${foilTiltY}deg`);
      card.style.setProperty('--shine-x', `${state.currentShineX}px`);
      card.style.setProperty('--shine-y', `${state.currentShineY}px`);

      if (Math.abs(state.targetX - state.currentX) > 0.01 || Math.abs(state.targetY - state.currentY) > 0.01) {
        state.raf = requestAnimationFrame(render);
      } else {
        state.raf = null;
      }
    };

    const reset = () => {
      state.targetX = 0;
      state.targetY = 0;
      state.targetShineX = 0;
      state.targetShineY = 0;
      if (!state.raf) {
        state.raf = requestAnimationFrame(render);
      }
    };

    card.addEventListener('pointermove', (event) => {
      const rect = card.getBoundingClientRect();
      const px = (event.clientX - rect.left) / rect.width;
      const py = (event.clientY - rect.top) / rect.height;
      const dx = px - 0.5;
      const dy = py - 0.5;
      const centerDistance = Math.min(1, Math.hypot(dx, dy) * 2.2);
      const centerBoost = 1 + (1 - centerDistance) * 4.5;
      const maxTilt = 2;
      const rotateY = Math.max(-maxTilt, Math.min(maxTilt, dx * 18 * centerBoost));
      const rotateX = Math.max(-maxTilt, Math.min(maxTilt, -dy * 18 * centerBoost));
      const shineX = dx * 28;
      const shineY = dy * 22;

      state.targetX = rotateX;
      state.targetY = rotateY;
      state.targetShineX = shineX;
      state.targetShineY = shineY;

      if (!state.raf) {
        state.raf = requestAnimationFrame(render);
      }
    });

    card.addEventListener('pointerleave', reset);
    card.addEventListener('pointercancel', reset);
    card.addEventListener('pointerout', reset);
    card.dataset.tiltBound = 'true';
    reset();
  });
}

document.addEventListener('DOMContentLoaded', () => {
  attachCardTilt();
});

window.addEventListener('load', () => {
  attachCardTilt();
});
