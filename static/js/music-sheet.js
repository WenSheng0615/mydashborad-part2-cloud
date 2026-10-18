// Owns the modal gesture only; playback remains in music.js.
window.createMusicSheet = ({sheet, grip, cover}) => {
    const mobile = matchMedia('(max-width:768px)');
    const reduced = matchMedia('(prefers-reduced-motion:reduce)');
    let motion = null, gesture = null, closing = false, suppressClick = false;

    const atTop = () => sheet.classList.toggle('sheet-at-top', sheet.scrollTop <= 1);
    function offset(y) {
        sheet.style.setProperty('--sheet-y', `${y}px`);
        sheet.style.setProperty('--sheet-dim', String(Math.max(.2, .8 - y / Math.max(1, sheet.offsetHeight) * .6)));
    }
    function stopMotion() { if (motion) { motion.cancel(); motion = null; } }
    function releaseGesture() {
        const previous = gesture;
        gesture = null;
        sheet.classList.remove('sheet-dragging');
        if (previous?.target.hasPointerCapture(previous.id)) previous.target.releasePointerCapture(previous.id);
    }
    function animate(from, to, duration, finish) {
        stopMotion();
        if (reduced.matches || typeof sheet.animate !== 'function') { finish(); return; }
        const animation = sheet.animate([{transform:from}, {transform:to}], {
            duration, easing:'cubic-bezier(.22,.8,.25,1)', fill:'forwards'
        });
        motion = animation;
        animation.onfinish = () => {
            if (motion !== animation) return;
            motion = null;finish();animation.cancel();
        };
    }
    function closeNow() {
        stopMotion();releaseGesture();closing = false;
        sheet.close();offset(0);sheet.classList.remove('sheet-closing');
    }
    function close() {
        if (!sheet.open || closing) return;
        closing = true;
        const from = getComputedStyle(sheet).transform;
        releaseGesture();sheet.classList.add('sheet-closing');
        animate(from, `translate3d(0,${sheet.offsetHeight + 32}px,0)`, 240, closeNow);
    }
    function settle() {
        const from = getComputedStyle(sheet).transform;
        releaseGesture();
        sheet.style.setProperty('--sheet-dim', '.8');
        animate(from, 'translate3d(0,0,0)', 220, () => offset(0));
    }
    function open() {
        if (sheet.open || !mobile.matches) return;
        stopMotion();offset(0);closing = false;
        sheet.classList.remove('sheet-closing');
        sheet.showModal();sheet.scrollTop = 0;atTop();
        // Opening is not dismissal: start focus on the existing Close button.
        sheet.querySelector('.music-sheet-head button').focus({preventScroll:true});
        animate(`translate3d(0,${sheet.offsetHeight + 32}px,0)`, 'translate3d(0,0,0)', 300, () => offset(0));
    }
    function start(event) {
        if (!mobile.matches || !sheet.open || closing || gesture || !event.isPrimary || event.button !== 0) return;
        if (event.currentTarget === cover && sheet.scrollTop > 1) return;
        suppressClick = false;
        const from = getComputedStyle(sheet).transform;
        stopMotion();
        // Continue from a partially completed entrance or snap-back without jumping.
        const y = from === 'none' ? 0 : Math.max(0, new DOMMatrixReadOnly(from).m42);
        offset(y);
        gesture = {id:event.pointerId,target:event.currentTarget,x:event.clientX,y:event.clientY,base:y,dy:y,moved:false,samples:[{y:event.clientY,t:event.timeStamp}]};
        event.currentTarget.setPointerCapture(event.pointerId);
    }
    function move(event) {
        if (!gesture || gesture.id !== event.pointerId) return;
        const dx = event.clientX - gesture.x, dy = event.clientY - gesture.y;
        if (!gesture.moved && Math.abs(dx) > 12 && Math.abs(dx) > Math.abs(dy)) {gesture.cancelled = true;gesture.moved = true;}
        if (gesture.cancelled) return;
        if (Math.abs(dy) > 6) gesture.moved = true;
        gesture.dy = Math.max(0, gesture.base + dy);
        gesture.samples.push({y:event.clientY,t:event.timeStamp});
        gesture.samples = gesture.samples.filter(p => event.timeStamp - p.t <= 100).slice(-8);
        sheet.classList.toggle('sheet-dragging', gesture.moved);
        offset(gesture.dy);
    }
    function end(event) {
        if (!gesture || gesture.id !== event.pointerId) return;
        const moved = gesture.moved, distance = gesture.dy;
        if (moved) suppressClick = true;
        const first = gesture.samples[0];
        const elapsed = event.timeStamp - first.t;
        const velocity = elapsed > 0 && elapsed <= 120 ? (event.clientY - first.y) / elapsed : 0;
        const threshold = Math.min(160, Math.max(104, sheet.offsetHeight * .22));
        if (event.type === 'pointerup' && !gesture.cancelled && moved && (distance >= threshold || (distance >= 64 && velocity > .65))) close();
        else settle();
    }
    for (const target of [grip, cover]) {
        target.addEventListener('pointerdown', start);
        target.addEventListener('pointermove', move);
        target.addEventListener('pointerup', end);
        target.addEventListener('pointercancel', end);
        target.addEventListener('lostpointercapture', () => {
            if (gesture?.target !== target) return;
            if (gesture.moved) suppressClick = true;
            settle();
        });
        // A swipe must not become a cover click (which toggles playback).
        target.addEventListener('click', event => {
            if (event.detail && suppressClick) {
                suppressClick = false;event.preventDefault();event.stopImmediatePropagation();
            }
        }, true);
        target.addEventListener('dragstart', event => event.preventDefault());
    }
    grip.addEventListener('click', close);
    sheet.addEventListener('cancel', event => {event.preventDefault();close();});
    sheet.addEventListener('scroll', atTop, {passive:true});
    sheet.addEventListener('click', event => {
        if (event.target !== sheet) return;
        const r = sheet.getBoundingClientRect();
        if (event.clientY < r.top || event.clientX < r.left || event.clientX > r.right || event.clientY > r.bottom) close();
    });
    sheet.addEventListener('close', () => {stopMotion();releaseGesture();offset(0);closing = false;sheet.classList.remove('sheet-closing');});
    return {open, close, closeNow};
};
