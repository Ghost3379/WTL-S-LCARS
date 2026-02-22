// Standby Management
let isStandby = false;
let standbyTimeout = null;
let STANDBY_DELAY = 5 * 60 * 1000; // 5 minutes (default, can be changed)

// API Base URL (will be set based on environment)
const API_BASE = window.location.origin;

// Time update intervals (global so they persist)
let timeUpdateInterval = null;
let dateUpdateInterval = null;
let dashboardDataInterval = null;
let minecraftStatusInterval = null;

// Store RGB state before standby
let rgbStateBeforeStandby = null;

// Store system state before standby
let systemStateBeforeStandby = {
    display: null,
    fan: null,
    minecraft: null
};

// Default standby configuration
const DEFAULT_STANDBY_CONFIG = {
    display: 'off',      // 'off' or 'on'
    lights: 'off',       // 'off' or 'on'
    fan: 'auto',         // 'auto', 'on', or 'off'
    minecraft: 'keep'    // 'keep' or 'stop'
};

// Network Scanner
async function loadNetworkDevices() {
    const listEl = document.getElementById('network-devices-list');
    const localIpEl = document.getElementById('network-local-ip');
    const scanBtn = document.querySelector('button[onclick="loadNetworkDevices()"]');
    const progressContainer = document.getElementById('network-progress-container');

    // Disable multiple triggers and show loading animation
    if (scanBtn) scanBtn.style.display = 'none';
    if (progressContainer) progressContainer.classList.remove('hidden');

    if (listEl) {
        listEl.innerHTML = ''; // Clear old list
    }

    try {
        const response = await fetch(`/api/network/scan`);
        const data = await response.json();

        if (localIpEl) localIpEl.textContent = data.local_ip;

        if (!listEl) return;

        if (data.devices && data.devices.length > 0) {
            let html = '';
            data.devices.forEach(device => {
                const selfBadge = device.is_self ? ' <span class="font-green">[THIS DEVICE]</span>' : '';
                html += `
                    <div class="network-device-card" style="margin-bottom: 10px; padding: 15px; background-color: var(--lcars-black); border-left: 5px solid ${device.is_self ? 'var(--lcars-green)' : 'var(--lcars-orange)'};">
                        <p class="flush uppercase font-golden-orange" style="font-size: 1.2rem;">${device.hostname || 'UNKNOWN DEVICE'}${selfBadge}</p>
                        <p class="flush"><span class="font-green">IP:</span> ${device.ip}</p>
                        <p class="flush"><span class="font-green">MAC:</span> ${device.mac}</p>
                        <p class="flush"><span class="font-green">STATUS:</span> ${device.status.toUpperCase()}</p>
                    </div>
                `;
            });
            listEl.innerHTML = html;
        } else {
            listEl.innerHTML = '<p class="flush uppercase font-red">No devices found.</p>';
        }

        // Hide loading animation and restore trigger
        if (progressContainer) progressContainer.classList.add('hidden');
        if (scanBtn) scanBtn.style.display = 'inline-block';
    } catch (error) {
        console.error('Failed to scan network:', error);
        if (listEl) {
            listEl.innerHTML = '<p class="flush uppercase font-red">Scan failed. Server connection error.</p>';
        }
        // Restore trigger on fail
        if (progressContainer) progressContainer.classList.add('hidden');
        if (scanBtn) scanBtn.style.display = 'inline-block';
    }
}

// Initialize on page load
document.addEventListener('DOMContentLoaded', () => {
    // Load saved settings
    loadSettings();
    loadStandbyConfig();

    // Show dashboard immediately
    showDashboard();

    // Setup screensaver double-click to wake
    const screensaver = document.getElementById('screensaver');
    if (screensaver) {
        let screensaverClickCount = 0;
        let screensaverClickTimer = null;

        screensaver.addEventListener('click', (e) => {
            screensaverClickCount++;
            if (screensaverClickCount === 1) {
                screensaverClickTimer = setTimeout(() => {
                    screensaverClickCount = 0;
                }, 500); // 500ms window for double-click
            } else if (screensaverClickCount === 2) {
                clearTimeout(screensaverClickTimer);
                screensaverClickCount = 0;
                exitStandby().catch(err => console.error('Error exiting standby:', err));
            }
        });

        screensaver.addEventListener('touchend', (e) => {
            e.preventDefault();
            screensaverClickCount++;
            if (screensaverClickCount === 1) {
                screensaverClickTimer = setTimeout(() => {
                    screensaverClickCount = 0;
                }, 500);
            } else if (screensaverClickCount === 2) {
                clearTimeout(screensaverClickTimer);
                screensaverClickCount = 0;
                exitStandby().catch(err => console.error('Error exiting standby:', err));
            }
        });
    }

    // Setup standby timeout
    resetStandbyTimeout();
    document.addEventListener('mousemove', resetStandbyTimeout);
    document.addEventListener('keypress', resetStandbyTimeout);
    document.addEventListener('touchstart', resetStandbyTimeout);

    // Global patch for touchscreen button clicks
    // Some local touchscreens fail to translate touchend to click on standard buttons
    document.addEventListener('touchend', function (e) {
        // Find if a button was touched
        const btn = e.target.closest('button');
        if (btn) {
            // Prevent default to stop redundant mousedown/click events
            e.preventDefault();
            // Force click
            btn.click();
        }
    }, { passive: false });
});

// Dashboard Management
function showDashboard() {
    // Hide all sections first, then show dashboard
    const sections = document.querySelectorAll('.content-section');
    sections.forEach(section => {
        section.classList.remove('active');
        section.style.display = 'none';
    });

    // Show dashboard section
    const dashboardSection = document.getElementById('section-dashboard');
    if (dashboardSection) {
        dashboardSection.classList.add('active');
        dashboardSection.style.display = 'block';
    }

    // Update time and date immediately when dashboard is shown
    updateTime();
    updateDate();

    // Start time update intervals if not already running
    if (!timeUpdateInterval) {
        timeUpdateInterval = setInterval(updateTime, 1000);
    }
    if (!dateUpdateInterval) {
        dateUpdateInterval = setInterval(updateDate, 60000); // Update every minute
    }

    // Load initial data
    loadDashboardData();

    // Start dashboard data update interval if not already running
    if (!dashboardDataInterval) {
        dashboardDataInterval = setInterval(loadDashboardData, 5000); // Update every 5 seconds
    }

    // Setup double-click on CONTROL panel to enter standby (after dashboard is shown)
    setupControlPanelStandby();
}

// Setup double-click on CONTROL panel to enter standby
let controlPanelClickCount = 0;
let controlPanelClickTimer = null;

function setupControlPanelStandby() {
    // Use a small delay to ensure the element is fully rendered
    setTimeout(() => {
        const controlPanel = document.getElementById('control-panel');
        if (controlPanel) {
            // Remove any existing listeners first
            const newPanel = controlPanel.cloneNode(true);
            controlPanel.parentNode.replaceChild(newPanel, controlPanel);

            // Reset click counter
            controlPanelClickCount = 0;
            if (controlPanelClickTimer) {
                clearTimeout(controlPanelClickTimer);
                controlPanelClickTimer = null;
            }

            newPanel.addEventListener('click', handleControlPanelClick);
            newPanel.addEventListener('dblclick', (e) => {
                e.preventDefault();
                e.stopPropagation();
                controlPanelClickCount = 0;
                if (controlPanelClickTimer) {
                    clearTimeout(controlPanelClickTimer);
                    controlPanelClickTimer = null;
                }
                enterStandby().catch(err => console.error('Error entering standby:', err));
            });

            // Also support touch events for mobile
            newPanel.addEventListener('touchend', handleControlPanelTouch);
        }
    }, 100);
}

function handleControlPanelClick(e) {
    e.stopPropagation();
    controlPanelClickCount++;
    if (controlPanelClickCount === 1) {
        controlPanelClickTimer = setTimeout(() => {
            controlPanelClickCount = 0;
        }, 500); // 500ms window for double-click
    } else if (controlPanelClickCount === 2) {
        clearTimeout(controlPanelClickTimer);
        controlPanelClickCount = 0;
        controlPanelClickTimer = null;
        enterStandby().catch(err => console.error('Error entering standby:', err));
    }
}

function handleControlPanelTouch(e) {
    e.preventDefault();
    e.stopPropagation();
    controlPanelClickCount++;
    if (controlPanelClickCount === 1) {
        controlPanelClickTimer = setTimeout(() => {
            controlPanelClickCount = 0;
        }, 500);
    } else if (controlPanelClickCount === 2) {
        clearTimeout(controlPanelClickTimer);
        controlPanelClickCount = 0;
        controlPanelClickTimer = null;
        enterStandby().catch(err => console.error('Error entering standby:', err));
    }
}


// Navigation
function switchSection(sectionName) {
    // Hide all sections - force hide with inline style
    const sections = document.querySelectorAll('.content-section');
    sections.forEach(section => {
        section.classList.remove('active');
        section.style.display = 'none';
    });

    // Show selected section
    const targetSection = document.getElementById(`section-${sectionName}`);
    if (targetSection) {
        targetSection.classList.add('active');
        targetSection.style.display = 'block';
    }

    // Update navigation buttons
    const navButtons = document.querySelectorAll('nav button');
    navButtons.forEach(btn => btn.classList.remove('active'));
    const activeNav = document.getElementById(`nav-${sectionName}`);
    if (activeNav) {
        activeNav.classList.add('active');
    }

    // Load section-specific data
    loadSectionData(sectionName);

    // Load standby config UI when settings section is shown
    if (sectionName === 'settings') {
        loadStandbyConfig();
    }

    // Play sound
    playSoundAndRedirect('audio2', '#');
}

// Time & Date Management
function updateTime() {
    const now = new Date();
    const timeString = now.toLocaleTimeString('en-US', {
        hour12: false,
        hour: '2-digit',
        minute: '2-digit',
        second: '2-digit'
    });

    // Update all time displays
    const timeElements = [
        document.getElementById('system-time-large'),
        document.getElementById('dashboard-time'),
        document.getElementById('screensaver-time')
    ];

    timeElements.forEach(el => {
        if (el) {
            el.textContent = timeString;
        }
    });
}

function updateDate() {
    const now = new Date();
    const dateString = now.toLocaleDateString('en-US', {
        weekday: 'long',
        year: 'numeric',
        month: 'long',
        day: 'numeric'
    }).toUpperCase();

    const dateElements = [
        document.getElementById('system-date'),
        document.getElementById('dashboard-date'),
        document.getElementById('screensaver-date')
    ];

    dateElements.forEach(el => {
        if (el) {
            el.textContent = dateString;
        }
    });
}

