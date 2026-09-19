document.addEventListener("touchstart", function() {},false);
let mybutton = document.getElementById("topBtn");
window.onscroll = function() {scrollFunction()};
function scrollFunction() {
  if (document.body.scrollTop > 200 || document.documentElement.scrollTop > 200) {
    mybutton.style.display = "block";
  } else {
    mybutton.style.display = "none";
  }
}
function topFunction() {
  document.body.scrollTop = 0;
  document.documentElement.scrollTop = 0;
}
// LCARS Audio Engine & Sound Registry
const LCARS_AUDIO = {
    // Key beeps rotated on standard keypresses/clicks:
    // Rotates randomly between original LCARS beep (audio2) and the two new wav beeps (sfx-key-1, sfx-key-2).
    // Easy to add more sound IDs here as additional audio assets are added!
    keyBeepIds: ['audio2', 'sfx-key-1', 'sfx-key-2'],
    lastKeyIndex: -1,
    cancelId: 'sfx-cancel',
    popupId: 'sfx-popup',
    lastPlayTick: 0,

    shouldPlay() {
        const now = performance.now();
        if (now - this.lastPlayTick < 50) return false;
        this.lastPlayTick = now;
        return true;
    },

    markPlayed() {
        this.lastPlayTick = performance.now();
    },

    play(audioId) {
        if (!audioId) return null;
        try {
            const el = document.getElementById(audioId);
            if (el) {
                el.onended = null;
                el.currentTime = 0;
                const p = el.play();
                if (p && typeof p.catch === 'function') {
                    p.catch(() => {});
                }
                return el;
            }
        } catch (err) {
            console.warn(`[LCARS SFX] Playback error for ${audioId}:`, err);
        }
        return null;
    },

    // Randomly rotate between key beeps without repeating the same one twice consecutively
    playKeyBeep() {
        if (!this.shouldPlay()) return null;
        if (!this.keyBeepIds || this.keyBeepIds.length === 0) return null;
        
        let idx = Math.floor(Math.random() * this.keyBeepIds.length);
        if (this.keyBeepIds.length > 1 && idx === this.lastKeyIndex) {
            idx = (idx + 1) % this.keyBeepIds.length;
        }
        this.lastKeyIndex = idx;
        const selectedId = this.keyBeepIds[idx];
        return this.play(selectedId);
    },

    playCancel() {
        if (!this.shouldPlay()) return null;
        return this.play(this.cancelId);
    },

    playPopup() {
        if (!this.shouldPlay()) return null;
        return this.play(this.popupId);
    },

    // Register dynamic sound for future sound extensions
    registerSound(id, src, category = 'general') {
        let el = document.getElementById(id);
        if (!el) {
            el = document.createElement('audio');
            el.id = id;
            el.src = src;
            el.preload = 'auto';
            document.body.appendChild(el);
        }
        if (category === 'key' && !this.keyBeepIds.includes(id)) {
            this.keyBeepIds.push(id);
        }
        return el;
    }
};

function playSoundAndRedirect(audioId, url) {
    let playedAudio = null;
    if (audioId === 'audio2' || audioId === 'key') {
        playedAudio = LCARS_AUDIO.playKeyBeep();
    } else if (audioId === 'sfx-cancel' || audioId === 'cancel') {
        playedAudio = LCARS_AUDIO.playCancel();
    } else if (audioId === 'sfx-popup' || audioId === 'popup') {
        playedAudio = LCARS_AUDIO.playPopup();
    } else {
        if (LCARS_AUDIO.shouldPlay()) {
            playedAudio = LCARS_AUDIO.play(audioId);
        }
    }

    if (url && typeof url === 'string' && url.trim() !== '' && url !== '#' && !url.startsWith('#') && url !== 'javascript:void(0)') {
        if (playedAudio) {
            let redirected = false;
            const doRedirect = () => {
                if (!redirected) {
                    redirected = true;
                    window.location.href = url;
                }
            };
            playedAudio.onended = doRedirect;
            setTimeout(doRedirect, 260);
        } else {
            window.location.href = url;
        }
    }
}

function playLcarsAudio(audioId) {
    if (audioId === 'audio2' || audioId === 'key') {
        return LCARS_AUDIO.playKeyBeep();
    } else if (audioId === 'sfx-cancel' || audioId === 'cancel') {
        return LCARS_AUDIO.playCancel();
    } else if (audioId === 'sfx-popup' || audioId === 'popup') {
        return LCARS_AUDIO.playPopup();
    } else {
        if (LCARS_AUDIO.shouldPlay()) {
            return LCARS_AUDIO.play(audioId);
        }
    }
    return null;
}

function goToAnchor(anchorId) {
    window.location.hash = anchorId;
}

// Accordion drop-down
var acc = document.getElementsByClassName("accordion");
var i;
for (i = 0; i < acc.length; i++) {
    acc[i].addEventListener("click", function() {
        this.classList.toggle("active");
        var accordionContent = this.nextElementSibling;
        if (accordionContent) {
            if (accordionContent.style.maxHeight) {
                accordionContent.style.maxHeight = null;
            } else {
                accordionContent.style.maxHeight = accordionContent.scrollHeight + "px";
            }
        }
    });
}

// Universal Button Sound Handler:
// Ensures every button, link, category card, and interactive control in the system plays an appropriate sound.
document.addEventListener('click', function(e) {
    const btn = e.target.closest('button, a, [role="button"], input[type="button"], input[type="submit"], .playSoundButton, .inventory-category-tile, .inventory-component-card, .inventory-card-top, .music-preset-btn, .standby-option');
    if (!btn) return;

    // If an audio sound was already triggered in this interaction window, ignore to prevent duplicate sound
    if (performance.now() - LCARS_AUDIO.lastPlayTick < 50) return;

    // Check if element requested a specific sound via data-sound
    const customSound = btn.dataset.sound;
    if (customSound) {
        playLcarsAudio(customSound);
        return;
    }

    // Inspect text, class, and attributes to select the best matching sound
    const text = (btn.textContent || '').trim().toUpperCase();
    const id = (btn.id || '').toLowerCase();
    const cls = (btn.className || '').toLowerCase();
    const ariaLabel = (btn.getAttribute('aria-label') || '').toLowerCase();

    const isCancelOrDelete = 
        cls.includes('cancel') ||
        cls.includes('close') ||
        cls.includes('delete') ||
        cls.includes('dismiss') ||
        cls.includes('clear') ||
        cls.includes('remove') ||
        id.includes('cancel') ||
        id.includes('close') ||
        id.includes('delete') ||
        id.includes('clear') ||
        id.includes('remove') ||
        ariaLabel.includes('cancel') ||
        ariaLabel.includes('close') ||
        ariaLabel.includes('delete') ||
        text === 'CANCEL' ||
        text === 'CLOSE' ||
        text === 'DELETE' ||
        text === 'DEL' ||
        text === 'CLEAR' ||
        text === 'DISMISS' ||
        text === 'REMOVE' ||
        text === '✕' ||
        text === 'X';

    const isPopupTrigger = 
        cls.includes('open-modal') ||
        cls.includes('inventory-btn-primary') ||
        text.startsWith('+ NEW') ||
        text.startsWith('+ ADD') ||
        text.startsWith('NEW ') ||
        text.startsWith('ADD ');

    if (isCancelOrDelete) {
        LCARS_AUDIO.playCancel();
    } else if (isPopupTrigger) {
        LCARS_AUDIO.playPopup();
    } else {
        LCARS_AUDIO.playKeyBeep();
    }
}, true); // Capture phase ensures universal coverage across all dynamically rendered elements