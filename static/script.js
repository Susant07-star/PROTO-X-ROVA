const API_BASE = window.location.origin + '/api';

// --- ELEMENT REFS ---
const statusDot = document.querySelector('.status-dot');
const statusText = document.getElementById('status-text');
const distVal = document.getElementById('dist-val');
const tempLegsVal = document.getElementById('temp-legs-val');
const tempArmsVal = document.getElementById('temp-arms-val');

// --- STATE ---
let isConnected = false;
let moveInterval = null;

// --- API CLIENT ---
async function callApi(endpoint, method, body) {
    try {
        const controller = new AbortController();
        const id = setTimeout(() => controller.abort(), 1000); // 1s timeout

        const response = await fetch(`${API_BASE}${endpoint}`, {
            method: method,
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(body),
            signal: controller.signal
        });
        clearTimeout(id);
        return response.ok;
    } catch (e) {
        console.error('API Error:', e);
        return false;
    }
}

async function sendMove(cmd, duration) {
    // Determine command type based on cmd string
    // Wheel commands: F, B, L, R, S
    // Arm commands have parsing logic on server, but here we just send to /move for simplicity 
    // IF the server handles all via one queue.
    // However, our plan said /api/move for wheels and /api/arm for arms.
    // Let's check the button attributes.

    // Actually, let's keep it simple: the UI buttons have data-type.
}

// --- CONTROLS HANDLER ---
// --- CONTROLS HANDLER ---
function setupControls() {
    // MOVEMENT (Hold to move, Release to stop)
    const moveButtons = document.querySelectorAll('.btn-control');

    moveButtons.forEach(btn => {
        const cmd = btn.dataset.cmd;

        const startAction = (e) => {
            e.preventDefault();
            btn.classList.add('active');
            callApi('/move', 'POST', { cmd: cmd, duration: 0 });
        };

        const endAction = (e) => {
            e.preventDefault();
            btn.classList.remove('active');
            if (cmd !== 'S') {
                callApi('/move', 'POST', { cmd: 'S', duration: 0 });
            }
        };

        btn.addEventListener('mousedown', startAction);
        btn.addEventListener('touchstart', startAction);

        btn.addEventListener('mouseup', endAction);
        btn.addEventListener('touchend', endAction);
        btn.addEventListener('mouseleave', endAction);
    });

    // ACTION BUTTONS (Click only)
    const actionButtons = document.querySelectorAll('.btn-action');
    actionButtons.forEach(btn => {
        btn.addEventListener('click', async () => {
            const type = btn.dataset.type;
            const cmd = btn.dataset.cmd;

            // Visual feedback
            btn.style.transform = "scale(0.95)";
            setTimeout(() => btn.style.transform = "scale(1)", 100);

            if (type === 'arm') {
                await callApi('/arm', 'POST', { action: cmd });
            } else if (type === 'move') {
                await callApi('/move', 'POST', { cmd: cmd, duration: 0 });
            }
        });
    });

    // ARM SLIDERS (Debounced)
    const sliders = document.querySelectorAll('.arm-slider');
    let debounceTimer = null;

    sliders.forEach(slider => {
        // Init Display
        const joint = slider.dataset.joint;
        const display = document.getElementById(`val-${joint}`);
        if (display) display.textContent = slider.value + "°";

        slider.addEventListener('input', (e) => {
            const angle = slider.value;
            // Update Text Immediately
            if (display) display.textContent = angle + "°";

            // Simple debounce to avoid flooding network
            if (debounceTimer) clearTimeout(debounceTimer);
            debounceTimer = setTimeout(() => {
                const actionCmd = `${joint}:${angle}`;
                callApi('/arm', 'POST', { action: actionCmd });
            }, 100);
        });
    });

    // KEYBOARD CONTROLS (Arrows)
    let currentKey = null;
    document.addEventListener('keydown', (e) => {
        if (currentKey) return; // Ignore repeats

        // Ignore if typing in chat
        if (document.activeElement.tagName === 'TEXTAREA' || document.activeElement.tagName === 'INPUT') return;

        let cmd = null;
        if (e.key === 'ArrowUp') cmd = 'F';
        else if (e.key === 'ArrowDown') cmd = 'B';
        else if (e.key === 'ArrowLeft') cmd = 'L';
        else if (e.key === 'ArrowRight') cmd = 'R';

        if (cmd) {
            e.preventDefault();
            currentKey = e.key;
            callApi('/move', 'POST', { cmd: cmd, duration: 0 });

            // Highlight Button
            const btn = document.querySelector(`.btn-control[data-cmd="${cmd}"]`);
            if (btn) btn.classList.add('active');
        }
    });

    document.addEventListener('keyup', (e) => {
        if (e.key === currentKey) {
            e.preventDefault();

            // Unhighlight Button
            let cmd = null;
            if (e.key === 'ArrowUp') cmd = 'F';
            else if (e.key === 'ArrowDown') cmd = 'B';
            else if (e.key === 'ArrowLeft') cmd = 'L';
            else if (e.key === 'ArrowRight') cmd = 'R';

            const btn = document.querySelector(`.btn-control[data-cmd="${cmd}"]`);
            if (btn) btn.classList.remove('active');

            currentKey = null;
            callApi('/move', 'POST', { cmd: 'S', duration: 0 });
        }
    });
}