async function updateTimeStatus() {
    try {
        const response = await fetch(`/api/system/time-status`);
        const data = await response.json();

        const statusEl = document.getElementById('time-status-value');
        const indicatorEl = document.getElementById('time-status-indicator');

        if (statusEl) {
            statusEl.textContent = data.status.toUpperCase();
            statusEl.className = `font-${data.status === 'ok' ? 'green' : 'red'}`;
            // Blink if status is not OK
            if (data.status !== 'ok') {
                statusEl.classList.add('blink-slow');
            } else {
                statusEl.classList.remove('blink-slow');
            }
        }

        if (indicatorEl) {
            indicatorEl.textContent = `TIME ${data.status.toUpperCase()}`;
            indicatorEl.className = `panel-6 font-${data.status === 'ok' ? 'green' : 'red'}`;
            // Blink if status is not OK
            if (data.status !== 'ok') {
                indicatorEl.classList.add('blink-slow');
            } else {
                indicatorEl.classList.remove('blink-slow');
            }
        }
    } catch (error) {
        // Silently fail if no backend is available (e.g., file:// protocol)
        if (window.location.protocol !== 'file:') {
            console.error('Failed to update time status:', error);
        }
    }
}

// Standby / Screensaver
async function enterStandby() {
    if (isStandby) return; // Already in standby

    isStandby = true;
    const screensaver = document.getElementById('screensaver');
    const dashboard = document.getElementById('main-dashboard');

    // Reset opacity for fade-in animation
    screensaver.style.opacity = '0';
    screensaver.classList.remove('hidden');
    screensaver.classList.remove('screensaver-exiting');

    // Trigger fade-in animation
    setTimeout(() => {
        screensaver.style.transition = 'opacity 0.5s ease-in';
        screensaver.style.opacity = '1';
    }, 10);

    // Fade out dashboard
    dashboard.style.transition = 'opacity 0.5s ease-out';
    dashboard.style.opacity = '0.1';

    // Get standby configuration
    const standbyConfig = getStandbyConfig();

    // Save current system state
    try {
        const pironmanResponse = await fetch(`/api/pironman/status`);
        const pironmanData = await pironmanResponse.json();

        systemStateBeforeStandby.display = pironmanData.display.on;
        systemStateBeforeStandby.fan = pironmanData.fan.mode;

        // Save RGB state
        rgbStateBeforeStandby = {
            on: pironmanData.rgb.on,
            color: pironmanData.rgb.color,
            style: pironmanData.rgb.style,
            brightness: pironmanData.rgb.brightness,
            speed: pironmanData.rgb.speed
        };

        // Handle lights based on config
        if (standbyConfig.lights === 'off' && pironmanData.rgb.on) {
            await fetch(`/api/pironman/fan-rgb`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ state: 'off' })
            });
        }
        // If config says 'on', lights stay on (do nothing)

        // Handle display based on config
        if (standbyConfig.display === 'off') {
            await setDisplay('off');
        }
        // If config says 'on', display stays on (do nothing)

        // Handle fan based on config
        if (standbyConfig.fan !== 'auto') {
            await setFanMode(standbyConfig.fan);
        }
        // If config says 'auto', fan stays in auto mode (do nothing)

    } catch (error) {
        console.error('Failed to save system state:', error);
    }

    // Handle Minecraft server based on config
    if (standbyConfig.minecraft === 'stop') {
        try {
            const mcResponse = await fetch(`/api/minecraft/status`);
            const mcData = await mcResponse.json();
            if (mcData.running) {
                systemStateBeforeStandby.minecraft = true;
                await fetch(`/api/minecraft/stop`, { method: 'POST' });
            } else {
                systemStateBeforeStandby.minecraft = false;
            }
        } catch (error) {
            console.error('Failed to handle Minecraft server:', error);
        }
    } else {
        // Keep running - just save current state
        try {
            const mcResponse = await fetch(`/api/minecraft/status`);
            const mcData = await mcResponse.json();
            systemStateBeforeStandby.minecraft = mcData.running;
        } catch (error) {
            console.error('Failed to check Minecraft status:', error);
        }
    }
}

async function exitStandby() {
    if (!isStandby) return; // Already awake

    isStandby = false;
    const screensaver = document.getElementById('screensaver');
    const dashboard = document.getElementById('main-dashboard');

    // Instant exit - no fade
    screensaver.classList.add('hidden');

    // Start startup animation immediately
    setTimeout(() => {
        // Reset dashboard opacity
        dashboard.style.opacity = '1';

        // Hide only text elements, keep structural elements (elbows, panels, bars) visible
        // NOTE: Panel texts (STATUS, MONITOR, CONTROL, etc.) are NOT hidden - they stay visible with the panels
        const textElements = dashboard.querySelectorAll(
            '.content-section.active h1, .content-section.active h2, .content-section.active h3, ' +
            '.content-section.active p, .content-section.active .lcars-text-bar, ' +
            '.content-section.active .lcars-text-bar h2, .content-section.active .lcars-text-bar h3, ' +
            '.content-section.active .lcars-text-bar h4, .content-section.active .lcars-text-bar span, ' +
            '.content-section.active .status-card, .content-section.active .buttons, ' +
            '.content-section.active .button-almond, .content-section.active .info-row, ' +
            '.content-section.active span, .content-section.active div[id], ' +
            '.banner, nav button, ' +
            '.right-frame-top .banner, .right-frame-top nav button'
        );

        textElements.forEach(el => {
            if (el && el.textContent && el.textContent.trim() !== '') {
                // Skip spans inside time-status-text - they'll be handled with the parent
                if (el.id === 'time-status-value' || (el.tagName === 'SPAN' && el.closest('#time-status-text'))) {
                    return;
                }
                el.style.opacity = '0';
            }
        });

        // Hide time-status-text and its children together
        const timeStatusText = dashboard.querySelector('#time-status-text');
        if (timeStatusText) {
            timeStatusText.style.opacity = '0';
            const timeStatusSpans = timeStatusText.querySelectorAll('span');
            timeStatusSpans.forEach(span => {
                span.style.opacity = '0';
            });
        }

        // Also hide all text content inside LCARS text bars (including SYSTEM TIME bar)
        const allTextBars = dashboard.querySelectorAll('.content-section.active .lcars-text-bar');
        allTextBars.forEach(bar => {
            bar.style.opacity = '0'; // Hide the bar itself
            const barTexts = bar.querySelectorAll('h2, h3, h4, span, p, div');
            barTexts.forEach(text => {
                text.style.opacity = '0';
            });
        });

        // DO NOT hide panel texts - they stay visible with the structural panels

        let delay = 0;
        const delayStep = 300; // Slower: 0.3s between groups

        // 1. Top navigation buttons - appear in pairs (horizontal pairs)
        const navButtons = Array.from(dashboard.querySelectorAll('nav button'));
        // Group buttons in pairs
        for (let i = 0; i < navButtons.length; i += 2) {
            const pair = navButtons.slice(i, i + 2);
            setTimeout(() => {
                pair.forEach(btn => {
                    btn.style.opacity = '1';
                    btn.style.transition = 'opacity 0.3s ease-out';
                });
            }, delay);
            delay += delayStep;
        }

        // 2. Left frame panels - panels and their texts are already visible (not animated)
        // Panels stay visible, no animation needed

        // 3. Left frame top button - button text stays visible (not animated)
        // Button stays visible, no animation needed

        // 4. Banner text
        const banner = dashboard.querySelector('.banner');
        if (banner) {
            setTimeout(() => {
                banner.style.opacity = '1';
                banner.style.transition = 'opacity 0.3s ease-out';
            }, delay);
            delay += delayStep;
        }

        // 5. Section title (h1 "PRODUCTION STATUS") and "SYSTEM TIME" bar together
        const sectionTitle = dashboard.querySelector('.content-section.active h1');
        const systemTimeBar = dashboard.querySelector('.content-section.active .lcars-text-bar h2');
        const systemTimeBarContainer = dashboard.querySelector('.content-section.active .lcars-text-bar');
        setTimeout(() => {
            // Show section title
            if (sectionTitle) {
                sectionTitle.style.opacity = '1';
                sectionTitle.style.transition = 'opacity 0.3s ease-out';
            }
            // Show SYSTEM TIME bar and its text together
            if (systemTimeBarContainer) {
                systemTimeBarContainer.style.opacity = '1';
                systemTimeBarContainer.style.transition = 'opacity 0.3s ease-out';
                // Show the h2 text inside the bar
                if (systemTimeBar) {
                    systemTimeBar.style.opacity = '1';
                    systemTimeBar.style.transition = 'opacity 0.3s ease-out';
                }
            }
        }, delay);
        delay += delayStep;

        // 6. Dashboard time/date display and TIME STATUS together
        const timeDisplay = dashboard.querySelectorAll('#dashboard-time, #dashboard-date, #time-status-text');
        setTimeout(() => {
            timeDisplay.forEach(el => {
                if (el) {
                    el.style.opacity = '1';
                    el.style.transition = 'opacity 0.3s ease-out';
                    // Also show all child elements (spans) inside time-status-text
                    if (el.id === 'time-status-text') {
                        const childSpans = el.querySelectorAll('span');
                        childSpans.forEach(span => {
                            span.style.opacity = '1';
                            span.style.transition = 'opacity 0.3s ease-out';
                        });
                    }
                }
            });
        }, delay);
        delay += delayStep;

        // 7. LCARS text bars and Status cards - appear together (labels with their boxes)
        const textBars = dashboard.querySelectorAll('.content-section.active .status-card .lcars-text-bar');
        const statusCards = dashboard.querySelectorAll('.content-section.active .status-card');
        setTimeout(() => {
            // Animate text bars and status cards together
            textBars.forEach(bar => {
                bar.style.opacity = '1';
                bar.style.transition = 'opacity 0.3s ease-out';
                // Show all text content inside the bar immediately
                const barContent = bar.querySelectorAll('h2, h3, h4, span, p, div');
                barContent.forEach(content => {
                    content.style.opacity = '1';
                    content.style.transition = 'opacity 0.3s ease-out';
                });
            });
            statusCards.forEach(card => {
                card.style.opacity = '1';
                card.style.transition = 'opacity 0.3s ease-out';
            });
        }, delay);
        delay += delayStep;

        // 7b. Status card values (the numbers/text inside cards) - appear together with a slight delay after labels
        const statusCardValues = dashboard.querySelectorAll('.content-section.active .status-card p[id], .content-section.active .status-card span[id]');
        setTimeout(() => {
            statusCardValues.forEach(el => {
                el.style.opacity = '1';
                el.style.transition = 'opacity 0.3s ease-out';
            });
        }, delay);
        delay += delayStep;

        // 8. Other LCARS text bars (not in status cards) - appear together with their content
        const otherTextBars = dashboard.querySelectorAll('.content-section.active .lcars-text-bar:not(.status-card .lcars-text-bar)');
        setTimeout(() => {
            otherTextBars.forEach(bar => {
                // Show the bar itself
                bar.style.opacity = '1';
                bar.style.transition = 'opacity 0.3s ease-out';
                // Show all text content inside the bar
                const barContent = bar.querySelectorAll('h2, h3, h4, span, p');
                barContent.forEach(content => {
                    content.style.opacity = '1';
                    content.style.transition = 'opacity 0.3s ease-out';
                });
            });
        }, delay);
        delay += delayStep;

        // 9. Info rows - appear together with their content
        const infoRows = dashboard.querySelectorAll('.content-section.active .info-row');
        setTimeout(() => {
            infoRows.forEach(row => {
                row.style.opacity = '1';
                row.style.transition = 'opacity 0.3s ease-out';
                // Show all content inside the row
                const rowContent = row.querySelectorAll('span, p, div');
                rowContent.forEach(content => {
                    content.style.opacity = '1';
                    content.style.transition = 'opacity 0.3s ease-out';
                });
            });
        }, delay);
        delay += delayStep;

        // 10. Buttons - appear together
        const buttons = dashboard.querySelectorAll('.content-section.active .buttons, .content-section.active .button-almond');
        setTimeout(() => {
            buttons.forEach(btn => {
                btn.style.opacity = '1';
                btn.style.transition = 'opacity 0.3s ease-out';
            });
        }, delay);
        delay += delayStep;

        // 11. Other paragraphs and spans - appear together with their parent containers
        const otherText = dashboard.querySelectorAll('.content-section.active p:not(.status-card p):not(.info-row p), .content-section.active span:not(.status-card span):not(.info-row span), .content-section.active div[id]:not(.status-card)');
        setTimeout(() => {
            otherText.forEach(el => {
                if (el && el.textContent && el.textContent.trim() !== '') {
                    // Check if element is inside a bar or container
                    const parentBar = el.closest('.lcars-text-bar, .info-row, .status-card');
                    if (!parentBar || parentBar.style.opacity === '1') {
                        // Only show if parent is already visible or has no parent bar
                        el.style.opacity = '1';
                        el.style.transition = 'opacity 0.3s ease-out';
                    }
                }
            });
        }, delay);
        delay += delayStep;

        // 12. Make sure any remaining hidden elements appear
        setTimeout(() => {
            textElements.forEach(el => {
                if (el && el.style.opacity === '0') {
                    el.style.opacity = '1';
                    el.style.transition = 'opacity 0.3s ease-out';
                }
            });
        }, delay);

        // Clean up after all animations complete
        setTimeout(() => {
            textElements.forEach(el => {
                if (el) {
                    el.style.transition = '';
                }
            });
        }, delay + 500);
    }, 0); // No delay, instant startup

    // Restore system state based on what was changed
    const standbyConfig = getStandbyConfig();

    try {
        // Restore display if it was turned off
        if (standbyConfig.display === 'off' && systemStateBeforeStandby.display !== null) {
            if (systemStateBeforeStandby.display) {
                await setDisplay('on');
            }
        }

        // Restore lights if they were turned off
        if (standbyConfig.lights === 'off' && rgbStateBeforeStandby && rgbStateBeforeStandby.on) {
            try {
                // Restore RGB color, style, brightness, and speed, then enable
                await fetch(`/api/pironman/fan-rgb-color`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ color: rgbStateBeforeStandby.color })
                });
                await fetch(`/api/pironman/fan-rgb-style`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ style: rgbStateBeforeStandby.style })
                });
                await fetch(`/api/pironman/fan-rgb-brightness`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ brightness: rgbStateBeforeStandby.brightness })
                });
                await fetch(`/api/pironman/fan-rgb-speed`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ speed: rgbStateBeforeStandby.speed })
                });
                // Enable RGB
                await fetch(`/api/pironman/fan-rgb`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ state: 'on' })
                });
            } catch (error) {
                console.error('Failed to restore RGB state:', error);
            }
        }

        // Restore fan mode if it was changed
        if (standbyConfig.fan !== 'auto' && systemStateBeforeStandby.fan !== null) {
            await setFanMode(systemStateBeforeStandby.fan);
        }

        // Reload status to update UI
        loadPironmanStatus();
    } catch (error) {
        console.error('Failed to restore system state:', error);
    }

    // Restore Minecraft server if it was stopped
    if (standbyConfig.minecraft === 'stop' && systemStateBeforeStandby.minecraft === true) {
        try {
            await fetch(`/api/minecraft/start`, { method: 'POST' });
            loadMinecraftStatus();
        } catch (error) {
            console.error('Failed to restore Minecraft server:', error);
        }
    }

    // Clear saved states
    rgbStateBeforeStandby = null;
    systemStateBeforeStandby = {
        display: null,
        fan: null,
        minecraft: null
    };

    resetStandbyTimeout();
}

function resetStandbyTimeout() {
    if (standbyTimeout) {
        clearTimeout(standbyTimeout);
    }

    if (!isStandby) {
        standbyTimeout = setTimeout(() => {
            enterStandby().catch(err => console.error('Error entering standby:', err));
        }, STANDBY_DELAY);
    }
}

// Dashboard Data
function loadDashboardData() {
    updateTimeStatus();
    updateSystemStats();
    updateSystemUptime();
    updateActiveProjects();
    updateServerStats();
}

// Update active projects count
async function updateActiveProjects() {
    try {
        const response = await fetch(`/api/projects`);
        const projects = await response.json();

        const activeCount = projects.filter(p => p.active).length;
        const activeProjectsEl = document.getElementById('active-projects');
        if (activeProjectsEl) {
            activeProjectsEl.textContent = activeCount;
            // Blink if there are active projects
            if (activeCount > 0) {
                activeProjectsEl.classList.add('blink-slow');
            } else {
                activeProjectsEl.classList.remove('blink-slow');
            }
        }
    } catch (error) {
        // Silently fail if no backend is available (e.g., file:// protocol)
        if (window.location.protocol !== 'file:') {
            console.error('Failed to update active projects:', error);
        }
    }
}

// Update server stats for dashboard
async function updateServerStats() {
    try {
        // Fetch Minecraft status
        try {
            const mcResponse = await fetch(`/api/minecraft/status`);
            const mcData = await mcResponse.json();
            const mcStatusEl = document.getElementById('dashboard-mc-status');
            if (mcStatusEl) {
                mcStatusEl.textContent = mcData.running ? 'RUNNING' : 'STOPPED';
                mcStatusEl.className = mcData.running ? 'font-green uppercase' : 'font-red uppercase';
            }
        } catch (error) {
            const mcStatusEl = document.getElementById('dashboard-mc-status');
            if (mcStatusEl) {
                mcStatusEl.textContent = 'ERROR';
                mcStatusEl.className = 'font-red uppercase';
            }
        }

        // Fetch Navidrome status
        try {
            const navResponse = await fetch(`/api/music/status`);
            const navData = await navResponse.json();
            const navStatusEl = document.getElementById('dashboard-nav-status');
            if (navStatusEl) {
                navStatusEl.textContent = navData.connected ? 'RUNNING' : 'STOPPED';
                navStatusEl.className = navData.connected ? 'font-green uppercase' : 'font-red uppercase';
            }
        } catch (error) {
            const navStatusEl = document.getElementById('dashboard-nav-status');
            if (navStatusEl) {
                navStatusEl.textContent = 'ERROR';
                navStatusEl.className = 'font-red uppercase';
            }
        }

        // Fetch Nextcloud status
        try {
            const ncResponse = await fetch(`/api/servers/nextcloud/status`);
            const ncData = await ncResponse.json();
            const ncStatusEl = document.getElementById('dashboard-nc-status');
            if (ncStatusEl) {
                ncStatusEl.textContent = ncData.running ? 'RUNNING' : 'STOPPED';
                ncStatusEl.className = ncData.running ? 'font-green uppercase' : 'font-red uppercase';
            }
        } catch (error) {
            const ncStatusEl = document.getElementById('dashboard-nc-status');
            if (ncStatusEl) {
                ncStatusEl.textContent = 'ERROR';
                ncStatusEl.className = 'font-red uppercase';
            }
        }
    } catch (error) {
        // Silently fail if no backend is available
        if (window.location.protocol !== 'file:') {
            console.error('Failed to update server stats:', error);
        }
    }
}


function loadSectionData(section) {
    // Clear Minecraft interval if switching away from servers
    if (minecraftStatusInterval) {
        clearInterval(minecraftStatusInterval);
        minecraftStatusInterval = null;
    }

    switch (section) {
        case 'dashboard':
            loadDashboardData();
            break;
        case 'projects':
            loadProjects();
            break;
        case 'apps':
            loadAppLauncher();
            break;
        case 'system':
            loadSystemInfo();
            break;
        case 'pironman':
            loadPironmanStatus();
            break;
        case 'servers':
            // Load all server statuses immediately
            loadMinecraftStatus();
            loadNavidromeStatus();
            loadNextcloudStatus();
            // Start auto-refresh for server statuses (every 5 seconds)
            minecraftStatusInterval = setInterval(() => {
                loadMinecraftStatus();
                loadNavidromeStatus();
                loadNextcloudStatus();
            }, 5000);
            break;
        case 'music':
            loadMusicStatus();
            loadMusicPlaylists();
            loadNowPlaying();
            // Set up periodic updates for now playing
            if (musicStatusInterval) {
                clearInterval(musicStatusInterval);
            }
            musicStatusInterval = setInterval(() => {
                loadNowPlaying();
            }, 3000); // Update every 3 seconds
            break;
    }
}