// --- POLLING STATUS ---
async function updateStatus() {
    try {
        const response = await fetch(API_BASE + '/status');
        if (response.ok) {
            const data = await response.json();

            // Update Connection UI
            if (data.esp32_connected) {
                statusDot.className = 'status-dot connected'; // Green
                statusDot.style.backgroundColor = ""; // Clear inline override
                statusDot.style.boxShadow = "";       // Clear inline override
                statusText.textContent = "SYSTEM ONLINE";
                statusText.style.color = "#00ff66";
            } else {
                statusDot.className = 'status-dot'; // Default (Red/Orange) or add a warning class
                statusDot.style.backgroundColor = "#ff9900"; // Orange for warning
                statusDot.style.boxShadow = "0 0 8px #ff9900";
                statusText.textContent = "ROBOT DISCONNECTED";
                statusText.style.color = "#ff9900";
            }
            isConnected = true;

            // Update Telemetry
            distVal.textContent = (data.obstacle_dist || '--') + ' cm';
            tempLegsVal.textContent = (data.temp_legs || '--') + ' °C';
            tempArmsVal.textContent = (data.temp_arms || '--') + ' °C';

            // Check Arm Connection
            if (data.arm_connected) {
                tempArmsVal.style.color = "#00ff66";
            } else {
                tempArmsVal.style.color = "#888";
            }

            // Debug Info
            document.getElementById('debug-status').textContent = `Server: OK | ESP32: ${data.esp32_connected}`;

        } else {
            throw new Error("Status API failed");
        }
    } catch (e) {
        if (isConnected) {
            isConnected = false;
            statusDot.classList.remove('connected');
            statusText.textContent = "OFFLINE";
            statusText.style.color = "#8b949e";
        }
    }
}

// --- REMINDER LOGIC REMOVED ---

// --- INIT ---
document.addEventListener('DOMContentLoaded', () => {
    setupControls();
    setupChat();
    setupTabs();

    // Start Pollers
    setInterval(updateStatus, 2000);
    // setInterval(updateReminders, 1000); // Check reminders removed
});

// --- TABS ---
function setupTabs() {
    const navBtns = document.querySelectorAll('.nav-btn');
    const tabContents = document.querySelectorAll('.tab-content');

    navBtns.forEach(btn => {
        btn.addEventListener('click', () => {
            const targetId = btn.dataset.tab;

            // Update Buttons
            navBtns.forEach(b => b.classList.remove('active'));
            btn.classList.add('active');

            // Update Tabs
            tabContents.forEach(content => {
                if (content.id === targetId) {
                    content.classList.add('active');
                    content.style.display = 'flex'; // Ensure flex
                } else {
                    content.classList.remove('active');
                    content.style.display = 'none';
                }
            });
        });
    });
}