// System Stats
async function updateSystemStats() {
    try {
        const response = await fetch(`/api/system/stats`);
        const data = await response.json();

        // Update dashboard cards
        const tempEl = document.getElementById('system-temp');
        const cpuLoadEl = document.getElementById('cpu-load');
        const ramUsageEl = document.getElementById('ram-usage');

        if (tempEl) {
            tempEl.textContent = `${data.cpuTemp}\u00B0C`;
            // Blink if temp is high (> 70°C)
            if (data.cpuTemp > 70) {
                tempEl.classList.add('blink-slow');
            } else {
                tempEl.classList.remove('blink-slow');
            }
        }

        if (cpuLoadEl) {
            cpuLoadEl.textContent = `${data.cpuLoad}%`;
            // Blink if CPU load is high (> 80%)
            if (data.cpuLoad > 80) {
                cpuLoadEl.classList.add('blink-slow');
            } else {
                cpuLoadEl.classList.remove('blink-slow');
            }
        }

        if (ramUsageEl) {
            ramUsageEl.textContent = `${data.ramUsage}%`;
            // Blink if RAM usage is high (> 85%)
            if (data.ramUsage > 85) {
                ramUsageEl.classList.add('blink-slow');
            } else {
                ramUsageEl.classList.remove('blink-slow');
            }
        }

        // Update system section
        const systemCpuLoadEl = document.getElementById('system-cpu-load');
        const systemRamUsageEl = document.getElementById('system-ram-usage');
        const systemCpuTempEl = document.getElementById('system-cpu-temp');
        const wlanStatusEl = document.getElementById('system-wlan-status');

        if (systemCpuLoadEl) {
            systemCpuLoadEl.textContent = `${data.cpuLoad}%`;
            if (data.cpuLoad > 80) {
                systemCpuLoadEl.classList.add('blink-slow');
            } else {
                systemCpuLoadEl.classList.remove('blink-slow');
            }
        }

        if (systemRamUsageEl) {
            systemRamUsageEl.textContent = `${data.ramUsage}%`;
            if (data.ramUsage > 85) {
                systemRamUsageEl.classList.add('blink-slow');
            } else {
                systemRamUsageEl.classList.remove('blink-slow');
            }
        }

        if (systemCpuTempEl) {
            systemCpuTempEl.textContent = `${data.cpuTemp}\u00B0C`;
            if (data.cpuTemp > 70) {
                systemCpuTempEl.classList.add('blink-slow');
            } else {
                systemCpuTempEl.classList.remove('blink-slow');
            }
        }

        updateElement('system-disk-space', `${data.diskUsed} / ${data.diskTotal} (${data.diskPercent}%)`);
        updateElement('system-wlan-ip', data.wlan.ip || '--');
        updateElement('system-wlan-rssi', data.wlan.rssi ? `${data.wlan.rssi} dBm` : '--');

        // Update WiFi SSID with special handling for WTL-S-Core
        const ssidEl = document.getElementById('system-wlan-ssid');
        const coreBadgeEl = document.getElementById('system-wlan-core-badge');
        const coreDescEl = document.getElementById('system-wlan-core-description');

        if (ssidEl) {
            const ssid = data.wlan.ssid || '--';
            ssidEl.textContent = ssid;

            // Check if connected to WTL-S-Core
            if (ssid === 'WTL-S-Core' || ssid === 'WTL-S-CORE') {
                if (coreBadgeEl) {
                    coreBadgeEl.style.display = 'inline';
                }
                if (coreDescEl) {
                    coreDescEl.style.display = 'block';
                }
            } else {
                if (coreBadgeEl) {
                    coreBadgeEl.style.display = 'none';
                }
                if (coreDescEl) {
                    coreDescEl.style.display = 'none';
                }
            }
        }

        if (wlanStatusEl) {
            const isConnected = data.wlan.connected;
            wlanStatusEl.textContent = isConnected ? 'CONNECTED' : 'DISCONNECTED';
            // Blink if disconnected
            if (!isConnected) {
                wlanStatusEl.classList.add('blink-slow');
            } else {
                wlanStatusEl.classList.remove('blink-slow');
            }
        }

    } catch (error) {
        // Silently fail if no backend is available (e.g., file:// protocol)
        if (window.location.protocol !== 'file:') {
            console.error('Failed to update system stats:', error);
        }
    }
}

async function updateSystemUptime() {
    try {
        const response = await fetch(`/api/system/uptime`);
        const data = await response.json();

        updateElement('system-uptime', data.formatted);
        updateElement('system-uptime-detailed', data.detailed);
    } catch (error) {
        // Silently fail if no backend is available (e.g., file:// protocol)
        if (window.location.protocol !== 'file:') {
            console.error('Failed to update uptime:', error);
        }
    }
}

// Projects
async function loadProjects() {
    try {
        const response = await fetch(`/api/projects`);
        const projects = await response.json();

        const projectsList = document.getElementById('projects-list');
        if (!projectsList) return;

        if (projects.length === 0) {
            projectsList.innerHTML = '<p class="flush uppercase go-big font-golden-orange">No active projects</p>';
            return;
        }

        let html = '';
        projects.forEach(project => {
            const activeClass = project.active ? 'font-golden-orange' : '';
            html += `
                <div class="status-card" style="margin-bottom: 20px;">
                    <div class="lcars-text-bar">
                        <h3>${project.name.toUpperCase()} ${project.active ? '[ACTIVE]' : ''}</h3>
                    </div>
                    <p><span class="font-green">STATUS:</span> <span class="font-golden-orange uppercase">${project.status}</span></p>
                    <p><span class="font-green">CREATED:</span> <span class="font-golden-orange">${project.created}</span></p>
                    ${project.todos && project.todos.length > 0 ? `
                        <p><span class="font-green">TODOS:</span> ${project.todos.filter(t => !t.done).length} / ${project.todos.length}</p>
                    ` : ''}
                    <div class="buttons" style="margin-top: 15px;">
                        <button onclick="editProject('${project.id}')" class="button-almond">EDIT</button>
                        <button onclick="viewProject('${project.id}')" class="button-almond">VIEW</button>
                    </div>
                </div>
            `;
        });

        projectsList.innerHTML = html;

        // Update active projects count
        const activeCount = projects.filter(p => p.active).length;
        const activeProjectsEl = document.getElementById('active-projects');
        if (activeProjectsEl) {
            activeProjectsEl.textContent = activeCount;
            // Blink if there are active projects
            if (activeCount > 0) {
                activeProjectsEl.classList.add('blink-slow');
            } else {
                activeProjectsEl.classList.remove('blink-slow');
            }
        }
    } catch (error) {
        console.error('Failed to load projects:', error);
    }
}

async function createProject() {
    const name = await lcarsPrompt('Project name:');
    if (!name) return;

    fetch(`/api/projects`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name })
    })
        .then(() => loadProjects())
        .catch(error => console.error('Failed to create project:', error));
}

async function editProject(id) {
    // TODO: Open project edit modal
    await lcarsAlert('Project edit feature coming soon!');
}

async function viewProject(id) {
    // TODO: Open project view
    await lcarsAlert('Project view feature coming soon!');
}


// App Launcher
function loadAppLauncher() {
    // App launcher doesn't need dynamic loading
}

async function openKicad() {
    try {
        await fetch(`/api/apps/kicad`, { method: 'POST' });
    } catch (error) {
        console.error('Failed to open KiCad:', error);
        await lcarsAlert('Failed to open KiCad');
    }
}

async function openKicadLastProject() {
    try {
        await fetch(`/api/apps/kicad/last-project`, { method: 'POST' });
    } catch (error) {
        console.error('Failed to open KiCad last project:', error);
        await lcarsAlert('Failed to open KiCad last project');
    }
}

async function openBambuStudio() {
    try {
        await fetch(`/api/apps/bambu-studio`, { method: 'POST' });
    } catch (error) {
        console.error('Failed to open Bambu Studio:', error);
        await lcarsAlert('Failed to open Bambu Studio');
    }
}

async function openPDFViewer() {
    // TODO: Open PDF file picker
    await lcarsAlert('PDF viewer feature coming soon!');
}

async function openPDFCategory(category) {
    // TODO: Open PDF category browser
    await lcarsAlert(`PDF category ${category} feature coming soon!`);
}

// System Controls
async function loadSystemInfo() {
    await updateSystemStats();
    await updateSystemUptime();
}

function showSystemInfo() {
    // Already shown in system section
    switchSection('system');
}

async function rebootSystem() {
    const confirmed = await lcarsConfirm('Are you sure you want to reboot the system?');
    if (!confirmed) return;

    try {
        await fetch(`/api/system/reboot`, { method: 'POST' });
        await lcarsAlert('System rebooting...');
    } catch (error) {
        console.error('Failed to reboot system:', error);
    }
}

async function shutdownSystem() {
    const confirmed = await lcarsConfirm('Are you sure you want to shutdown the system?');
    if (!confirmed) return;

    try {
        await fetch(`/api/system/shutdown`, { method: 'POST' });
        await lcarsAlert('System shutting down...');
    } catch (error) {
        console.error('Failed to shutdown system:', error);
    }
}

async function systemStandby() {
    await enterStandby();
    try {
        await fetch(`/api/system/standby`, { method: 'POST' });
    } catch (error) {
        console.error('Failed to set system standby:', error);
    }
}

// Pironman Controls
async function loadPironmanStatus() {
    try {
        const response = await fetch(`/api/pironman/status`);
        const data = await response.json();

        updateElement('fan-status', data.fan.mode.toUpperCase());
        updateElement('display-status', data.display.on ? 'ON' : 'OFF');

        // Fan RGB LED status
        const fanRgbLedStatus = data.fan.rgb_led || 'follow';
        updateElement('fan-rgb-led-status', fanRgbLedStatus.toUpperCase());

        // RGB status (neopixels)
        updateElement('rgb-status', data.rgb.on ? 'ON' : 'OFF');
        updateElement('rgb-style-display', data.rgb.style.toUpperCase().replace('_', ' '));
        updateElement('rgb-brightness-display', `${data.rgb.brightness}%`);

        // Update RGB color picker and hex input
        const colorPicker = document.getElementById('rgb-color-picker');
        const colorHex = document.getElementById('rgb-color-hex');
        if (colorPicker && data.rgb.color) {
            colorPicker.value = `#${data.rgb.color}`;
        }
        if (colorHex && data.rgb.color) {
            colorHex.value = data.rgb.color;
        }

        // Update RGB brightness slider
        const rgbBrightnessSlider = document.getElementById('rgb-brightness-slider');
        const rgbBrightnessValue = document.getElementById('rgb-brightness-value');
        if (rgbBrightnessSlider) rgbBrightnessSlider.value = data.rgb.brightness;
        if (rgbBrightnessValue) rgbBrightnessValue.textContent = `${data.rgb.brightness}%`;

        // Update RGB speed slider
        const rgbSpeedSlider = document.getElementById('rgb-speed-slider');
        const rgbSpeedValue = document.getElementById('rgb-speed-value');
        if (rgbSpeedSlider) rgbSpeedSlider.value = data.rgb.speed;
        if (rgbSpeedValue) rgbSpeedValue.textContent = `${data.rgb.speed}%`;
    } catch (error) {
        console.error('Failed to load Pironman status:', error);
    }
}

async function setFanMode(mode) {
    try {
        await fetch(`/api/pironman/fan`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ mode })
        });
        loadPironmanStatus();
    } catch (error) {
        console.error('Failed to set fan mode:', error);
    }
}

async function setFanRGB(state) {
    try {
        await fetch(`/api/pironman/fan-rgb`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ state })
        });
        loadPironmanStatus();
    } catch (error) {
        console.error('Failed to set fan RGB:', error);
    }
}

async function setDisplay(state) {
    try {
        await fetch(`/api/pironman/display`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ state })
        });
        loadPironmanStatus();
    } catch (error) {
        console.error('Failed to set display:', error);
    }
}

async function setRGBColor(color) {
    // Remove # if present
    const hexColor = color.replace('#', '');

    // Update hex input
    const colorHex = document.getElementById('rgb-color-hex');
    if (colorHex) colorHex.value = hexColor;

    try {
        await fetch(`/api/pironman/fan-rgb-color`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ color: hexColor })
        });
        loadPironmanStatus();
    } catch (error) {
        console.error('Failed to set RGB color:', error);
    }
}

async function setRGBColorFromHex(hexColor) {
    // Remove # if present and validate
    hexColor = hexColor.replace('#', '').toLowerCase();

    if (hexColor.length !== 6 || !/^[0-9a-f]{6}$/.test(hexColor)) {
        await lcarsAlert('Invalid hex color format. Use 6 hex digits (e.g., ff0000)');
        return;
    }

    // Update color picker
    const colorPicker = document.getElementById('rgb-color-picker');
    if (colorPicker) colorPicker.value = `#${hexColor}`;

    try {
        await fetch(`/api/pironman/fan-rgb-color`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ color: hexColor })
        });
        loadPironmanStatus();
    } catch (error) {
        console.error('Failed to set RGB color:', error);
    }
}

async function setRGBStyle(style) {
    try {
        await fetch(`/api/pironman/fan-rgb-style`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ style })
        });
        loadPironmanStatus();
    } catch (error) {
        console.error('Failed to set RGB style:', error);
    }
}

async function setRGBBrightness(value) {
    const valueEl = document.getElementById('rgb-brightness-value');
    if (valueEl) valueEl.textContent = `${value}%`;

    try {
        await fetch(`/api/pironman/fan-rgb-brightness`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ brightness: parseInt(value) })
        });
        loadPironmanStatus();
    } catch (error) {
        console.error('Failed to set RGB brightness:', error);
    }
}

async function setRGBSpeed(value) {
    const valueEl = document.getElementById('rgb-speed-value');
    if (valueEl) valueEl.textContent = `${value}%`;

    try {
        await fetch(`/api/pironman/fan-rgb-speed`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ speed: parseInt(value) })
        });
        loadPironmanStatus();
    } catch (error) {
        console.error('Failed to set RGB speed:', error);
    }
}

async function setFanRGBLED(state) {
    try {
        await fetch(`/api/pironman/fan-rgb-led`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ state })
        });
        loadPironmanStatus();
    } catch (error) {
        console.error('Failed to set fan RGB LED:', error);
    }
}

// Minecraft Server
async function loadMinecraftStatus() {
    try {
        const response = await fetch(`/api/minecraft/status`);
        const data = await response.json();

        const mcStatusEl = document.getElementById('mc-status');
        if (mcStatusEl) {
            const isRunning = data.running;
            mcStatusEl.textContent = isRunning ? 'RUNNING' : 'STOPPED';
            // Blink if running (to show it's active) - faster blink
            if (isRunning) {
                mcStatusEl.classList.remove('blink-slow');
                mcStatusEl.classList.add('blink-fast');
            } else {
                mcStatusEl.classList.remove('blink-fast', 'blink-slow');
            }
        }

        // Update RAM usage
        const ramEl = document.getElementById('mc-ram-usage');
        if (ramEl) {
            ramEl.textContent = data.ramUsage || '--';
        }

        // Update player count
        const playersEl = document.getElementById('mc-players');
        if (playersEl) {
            playersEl.textContent = `${data.players || 0} / ${data.maxPlayers || 0}`;
        }

        // Update IP
        const ipEl = document.getElementById('mc-ip');
        if (ipEl) {
            ipEl.textContent = data.ip || '--';
        }
    } catch (error) {
        console.error('Failed to load Minecraft status:', error);
    }
}

async function mcStart() {
    try {
        await fetch(`/api/minecraft/start`, { method: 'POST' });
        loadMinecraftStatus();
    } catch (error) {
        console.error('Failed to start Minecraft server:', error);
    }
}

async function mcStop() {
    const confirmed = await lcarsConfirm('Are you sure you want to stop the Minecraft server?');
    if (!confirmed) return;

    try {
        await fetch(`/api/minecraft/stop`, { method: 'POST' });
        loadMinecraftStatus();
    } catch (error) {
        console.error('Failed to stop Minecraft server:', error);
    }
}

async function mcRestart() {
    const confirmed = await lcarsConfirm('Are you sure you want to restart the Minecraft server?');
    if (!confirmed) return;

    try {
        await fetch(`/api/minecraft/restart`, { method: 'POST' });
        loadMinecraftStatus();
    } catch (error) {
        console.error('Failed to restart Minecraft server:', error);
    }
}

async function showMCLog() {
    try {
        const response = await fetch(`/api/minecraft/log?lines=100`);
        const data = await response.json();

        if (data.error) {
            await lcarsAlert(`Error: ${data.error}`);
            return;
        }

        // Create a simple log viewer window
        const logWindow = window.open('', 'Minecraft Log', 'width=800,height=600,scrollbars=yes');
        if (logWindow) {
            logWindow.document.write(`
                <html>
                    <head>
                        <title>Minecraft Server Log</title>
                        <style>
                            body { 
                                font-family: monospace; 
                                background: #000; 
                                color: #0f0; 
                                padding: 20px;
                                font-size: 12px;
                            }
                            pre { white-space: pre-wrap; word-wrap: break-word; }
                        </style>
                    </head>
                    <body>
                        <h2>Minecraft Server Log (Last ${data.lines.length} lines)</h2>
                        <pre>${data.lines.join('')}</pre>
                    </body>
                </html>
            `);
        }
    } catch (error) {
        console.error('Failed to load log:', error);
        await lcarsAlert('Failed to load server log');
    }
}

async function mcBackup() {
    try {
        await fetch(`/api/minecraft/backup`, { method: 'POST' });
        await lcarsAlert('Backup triggered');
    } catch (error) {
        console.error('Failed to trigger backup:', error);
    }
}

// Navidrome Server
async function loadNavidromeStatus() {
    try {
        const response = await fetch(`/api/music/status`);
        const data = await response.json();

        const statusEl = document.getElementById('navidrome-status');
        const versionEl = document.getElementById('navidrome-version');

        if (statusEl) {
            if (data.connected) {
                statusEl.textContent = 'RUNNING';
                statusEl.classList.remove('blink-slow');
                statusEl.className = 'font-green';
            } else {
                statusEl.textContent = 'STOPPED';
                statusEl.classList.add('blink-slow');
                statusEl.className = 'font-red';
            }
        }

        if (versionEl && data.version) {
            versionEl.textContent = data.version;

            const navIpEl = document.getElementById("navidrome-ip");
            if (navIpEl && data.ip) {
                navIpEl.textContent = data.ip;
            }
        }
    } catch (error) {
        console.error('Failed to load Navidrome status:', error);
        updateElement('navidrome-status', 'ERROR');
    }
}

async function navidromeStart() {
    try {
        await fetch(`/api/servers/navidrome/start`, { method: 'POST' });
        await lcarsAlert('Navidrome starting...');
        setTimeout(() => loadNavidromeStatus(), 2000);
    } catch (error) {
        console.error('Failed to start Navidrome:', error);
        await lcarsAlert('Failed to start Navidrome');
    }
}

async function navidromeStop() {
    const confirmed = await lcarsConfirm('Are you sure you want to stop Navidrome?');
    if (!confirmed) return;

    try {
        await fetch(`/api/servers/navidrome/stop`, { method: 'POST' });
        await lcarsAlert('Navidrome stopping...');
        setTimeout(() => loadNavidromeStatus(), 2000);
    } catch (error) {
        console.error('Failed to stop Navidrome:', error);
        await lcarsAlert('Failed to stop Navidrome');
    }
}

async function navidromeRestart() {
    const confirmed = await lcarsConfirm('Are you sure you want to restart Navidrome?');
    if (!confirmed) return;

    try {
        await fetch(`/api/servers/navidrome/restart`, { method: 'POST' });
        await lcarsAlert('Navidrome restarting...');
        setTimeout(() => loadNavidromeStatus(), 3000);
    } catch (error) {
        console.error('Failed to restart Navidrome:', error);
        await lcarsAlert('Failed to restart Navidrome');
    }
}

async function navidromeLogs() {
    try {
        const response = await fetch(`/api/servers/navidrome/logs?lines=100`);
        const data = await response.json();

        if (data.error) {
            await lcarsAlert(`Error: ${data.error}`);
            return;
        }

        const logWindow = window.open('', 'Navidrome Logs', 'width=800,height=600,scrollbars=yes');
        if (logWindow) {
            logWindow.document.write(`
                <html>
                    <head>
                        <title>Navidrome Logs</title>
                        <style>
                            body { 
                                font-family: monospace; 
                                background: #000; 
                                color: #0f0; 
                                padding: 20px;
                                font-size: 12px;
                            }
                            pre { white-space: pre-wrap; word-wrap: break-word; }
                        </style>
                    </head>
                    <body>
                        <h2>Navidrome Logs (Last ${data.lines.length} lines)</h2>
                        <pre>${data.lines.join('')}</pre>
                    </body>
                </html>
            `);
        }
    } catch (error) {
        console.error('Failed to load Navidrome logs:', error);
        await lcarsAlert('Failed to load Navidrome logs');
    }
}