// --- CHAT ---
function setupChat() {
    const input = document.getElementById('chat-input');
    const sendBtn = document.getElementById('btn-send');
    const history = document.getElementById('chat-history');
    const micBtn = document.getElementById('btn-mic');
    const stopBtn = document.getElementById('btn-stop');

    // --- STOP LOGIC ---
    stopBtn.addEventListener('click', async () => {
        console.log("🛑 Sending Stop Command...");
        stopBtn.style.transform = "scale(0.9)";
        setTimeout(() => stopBtn.style.transform = "scale(1)", 100);

        // Hide button immediately
        stopBtn.style.display = 'none';

        // Call API
        await callApi('/stop', 'POST', {});

        // Visual feedback in chat
        appendMessage('system', '🚫 Audio Stopped');
    });

    // --- CUSTOM AUDIO STREAMING (OFFLINE VOICE) ---
    let audioContext = null;
    let microphone = null;
    let processor = null;
    let ws = null;
    let isListening = false; // MOVED HERE for scope access

    // Check support
    if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
        micBtn.style.display = 'none';
        console.warn("Media Devices API not supported.");
    }

    micBtn.addEventListener('click', async () => {
        if (isListening) {
            stopRecording();
        } else {
            startRecording();
        }
    });

    async function startRecording() {
        try {
            micBtn.classList.add('listening');
            isListening = true;
            input.placeholder = "Listening...";

            // 1. Setup Audio Context (16kHz preferred if possible, but we resample)
            audioContext = new (window.AudioContext || window.webkitAudioContext)({ sampleRate: 16000 });

            const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
            microphone = audioContext.createMediaStreamSource(stream);

            // 2. Setup WebSocket
            const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
            ws = new WebSocket(`${protocol}//${window.location.host}/api/audio_stream`);
            ws.binaryType = 'arraybuffer';

            ws.onopen = () => {
                console.log("🎙️ WS Connected");
                // 3. Start Processor
                processor = audioContext.createScriptProcessor(4096, 1, 1);
                processor.onaudioprocess = (e) => {
                    const inputData = e.inputBuffer.getChannelData(0);
                    // Downsample/Convert to Int16 PCM for server
                    const pcm16 = floatTo16BitPCM(inputData);
                    if (ws.readyState === WebSocket.OPEN) {
                        ws.send(pcm16);
                    }
                };

                microphone.connect(processor);
                processor.connect(audioContext.destination); // Needed for processing to happen
            };

            ws.onmessage = (event) => {
                const data = JSON.parse(event.data);
                if (data.type === 'partial') {
                    input.value = data.text + '...';
                } else if (data.type === 'final') {
                    input.value = data.text;
                    stopRecording(); // Auto-stop on final (triggered by server silence detection? No, server listens. Wait, server logic relied on client sending STOP. )
                    // Actually, my server logic relies on client sending "stop" action OR detecting silence?
                    // The server logic I wrote does partials periodically. It does FINAL only when client sends "stop".
                    // So we need Manual Stop button or VAD?
                    // User asked for "instant". Let's update stopRecording to send "stop" action.
                }

                // Auto-resize
                input.style.height = 'auto';
                input.style.height = (input.scrollHeight) + 'px';
            };

            ws.onerror = (e) => console.error("WS Error:", e);

        } catch (e) {
            console.error("Mic Error:", e);
            stopRecording();
            alert("Microphone Error: " + e.message);
        }
    }

    function stopRecording() {
        isListening = false;
        micBtn.classList.remove('listening');
        input.placeholder = "Type a message...";

        // Stop Audio
        if (microphone) microphone.disconnect();
        if (processor) {
            processor.disconnect();
            processor.onaudioprocess = null;
        }
        if (audioContext) audioContext.close();

        // Tell Server to Finalize
        if (ws && ws.readyState === WebSocket.OPEN) {
            ws.send(JSON.stringify({ action: "stop" }));
            // Don't close WS yet, wait for final result?
            // Actually server sends final then closes? No server keeps open.
            // Client should wait for final msg then close?
            // Let's just close after a short delay or let onmessage handle it?
            // My server logic sends final then clears buffer. It doesn't close.
            // So we can close client side.
            setTimeout(() => ws.close(), 1000);
        }

        audioContext = null;
        microphone = null;
        processor = null;
    }

    function floatTo16BitPCM(output) {
        const buffer = new ArrayBuffer(output.length * 2);
        const view = new DataView(buffer);
        for (let i = 0; i < output.length; i++) {
            const s = Math.max(-1, Math.min(1, output[i]));
            view.setInt16(i * 2, s < 0 ? s * 0x8000 : s * 0x7FFF, true);
        }
        return buffer;
    }

    // REMOVED SpeechRecognition Logic

    async function sendMessage() {
        console.log("Submit clicked");
        try {
            const text = input.value.trim();
            if (!text) {
                console.log("Empty text");
                return;
            }

            // Stop mic if listening
            if (isListening) {
                stopRecording();
            }

            // User Bubble
            appendMessage('user', text);
            input.value = '';
            input.style.height = '45px'; // Reset height

            // Show Stop Button
            if (stopBtn) stopBtn.style.display = 'flex';

            // Call API
            // Create placeholder for AI response
            const aiMsgDiv = document.createElement('div');
            aiMsgDiv.className = 'message ai';
            aiMsgDiv.innerHTML = '<div class="bubble">...</div>';
            history.appendChild(aiMsgDiv);
            history.scrollTop = history.scrollHeight;

            const aiBubble = aiMsgDiv.querySelector('.bubble');
            aiBubble.textContent = ''; // Clear "..."

            console.log("Sending fetch...");
            const response = await fetch(API_BASE + '/chat', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ text: text })
            });

            if (response.ok) {
                const reader = response.body.getReader();
                const decoder = new TextDecoder();

                while (true) {
                    const { done, value } = await reader.read();
                    if (done) break;
                    const chunk = decoder.decode(value, { stream: true });
                    aiBubble.textContent += chunk;
                    history.scrollTop = history.scrollHeight;
                }
            } else {
                console.error("Server error", response.status);
                aiBubble.textContent = 'Error: Server returned ' + response.status;
            }
        } catch (e) {
            console.error("Chat Error:", e);
            alert("Chat Error: " + e.message);
            appendMessage('ai', 'Error: ' + e.message);
        } finally {
            // Hide Stop Button when done (or error)
            if (stopBtn) stopBtn.style.display = 'none';
        }
    }

    function appendMessage(role, text) {
        const msgDiv = document.createElement('div');
        msgDiv.className = `message ${role}`;
        msgDiv.innerHTML = `<div class="bubble">${text}</div>`;
        history.appendChild(msgDiv);
        history.scrollTop = history.scrollHeight;
    }

    sendBtn.addEventListener('click', sendMessage);

    // Handle Enter to send, Shift+Enter to newline
    input.addEventListener('keydown', (e) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            sendMessage();
        }
    });

    // Auto-resize textarea
    input.addEventListener('input', function () {
        this.style.height = 'auto';
        this.style.height = (this.scrollHeight) + 'px';
        if (this.value === '') {
            this.style.height = '45px';
        }
    });
}