// Nextcloud Server
async function loadNextcloudStatus() {
    try {
        const response = await fetch(`/api/servers/nextcloud/status`);
        const data = await response.json();

        const statusEl = document.getElementById('nextcloud-status');
        const versionEl = document.getElementById('nextcloud-version');

        if (statusEl) {
            if (data.running) {
                statusEl.textContent = 'RUNNING';
                statusEl.classList.remove('blink-slow');
                statusEl.className = 'font-green';
            } else {
                statusEl.textContent = 'STOPPED';
                statusEl.classList.add('blink-slow');
                statusEl.className = 'font-red';
            }
        }

        if (versionEl && data.version) {
            versionEl.textContent = data.version;

            const ncIpEl = document.getElementById("nextcloud-ip");
            if (ncIpEl && data.ip) {
                ncIpEl.textContent = data.ip;
            }
        }
    } catch (error) {
        console.error('Failed to load Nextcloud status:', error);
        updateElement('nextcloud-status', 'ERROR');
    }
}

async function nextcloudStart() {
    try {
        await fetch(`/api/servers/nextcloud/start`, { method: 'POST' });
        await lcarsAlert('Nextcloud starting...');
        setTimeout(() => loadNextcloudStatus(), 2000);
    } catch (error) {
        console.error('Failed to start Nextcloud:', error);
        await lcarsAlert('Failed to start Nextcloud');
    }
}

async function nextcloudStop() {
    const confirmed = await lcarsConfirm('Are you sure you want to stop Nextcloud?');
    if (!confirmed) return;

    try {
        await fetch(`/api/servers/nextcloud/stop`, { method: 'POST' });
        await lcarsAlert('Nextcloud stopping...');
        setTimeout(() => loadNextcloudStatus(), 2000);
    } catch (error) {
        console.error('Failed to stop Nextcloud:', error);
        await lcarsAlert('Failed to stop Nextcloud');
    }
}

async function nextcloudRestart() {
    const confirmed = await lcarsConfirm('Are you sure you want to restart Nextcloud?');
    if (!confirmed) return;

    try {
        await fetch(`/api/servers/nextcloud/restart`, { method: 'POST' });
        await lcarsAlert('Nextcloud restarting...');
        setTimeout(() => loadNextcloudStatus(), 3000);
    } catch (error) {
        console.error('Failed to restart Nextcloud:', error);
        await lcarsAlert('Failed to restart Nextcloud');
    }
}

async function nextcloudLogs() {
    try {
        const response = await fetch(`/api/servers/nextcloud/logs?lines=100`);
        const data = await response.json();

        if (data.error) {
            await lcarsAlert(`Error: ${data.error}`);
            return;
        }

        const logWindow = window.open('', 'Nextcloud Logs', 'width=800,height=600,scrollbars=yes');
        if (logWindow) {
            logWindow.document.write(`
                <html>
                    <head>
                        <title>Nextcloud Logs</title>
                        <style>
                            body { 
                                font-family: monospace; 
                                background: #000; 
                                color: #0f0; 
                                padding: 20px;
                                font-size: 12px;
                            }
                            pre { white-space: pre-wrap; word-wrap: break-word; }
                        </style>
                    </head>
                    <body>
                        <h2>Nextcloud Logs (Last ${data.lines.length} lines)</h2>
                        <pre>${data.lines.join('')}</pre>
                    </body>
                </html>
            `);
        }
    } catch (error) {
        console.error('Failed to load Nextcloud logs:', error);
        await lcarsAlert('Failed to load Nextcloud logs');
    }
}

// Music Player
let musicPlayer = null;
let currentTrack = null;
let musicStatusInterval = null;

async function loadMusicStatus() {
    try {
        const response = await fetch(`/api/music/status`);
        const data = await response.json();

        const statusEl = document.getElementById('music-status');
        if (statusEl) {
            if (data.connected) {
                statusEl.textContent = 'CONNECTED';
                statusEl.classList.remove('blink-slow');
                statusEl.className = 'font-green';
            } else {
                statusEl.textContent = 'NOT CONNECTED';
                statusEl.classList.add('blink-slow');
                statusEl.className = 'font-red';
            }
        }

        // Load now playing if connected
        if (data.connected) {
            loadNowPlaying();
        }
    } catch (error) {
        console.error('Failed to load music status:', error);
        updateElement('music-status', 'ERROR');
    }
}

async function loadNowPlaying() {
    try {
        const response = await fetch(`/api/music/now-playing`);
        const data = await response.json();

        if (data.playing && data.title) {
            updateElement('music-track-title', data.title);
            updateElement('music-track-artist', data.artist || 'Unknown Artist');
            updateElement('music-track-album', data.album || 'Unknown Album');
            currentTrack = data;
        } else if (currentTrack && currentTrack.title) {
            // If API doesn't have now playing but we have track info, keep showing it
            updateElement('music-track-title', currentTrack.title);
            updateElement('music-track-artist', currentTrack.artist || '--');
            updateElement('music-track-album', currentTrack.album || '--');
        } else {
            // Only clear if we don't have any track info
            if (!musicPlayer || musicPlayer.paused || musicPlayer.ended) {
                updateElement('music-track-title', '--');
                updateElement('music-track-artist', '--');
                updateElement('music-track-album', '--');
            }
        }
    } catch (error) {
        console.error('Failed to load now playing:', error);
        // Keep current track info if API fails
        if (currentTrack && currentTrack.title) {
            updateElement('music-track-title', currentTrack.title);
            updateElement('music-track-artist', currentTrack.artist || '--');
            updateElement('music-track-album', currentTrack.album || '--');
        }
    }
}

async function loadMusicPlaylists() {
    try {
        const response = await fetch(`/api/music/playlists`);
        const playlists = await response.json();

        const playlistsEl = document.getElementById('music-playlists');
        if (!playlistsEl) return;

        if (playlists.error) {
            playlistsEl.innerHTML = `<p class="flush uppercase font-red">Error: ${playlists.error}</p>`;
            return;
        }

        if (playlists.length === 0) {
            playlistsEl.innerHTML = '<p class="flush uppercase go-big font-golden-orange">No playlists found</p>';
            return;
        }

        let html = '';
        playlists.forEach(playlist => {
            const duration = Math.floor(playlist.duration / 60);
            html += `
                <div class="status-card" style="margin-bottom: 20px; cursor: pointer;" onclick="loadPlaylist('${playlist.id}')">
                    <div class="lcars-text-bar">
                        <h3>${playlist.name.toUpperCase()}</h3>
                    </div>
                    <p><span class="font-green">SONGS:</span> <span class="font-golden-orange">${playlist.songCount}</span></p>
                    <p><span class="font-green">DURATION:</span> <span class="font-golden-orange">${duration} MIN</span></p>
                </div>
            `;
        });

        playlistsEl.innerHTML = html;
    } catch (error) {
        console.error('Failed to load playlists:', error);
        const playlistsEl = document.getElementById('music-playlists');
        if (playlistsEl) {
            playlistsEl.innerHTML = '<p class="flush uppercase font-red">Failed to load playlists</p>';
        }
    }
}

async function loadPlaylist(playlistId) {
    try {
        const response = await fetch(`/api/music/playlist/${playlistId}`);
        const playlist = await response.json();

        if (playlist.error) {
            await lcarsAlert(`Error: ${playlist.error}`);
            return;
        }

        // Show playlist tracks in search results area
        const resultsEl = document.getElementById('music-search-results');
        if (!resultsEl) return;

        let html = `<div class="lcars-text-bar" style="margin-bottom: 15px;"><h3>${playlist.name} (${playlist.songCount} tracks)</h3></div>`;

        playlist.tracks.forEach(track => {
            html += `
                <div class="status-card" style="margin-bottom: 10px; cursor: pointer; padding: 15px;" onclick="playTrack('${track.id}', '${track.title.replace(/'/g, "\\'")}', '${(track.artist || '').replace(/'/g, "\\'")}', '${(track.album || '').replace(/'/g, "\\'")}')">
                    <p class="flush uppercase font-golden-orange">${track.title}</p>
                    <p class="flush">${track.artist} - ${track.album}</p>
                    <p class="flush" style="font-size: 0.9em; color: var(--lcars-light-gray);">${Math.floor(track.duration / 60)}:${String(track.duration % 60).padStart(2, '0')}</p>
                </div>
            `;
        });

        resultsEl.innerHTML = html;
    } catch (error) {
        console.error('Failed to load playlist:', error);
        await lcarsAlert('Failed to load playlist');
    }
}

async function musicSearch() {
    const query = document.getElementById('music-search-input').value.trim();
    if (!query) {
        await lcarsAlert('Please enter a search query');
        return;
    }

    try {
        const response = await fetch(`/api/music/search?q=${encodeURIComponent(query)}`);
        const results = await response.json();

        if (results.error) {
            await lcarsAlert(`Error: ${results.error}`);
            return;
        }

        const resultsEl = document.getElementById('music-search-results');
        if (!resultsEl) return;

        let html = '';

        if (results.songs && results.songs.length > 0) {
            html += '<div class="lcars-text-bar" style="margin-bottom: 30px;"><h3>Songs</h3></div>';
            results.songs.forEach(song => {
                html += `
                    <div class="status-card" style="margin-bottom: 10px; cursor: pointer; padding: 15px;" onclick="playTrack('${song.id}', '${song.title.replace(/'/g, "\\'")}', '${(song.artist || '').replace(/'/g, "\\'")}', '${(song.album || '').replace(/'/g, "\\'")}')">
                        <p class="flush uppercase font-golden-orange">${song.title}</p>
                        <p class="flush">${song.artist} - ${song.album}</p>
                        <p class="flush" style="font-size: 0.9em; color: var(--lcars-light-gray);">${Math.floor(song.duration / 60)}:${String(song.duration % 60).padStart(2, '0')}</p>
                    </div>
                `;
            });
        }

        if (results.albums && results.albums.length > 0) {
            html += '<div class="lcars-text-bar" style="margin-top: 30px; margin-bottom: 15px;"><h3>Albums</h3></div>';
            results.albums.forEach(album => {
                html += `
                    <div class="status-card" style="margin-bottom: 10px; padding: 15px;">
                        <p class="flush uppercase font-golden-orange">${album.name}</p>
                        <p class="flush">${album.artist}</p>
                        <p class="flush" style="font-size: 0.9em; color: var(--lcars-light-gray);">${album.songCount} tracks</p>
                    </div>
                `;
            });
        }

        if (results.artists && results.artists.length > 0) {
            html += '<div class="lcars-text-bar" style="margin-top: 30px; margin-bottom: 15px;"><h3>Artists</h3></div>';
            results.artists.forEach(artist => {
                html += `
                    <div class="status-card" style="margin-bottom: 10px; padding: 15px;">
                        <p class="flush uppercase font-golden-orange">${artist.name}</p>
                        <p class="flush" style="font-size: 0.9em; color: var(--lcars-light-gray);">${artist.albumCount} albums</p>
                    </div>
                `;
            });
        }

        if (!html) {
            html = '<p class="flush uppercase font-golden-orange">No results found</p>';
        }

        resultsEl.innerHTML = html;
    } catch (error) {
        console.error('Failed to search:', error);
        await lcarsAlert('Failed to search');
    }
}

async function playTrack(trackId, title, artist, album) {
    try {
        // Store track info for now playing display
        if (title && artist && album) {
            currentTrack = {
                id: trackId,
                title: title,
                artist: artist,
                album: album
            };
            // Update now playing immediately
            updateElement('music-track-title', title);
            updateElement('music-track-artist', artist);
            updateElement('music-track-album', album);
        }

        // URL encode the track ID to handle special characters
        const encodedTrackId = encodeURIComponent(trackId);
        const streamUrl = `/api/music/stream/${encodedTrackId}`;

        console.log('Playing track:', trackId, 'URL:', streamUrl);

        // Get or create audio player
        musicPlayer = document.getElementById('music-player');
        if (!musicPlayer) {
            musicPlayer = document.createElement('audio');
            musicPlayer.id = 'music-player';
            musicPlayer.preload = 'none';
            musicPlayer.style.display = 'none';
            document.body.appendChild(musicPlayer);
        }

        // Clear previous error handlers
        musicPlayer.onerror = null;
        musicPlayer.onloadstart = null;
        musicPlayer.oncanplay = null;

        // Add comprehensive error handlers
        musicPlayer.onerror = (e) => {
            console.error('Audio playback error:', e, musicPlayer.error);
            const errorCode = musicPlayer.error ? musicPlayer.error.code : 'unknown';
            let errorMsg = 'Unknown error';

            if (musicPlayer.error) {
                switch (musicPlayer.error.code) {
                    case 1: errorMsg = 'MEDIA_ERR_ABORTED - User aborted'; break;
                    case 2: errorMsg = 'MEDIA_ERR_NETWORK - Network error'; break;
                    case 3: errorMsg = 'MEDIA_ERR_DECODE - Decode error (unsupported format?)'; break;
                    case 4: errorMsg = 'MEDIA_ERR_SRC_NOT_SUPPORTED - Source not supported'; break;
                    default: errorMsg = musicPlayer.error.message || 'Unknown error';
                }
            }
            lcarsAlert(`Playback error (${errorCode}): ${errorMsg}`);
        };

        // Add load event handlers for debugging
        musicPlayer.onloadstart = () => {
            console.log('Audio load started');
        };

        musicPlayer.oncanplay = () => {
            console.log('Audio can play');
        };

        // Set source and play
        musicPlayer.src = streamUrl;
        musicPlayer.load();

        // Wait a bit for the audio to load before playing
        await new Promise((resolve) => {
            if (musicPlayer.readyState >= 2) { // HAVE_CURRENT_DATA
                resolve();
            } else {
                musicPlayer.addEventListener('canplay', () => resolve(), { once: true });
                musicPlayer.addEventListener('error', () => resolve(), { once: true });
                // Timeout after 5 seconds
                setTimeout(() => resolve(), 5000);
            }
        });

        try {
            await musicPlayer.play();
            console.log('Track playing successfully');
        } catch (playError) {
            console.error('Play error:', playError);
            const errorMsg = playError.message || 'Could not play track. Check browser console for details.';
            await lcarsAlert(`Failed to play: ${errorMsg}`);
            return;
        }

        // Update now playing immediately with track info
        if (currentTrack) {
            updateElement('music-track-title', currentTrack.title || '--');
            updateElement('music-track-artist', currentTrack.artist || '--');
            updateElement('music-track-album', currentTrack.album || '--');
        }

        // Also try to load from API
        loadNowPlaying();

        // Set up periodic updates for now playing
        if (musicStatusInterval) {
            clearInterval(musicStatusInterval);
        }
        musicStatusInterval = setInterval(() => {
            loadNowPlaying();
        }, 3000); // Update every 3 seconds
    } catch (error) {
        console.error('Failed to play track:', error);
        await lcarsAlert(`Failed to play track: ${error.message || error}`);
    }
}

function musicToggle() {
    if (musicPlayer) {
        if (musicPlayer.paused) {
            musicPlay();
        } else {
            musicPause();
        }
    }
}

function updateMusicButtonState() {
    const playIcon = document.getElementById('music-play-icon');
    const pauseIcon = document.getElementById('music-pause-icon');

    if (musicPlayer && !musicPlayer.paused) {
        if (playIcon) playIcon.style.display = 'none';
        if (pauseIcon) pauseIcon.style.display = 'block';
    } else {
        if (playIcon) playIcon.style.display = 'block';
        if (pauseIcon) pauseIcon.style.display = 'none';
    }
}

function musicPlay() {
    if (musicPlayer) {
        musicPlayer.play().catch(err => console.error('Play failed:', err));
        updateMusicButtonState();
    }
}

function musicPause() {
    if (musicPlayer) {
        musicPlayer.pause();
        updateMusicButtonState();
    }
}

function musicStop() {
    if (musicPlayer) {
        musicPlayer.pause();
        musicPlayer.currentTime = 0;
        updateMusicButtonState();
    }
}

async function musicPrevious() {
    // TODO: Implement previous track
    await lcarsAlert('Previous track feature coming soon!');
}

async function musicNext() {
    // TODO: Implement next track
    await lcarsAlert('Next track feature coming soon!');
}

async function openMusicFolder() {
    try {
        const response = await fetch(`/api/music/open-music-folder`, { method: 'POST' });
        const data = await response.json();

        if (data.error) {
            await lcarsAlert(`Error: ${data.error}`);
        } else {
            await lcarsAlert(`Music folder opened: ${data.folder}`);
        }
    } catch (error) {
        console.error('Failed to open music folder:', error);
        await lcarsAlert('Failed to open music folder');
    }
}

async function triggerMusicScan() {
    try {
        const response = await fetch(`/api/music/scan`, { method: 'POST' });
        const data = await response.json();

        if (data.error) {
            await lcarsAlert(`Error: ${data.error}`);
        } else {
            await lcarsAlert(data.message || 'Library scan started. This may take a few minutes.');
            // Reload playlists after a delay
            setTimeout(() => {
                loadMusicPlaylists();
            }, 5000);
        }
    } catch (error) {
        console.error('Failed to trigger scan:', error);
        await lcarsAlert('Failed to trigger library scan');
    }
}

// Standby Configuration Management
async function getStandbyConfig() {
    try {
        const response = await fetch(`/api/system/settings`);
        const settings = await response.json();
        if (settings.standbyConfig) {
            return settings.standbyConfig;
        }
    } catch (e) {
        console.error('Failed to fetch settings from backend:', e);
    }

    const saved = localStorage.getItem('wtl-s-lcars-standby-config');
    if (saved) {
        try {
            return JSON.parse(saved);
        } catch (e) {
            console.error('Failed to parse standby config:', e);
        }
    }
    return { ...DEFAULT_STANDBY_CONFIG };
}

async function saveStandbyConfig(config) {
    localStorage.setItem('wtl-s-lcars-standby-config', JSON.stringify(config));

    // Also save to backend
    try {
        const currentSettingsResponse = await fetch(`/api/system/settings`);
        const settings = await currentSettingsResponse.json();
        settings.standbyConfig = config;

        await fetch(`/api/system/settings`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(settings)
        });
    } catch (e) {
        console.error('Failed to save settings to backend:', e);
    }
}

async function setStandbyConfig(key, value) {
    const config = await getStandbyConfig();
    config[key] = value;
    await saveStandbyConfig(config);
    updateStandbyConfigUI();
}

async function loadStandbyConfig() {
    updateStandbyConfigUI();
}

async function updateStandbyConfigUI() {
    const config = await getStandbyConfig();

    // Update display buttons
    const displayOffBtn = document.getElementById('standby-display-off');
    const displayOnBtn = document.getElementById('standby-display-on');
    const displayStatus = document.getElementById('standby-display-status');
    if (displayOffBtn && displayOnBtn && displayStatus) {
        if (config.display === 'off') {
            displayOffBtn.classList.add('active');
            displayOnBtn.classList.remove('active');
            displayStatus.textContent = 'TURN OFF';
        } else {
            displayOffBtn.classList.remove('active');
            displayOnBtn.classList.add('active');
            displayStatus.textContent = 'KEEP ON';
        }
    }

    // Update lights buttons
    const lightsOffBtn = document.getElementById('standby-lights-off');
    const lightsOnBtn = document.getElementById('standby-lights-on');
    const lightsStatus = document.getElementById('standby-lights-status');
    if (lightsOffBtn && lightsOnBtn && lightsStatus) {
        if (config.lights === 'off') {
            lightsOffBtn.classList.add('active');
            lightsOnBtn.classList.remove('active');
            lightsStatus.textContent = 'TURN OFF';
        } else {
            lightsOffBtn.classList.remove('active');
            lightsOnBtn.classList.add('active');
            lightsStatus.textContent = 'KEEP ON';
        }
    }

    // Update fan buttons
    const fanAutoBtn = document.getElementById('standby-fan-auto');
    const fanOnBtn = document.getElementById('standby-fan-on');
    const fanOffBtn = document.getElementById('standby-fan-off');
    const fanStatus = document.getElementById('standby-fan-status');
    if (fanAutoBtn && fanOnBtn && fanOffBtn && fanStatus) {
        fanAutoBtn.classList.remove('active');
        fanOnBtn.classList.remove('active');
        fanOffBtn.classList.remove('active');

        if (config.fan === 'auto') {
            fanAutoBtn.classList.add('active');
            fanStatus.textContent = 'AUTO';
        } else if (config.fan === 'on') {
            fanOnBtn.classList.add('active');
            fanStatus.textContent = 'ON';
        } else {
            fanOffBtn.classList.add('active');
            fanStatus.textContent = 'OFF';
        }
    }

    // Update Minecraft buttons
    const mcKeepBtn = document.getElementById('standby-minecraft-keep');
    const mcStopBtn = document.getElementById('standby-minecraft-stop');
    const mcStatus = document.getElementById('standby-minecraft-status');
    if (mcKeepBtn && mcStopBtn && mcStatus) {
        if (config.minecraft === 'keep') {
            mcKeepBtn.classList.add('active');
            mcStopBtn.classList.remove('active');
            mcStatus.textContent = 'KEEP RUNNING';
        } else {
            mcKeepBtn.classList.remove('active');
            mcStopBtn.classList.add('active');
            mcStatus.textContent = 'STOP';
        }
    }
}

// Settings
async function loadSettings() {
    try {
        const response = await fetch(`/api/system/settings`);
        const settings = await response.json();

        if (settings.volume !== undefined) {
            setVolume(settings.volume, false);
        } else {
            const savedVolume = localStorage.getItem('wtl-s-lcars-volume');
            if (savedVolume !== null) {
                setVolume(parseInt(savedVolume), false);
            }
        }

        if (settings.standbyTimeout !== undefined) {
            setStandbyTimeout(settings.standbyTimeout, false);
        } else {
            const savedTimeout = localStorage.getItem('wtl-s-lcars-standby-timeout');
            if (savedTimeout !== null) {
                setStandbyTimeout(parseInt(savedTimeout), false);
            }
        }
    } catch (e) {
        console.error('Failed to load settings from backend:', e);
    }

    // Load fullscreen state (check after a small delay to ensure DOM is ready)
    setTimeout(updateFullscreenButton, 100);
}


function showSystemSettings() {
    // Already shown in system section
    switchSection('system');
}

// Volume Control
async function setVolume(value, save = true) {
    const volume = parseInt(value);
    const volumePercent = volume + '%';

    // Update all audio elements
    const audioElements = document.querySelectorAll('audio');
    audioElements.forEach(audio => {
        audio.volume = volume / 100;
    });

    // Update display
    const volumeDisplay = document.getElementById('volume-display');
    const volumeValue = document.getElementById('volume-value');
    const volumeSlider = document.getElementById('volume-slider');

    if (volumeDisplay) volumeDisplay.textContent = volumePercent;
    if (volumeValue) volumeValue.textContent = volumePercent;
    if (volumeSlider) volumeSlider.value = volume;

    // Save to localStorage
    if (save) {
        localStorage.setItem('wtl-s-lcars-volume', volume.toString());

        // Also save to backend
        try {
            const currentSettingsResponse = await fetch(`/api/system/settings`);
            const settings = await currentSettingsResponse.json();
            settings.volume = volume;

            await fetch(`/api/system/settings`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(settings)
            });
        } catch (e) {
            console.error('Failed to save volume to backend:', e);
        }
    }
}

// Standby Timeout Control
async function setStandbyTimeout(minutes, save = true) {
    const mins = parseInt(minutes);
    STANDBY_DELAY = mins * 60 * 1000; // Convert to milliseconds

    // Update display
    const timeoutDisplay = document.getElementById('standby-timeout-display');
    const timeoutValue = document.getElementById('standby-timeout-value');
    const timeoutSlider = document.getElementById('standby-timeout-slider');

    const displayText = mins === 1 ? '1 MIN' : `${mins} MINS`;

    if (timeoutDisplay) timeoutDisplay.textContent = displayText;
    if (timeoutValue) timeoutValue.textContent = displayText;
    if (timeoutSlider) timeoutSlider.value = mins;

    // Reset standby timeout with new delay
    resetStandbyTimeout();

    // Save to localStorage
    if (save) {
        localStorage.setItem('wtl-s-lcars-standby-timeout', mins.toString());

        // Also save to backend
        try {
            const currentSettingsResponse = await fetch(`/api/system/settings`);
            const settings = await currentSettingsResponse.json();
            settings.standbyTimeout = mins;

            await fetch(`/api/system/settings`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(settings)
            });
        } catch (e) {
            console.error('Failed to save timeout to backend:', e);
        }
    }
}

// Fullscreen Control
function toggleFullscreen() {
    if (!document.fullscreenElement && !document.webkitFullscreenElement &&
        !document.mozFullScreenElement && !document.msFullscreenElement) {
        // Enter fullscreen
        if (document.documentElement.requestFullscreen) {
            document.documentElement.requestFullscreen();
        } else if (document.documentElement.webkitRequestFullscreen) {
            document.documentElement.webkitRequestFullscreen();
        } else if (document.documentElement.mozRequestFullScreen) {
            document.documentElement.mozRequestFullScreen();
        } else if (document.documentElement.msRequestFullscreen) {
            document.documentElement.msRequestFullscreen();
        }
    } else {
        // Exit fullscreen
        if (document.exitFullscreen) {
            document.exitFullscreen();
        } else if (document.webkitExitFullscreen) {
            document.webkitExitFullscreen();
        } else if (document.mozCancelFullScreen) {
            document.mozCancelFullScreen();
        } else if (document.msExitFullscreen) {
            document.msExitFullscreen();
        }
    }
}

function updateFullscreenButton() {
    const isFullscreen = !!(document.fullscreenElement || document.webkitFullscreenElement ||
        document.mozFullScreenElement || document.msFullscreenElement);

    const fullscreenButton = document.getElementById('fullscreen-button');
    const fullscreenStatus = document.getElementById('fullscreen-status');

    if (fullscreenButton) {
        fullscreenButton.textContent = isFullscreen ? 'EXIT FULLSCREEN' : 'ENTER FULLSCREEN';
    }
    if (fullscreenStatus) {
        fullscreenStatus.textContent = isFullscreen ? 'ON' : 'OFF';
    }
}

// Listen for fullscreen changes
document.addEventListener('fullscreenchange', updateFullscreenButton);
document.addEventListener('webkitfullscreenchange', updateFullscreenButton);
document.addEventListener('mozfullscreenchange', updateFullscreenButton);
document.addEventListener('MSFullscreenChange', updateFullscreenButton);

// Keyboard shortcut for fullscreen (F11)
document.addEventListener('keydown', (e) => {
    if (e.key === 'F11') {
        e.preventDefault();
        toggleFullscreen();
    }
});

// Server Restart
async function restartServer() {
    const confirmed = await lcarsConfirm('Are you sure you want to restart the backend server and Nginx? The page will reload.');
    if (!confirmed) {
        return;
    }

    try {
        await fetch(`/api/system/restart-server`, { method: 'POST' });
        // Wait a moment for server to restart, then reload
        setTimeout(() => {
            location.reload();
        }, 2000);
    } catch (error) {
        console.error('Failed to restart server:', error);
        // Still reload after a delay in case server is restarting
        setTimeout(() => {
            location.reload();
        }, 3000);
    }
}

// LCARS Modal System
let lcarsModalResolve = null;
let lcarsModalType = 'alert'; // 'alert', 'confirm', 'prompt'

function lcarsAlert(message) {
    return new Promise((resolve) => {
        const modal = document.getElementById('lcars-modal');
        const title = document.getElementById('lcars-modal-title');
        const messageEl = document.getElementById('lcars-modal-message');
        const inputWrapper = document.getElementById('lcars-modal-input-wrapper');
        const footer = document.getElementById('lcars-modal-footer');
        const okBtn = document.getElementById('lcars-modal-ok');

        title.textContent = 'ALERT';
        messageEl.textContent = message;
        inputWrapper.style.display = 'none';

        // Clear footer and add OK button
        footer.innerHTML = '';
        okBtn.textContent = 'OK';
        footer.appendChild(okBtn);

        lcarsModalResolve = resolve;
        lcarsModalType = 'alert';
        modal.classList.remove('hidden');

        // Focus OK button
        setTimeout(() => okBtn.focus(), 100);
    });
}

function lcarsConfirm(message) {
    return new Promise((resolve) => {
        const modal = document.getElementById('lcars-modal');
        const title = document.getElementById('lcars-modal-title');
        const messageEl = document.getElementById('lcars-modal-message');
        const inputWrapper = document.getElementById('lcars-modal-input-wrapper');
        const footer = document.getElementById('lcars-modal-footer');

        title.textContent = 'CONFIRM';
        messageEl.textContent = message;
        inputWrapper.style.display = 'none';

        // Clear footer and add YES/NO buttons
        footer.innerHTML = '';
        const yesBtn = document.createElement('button');
        yesBtn.className = 'button-almond';
        yesBtn.textContent = 'YES';
        yesBtn.onclick = () => {
            lcarsModalClose();
            resolve(true);
        };

        const noBtn = document.createElement('button');
        noBtn.className = 'button-almond';
        noBtn.textContent = 'NO';
        noBtn.onclick = () => {
            lcarsModalClose();
            resolve(false);
        };

        footer.appendChild(yesBtn);
        footer.appendChild(noBtn);

        lcarsModalType = 'confirm';
        modal.classList.remove('hidden');

        // Focus YES button
        setTimeout(() => yesBtn.focus(), 100);
    });
}

function lcarsPrompt(message, defaultValue = '') {
    return new Promise((resolve) => {
        const modal = document.getElementById('lcars-modal');
        const title = document.getElementById('lcars-modal-title');
        const messageEl = document.getElementById('lcars-modal-message');
        const inputWrapper = document.getElementById('lcars-modal-input-wrapper');
        const input = document.getElementById('lcars-modal-input');
        const footer = document.getElementById('lcars-modal-footer');
        const okBtn = document.getElementById('lcars-modal-ok');

        title.textContent = 'INPUT';
        messageEl.textContent = message;
        input.value = defaultValue;
        inputWrapper.style.display = 'block';

        // Clear footer and add OK/CANCEL buttons
        footer.innerHTML = '';
        okBtn.textContent = 'OK';
        okBtn.onclick = () => {
            lcarsModalClose();
            resolve(input.value);
        };

        const cancelBtn = document.createElement('button');
        cancelBtn.className = 'button-almond';
        cancelBtn.textContent = 'CANCEL';
        cancelBtn.onclick = () => {
            lcarsModalClose();
            resolve(null);
        };

        footer.appendChild(okBtn);
        footer.appendChild(cancelBtn);

        lcarsModalResolve = resolve;
        lcarsModalType = 'prompt';
        modal.classList.remove('hidden');

        // Focus input
        setTimeout(() => input.focus(), 100);

        // Handle Enter key
        input.onkeydown = (e) => {
            if (e.key === 'Enter') {
                okBtn.click();
            } else if (e.key === 'Escape') {
                cancelBtn.click();
            }
        };
    });
}

function lcarsModalClose() {
    const modal = document.getElementById('lcars-modal');
    modal.classList.add('hidden');

    if (lcarsModalResolve && lcarsModalType === 'alert') {
        lcarsModalResolve();
        lcarsModalResolve = null;
    }
}

function lcarsModalOk() {
    if (lcarsModalType === 'alert') {
        lcarsModalClose();
    }
}

// Keyboard support for modals
document.addEventListener('keydown', (e) => {
    const modal = document.getElementById('lcars-modal');
    if (!modal.classList.contains('hidden')) {
        if (e.key === 'Escape') {
            lcarsModalClose();
        }
    }
});

// Helper Functions
function updateElement(id, text) {
    const el = document.getElementById(id);
    if (el) {
        el.textContent = text;
    }
}

