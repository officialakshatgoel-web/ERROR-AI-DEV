import { initializeApp } from "https://www.gstatic.com/firebasejs/10.7.1/firebase-app.js";
import { getDatabase, ref, onValue } from "https://www.gstatic.com/firebasejs/10.7.1/firebase-database.js";

// Fetch Firebase Config dynamically from the backend API
const configRes = await fetch('/api/v1/firebase/config');
const firebaseConfig = await configRes.json();

const app = initializeApp(firebaseConfig);
const db = getDatabase(app);

// Real-time synchronization
const settingsRef = ref(db, 'settings');
onValue(settingsRef, (snapshot) => {
    const data = snapshot.val();
    if (data) {
        // Update Daily Limit
        const dailyLimitEl = document.getElementById('web-daily-limit');
        if (dailyLimitEl) dailyLimitEl.innerText = `${data.default_daily_limit || 100} req`;
        
        // Update Contact
        const contact = data.contact_username || "@DARKVENDOR07";
        const link = document.getElementById('web-contact-link');
        if (link) {
            link.querySelector('span').innerText = `Contact Admin: ${contact}`;
            link.href = `https://t.me/${contact.replace('@', '')}`;
        }

        // Update Total Requests with animation
        updateCounter(data.total_requests || 0);
    }
});

// Live Health Check
setInterval(async () => {
    try {
        const res = await fetch('/api/v1/config');
        const data = await res.json();
        const statusVal = document.getElementById('model-status-val');
        if (statusVal && data.status) {
            statusVal.innerText = data.status;
            statusVal.style.color = (data.status === 'ACTIVE') ? '#00ff88' : '#ff4d4d';
        }
    } catch(e) {}
}, 30000);

function updateCounter(target) {
    const countEl = document.getElementById('live-requests-count');
    if (!countEl) return;
    const current = parseInt(countEl.innerText.replace(/,/g, '')) || 0;
    if (current === target) return;

    const duration = 1500;
    const start = performance.now();

    function animate(now) {
        const elapsed = now - start;
        const progress = Math.min(elapsed / duration, 1);
        const ease = 1 - Math.pow(1 - progress, 4);
        const val = Math.floor(current + (target - current) * ease);
        countEl.innerText = val.toLocaleString();
        if (progress < 1) requestAnimationFrame(animate);
    }
    requestAnimationFrame(animate);
}

// ═══════════════════════════════════════════════════════════
//  CONFIG MARKED.JS (Latest v12+ support)
// ═══════════════════════════════════════════════════════════
const icons = {
    copy: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="9" y="9" width="13" height="13" rx="2"/><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/></svg>`,
    check: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><polyline points="20 6 9 17 4 12"/></svg>`,
    regen: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="23 4 23 10 17 10"/><path d="M20.49 15a9 9 0 1 1-2.12-9.36L23 10"/></svg>`,
};

const customRenderer = {
    code(token) {
        const code = token.text || token.code || '';
        const language = token.lang || 'plaintext';
        
        let highlighted;
        try {
            highlighted = hljs.getLanguage(language)
                ? hljs.highlight(code, { language }).value
                : hljs.highlightAuto(code).value;
        } catch (e) {
            highlighted = code;
        }
        
        const id = 'code-' + Math.random().toString(36).slice(2);
        return `<pre><div class="code-header"><span class="code-lang">${language}</span><button class="code-copy" data-target="${id}" onclick="copyCode(this,'${id}')">
        ${icons.copy} Copy</button></div><code id="${id}" class="hljs language-${language}">${highlighted}</code></pre>`;
    }
};

marked.use({ 
    renderer: customRenderer,
    breaks: true,
    gfm: true 
});

// ═══════════════════════════════════════════════════════════
//  STATE
// ═══════════════════════════════════════════════════════════
let conversationHistory = [];
let isGenerating = false;
let abortController = null;
let lastUserMessage = null;
let currentAiWrapper = null;

// ═══════════════════════════════════════════════════════════
//  DOM REFS
// ═══════════════════════════════════════════════════════════
const msgContainer = document.getElementById('chat-messages');
const userInput = document.getElementById('user-input');
const sendBtn = document.getElementById('send-btn');
const stopBtn = document.getElementById('stop-btn');
const styleSelect = document.getElementById('chat-style');
const clearBtn = document.getElementById('clear-btn');
const chatContainer = document.getElementById('chat-container');
const fsBtn = document.getElementById('fullscreen-btn');
const fsExpand = document.getElementById('fs-icon-expand');
const fsCollapse = document.getElementById('fs-icon-collapse');

// ═══════════════════════════════════════════════════════════
//  AUTO-RESIZE TEXTAREA
// ═══════════════════════════════════════════════════════════
function autoResize() {
    if (!userInput) return;
    userInput.style.height = 'auto';
    userInput.style.height = Math.min(userInput.scrollHeight, 180) + 'px';
}
if (userInput) userInput.addEventListener('input', autoResize);

function renderMarkdown(el, rawText) {
    const text = String(rawText || '');
    el.innerHTML = marked.parse(text);
}

window.copyCode = function (btn, id) {
    const code = document.getElementById(id);
    if (!code) return;
    navigator.clipboard.writeText(code.innerText).then(() => {
        btn.classList.add('copied');
        btn.innerHTML = icons.check + ' Copied';
        setTimeout(() => {
            btn.classList.remove('copied');
            btn.innerHTML = icons.copy + ' Copy';
        }, 2000);
    });
};

// ═══════════════════════════════════════════════════════════
//  APPEND MESSAGE
// ═══════════════════════════════════════════════════════════
function appendMessage(role, htmlOrText, isRaw = true) {
    const wrapper = document.createElement('div');
    wrapper.className = `msg-wrapper ${role}`;

    const bubble = document.createElement('div');
    bubble.className = `message ${role}`;

    if (role === 'ai' && isRaw) {
        renderMarkdown(bubble, htmlOrText);
    } else if (role === 'ai' && !isRaw) {
        bubble.innerHTML = htmlOrText;
    } else {
        bubble.textContent = htmlOrText;
    }

    wrapper.appendChild(bubble);

    const actions = document.createElement('div');
    actions.className = 'msg-actions';

    if (role === 'ai') {
        const copyBtn = document.createElement('button');
        copyBtn.className = 'action-btn';
        copyBtn.innerHTML = `${icons.copy} Copy`;
        copyBtn.onclick = () => {
            navigator.clipboard.writeText(bubble.innerText).then(() => {
                copyBtn.classList.add('copied');
                copyBtn.innerHTML = `${icons.check} Copied`;
                setTimeout(() => {
                    copyBtn.classList.remove('copied');
                    copyBtn.innerHTML = `${icons.copy} Copy`;
                }, 2000);
            });
        };
        actions.appendChild(copyBtn);
    }

    if (role === 'user') {
        const copyBtn = document.createElement('button');
        copyBtn.className = 'action-btn';
        copyBtn.innerHTML = `${icons.copy} Copy`;
        copyBtn.onclick = () => {
            navigator.clipboard.writeText(bubble.textContent).then(() => {
                copyBtn.classList.add('copied');
                copyBtn.innerHTML = `${icons.check} Copied`;
                setTimeout(() => {
                    copyBtn.classList.remove('copied');
                    copyBtn.innerHTML = `${icons.copy} Copy`;
                }, 2000);
            });
        };
        actions.appendChild(copyBtn);
    }

    wrapper.appendChild(actions);
    if (msgContainer) msgContainer.appendChild(wrapper);
    scrollToBottom();
    return { wrapper, bubble };
}

function scrollToBottom() {
    if (msgContainer) msgContainer.scrollTop = msgContainer.scrollHeight;
}

// ═══════════════════════════════════════════════════════════
//  THINKING INDICATOR
// ═══════════════════════════════════════════════════════════
function showThinking() {
    const wrapper = document.createElement('div');
    wrapper.className = 'msg-wrapper ai';
    wrapper.id = 'thinking-indicator';
    wrapper.innerHTML = `<div class="message ai thinking">
    <span class="thinking-dot"></span>
    <span class="thinking-dot"></span>
    <span class="thinking-dot"></span>
</div>`;
    if (msgContainer) msgContainer.appendChild(wrapper);
    scrollToBottom();
}
function hideThinking() {
    const el = document.getElementById('thinking-indicator');
    if (el) el.remove();
}

function setGenerating(state) {
    isGenerating = state;
    if (sendBtn) sendBtn.disabled = state;
    if (stopBtn) stopBtn.classList.toggle('visible', state);
}

// ═══════════════════════════════════════════════════════════
//  SEND MESSAGE + STREAM
// ═══════════════════════════════════════════════════════════
async function sendMessage(userText) {
    if (isGenerating) return;

    const text = (userText || (userInput ? userInput.value : "")).trim();
    if (!text) return;

    if (userInput) {
        userInput.value = '';
        userInput.style.height = 'auto';
    }
    lastUserMessage = text;

    const historySnapshot = conversationHistory.map(h => ({ role: h.role, content: h.content }));
    appendMessage('user', text, false);
    conversationHistory.push({ role: 'user', content: text });

    showThinking();
    setGenerating(true);

    let fullText = '';
    let aiBubble = null;
    let aiWrapper = null;

    abortController = new AbortController();

    try {
        const response = await fetch('/api/v1/chat', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                message: text,
                style: styleSelect ? styleSelect.value : "Default",
                history: historySnapshot
            }),
            signal: abortController.signal
        });

        if (!response.ok) {
            const err = await response.json().catch(() => ({ detail: 'Server error' }));
            hideThinking();
            appendMessage('ai', `**Error:** ${err.detail || 'Unknown server error'}`, true);
            setGenerating(false);
            return;
        }

        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        let buffer = '';
        let firstToken = true;

        while (true) {
            let done, value;
            try {
                ({ done, value} = await reader.read());
            } catch (e) {
                break;
            }
            if (done) break;

            buffer += decoder.decode(value, { stream: true });
            const lines = buffer.split('\n');
            buffer = lines.pop();

            for (const line of lines) {
                if (!line.startsWith('data: ')) continue;
                const payload = line.slice(6).trim();
                if (payload === '[DONE]') break;

                try {
                    const parsed = JSON.parse(payload);
                    if (parsed.error) {
                        hideThinking();
                        appendMessage('ai', `**Error:** ${parsed.error}`, true);
                        setGenerating(false);
                        return;
                    }
                    if (parsed.token) {
                        if (firstToken) {
                            hideThinking();
                            const result = createStreamBubble();
                            aiBubble = result.bubble;
                            aiWrapper = result.wrapper;
                            currentAiWrapper = aiWrapper;
                            firstToken = false;
                        }
                        fullText += parsed.token;
                        updateStreamBubble(aiBubble, fullText);
                    }
                } catch (e) {}
            }
        }

    } catch (e) {
        if (e.name !== 'AbortError') {
            hideThinking();
            appendMessage('ai', '**Connection lost.** The AI is offline or request failed.', true);
        }
    }

    hideThinking();
    setGenerating(false);
    abortController = null;

    if (aiBubble && fullText) {
        renderMarkdown(aiBubble, fullText);
        addRegenerateBtn(aiWrapper, fullText);
        conversationHistory.push({ role: 'assistant', content: fullText });
    } else if (!fullText) {
        appendMessage('ai', '*(No response received. The model may be loading.)*', true);
    }

    scrollToBottom();
}

function createStreamBubble() {
    const wrapper = document.createElement('div');
    wrapper.className = 'msg-wrapper ai';
    const bubble = document.createElement('div');
    bubble.className = 'message ai';
    wrapper.appendChild(bubble);
    if (msgContainer) msgContainer.appendChild(wrapper);
    return { wrapper, bubble };
}

function updateStreamBubble(bubble, text) {
    bubble.innerHTML = marked.parse(String(text)) + '<span class="streaming-cursor"></span>';
    scrollToBottom();
}

function addRegenerateBtn(wrapper, fullText) {
    let actions = wrapper.querySelector('.msg-actions');
    if (!actions) {
        actions = document.createElement('div');
        actions.className = 'msg-actions';
        wrapper.appendChild(actions);
    }

    const bubble = wrapper.querySelector('.message.ai');
    const copyBtn = document.createElement('button');
    copyBtn.className = 'action-btn';
    copyBtn.innerHTML = `${icons.copy} Copy`;
    copyBtn.onclick = () => {
        navigator.clipboard.writeText(bubble.innerText).then(() => {
            copyBtn.classList.add('copied');
            copyBtn.innerHTML = `${icons.check} Copied`;
            setTimeout(() => { copyBtn.classList.remove('copied'); copyBtn.innerHTML = `${icons.copy} Copy`; }, 2000);
        });
    };
    actions.appendChild(copyBtn);

    const regenBtn = document.createElement('button');
    regenBtn.className = 'action-btn';
    regenBtn.innerHTML = `${icons.regen} Regenerate`;
    regenBtn.onclick = () => {
        if (isGenerating) return;
        wrapper.remove();
        const lastHistIdx = conversationHistory.findLastIndex(h => h.role === 'assistant');
        if (lastHistIdx !== -1) conversationHistory.splice(lastHistIdx, 1);
        if (lastUserMessage) {
            const lastUserIdx = conversationHistory.findLastIndex(h => h.role === 'user');
            const msgToRegen = lastUserMessage;
            if (lastUserIdx !== -1) conversationHistory.splice(lastUserIdx, 1);
            sendMessage(msgToRegen);
        }
    };
    actions.appendChild(regenBtn);

    actions.style.opacity = '1';
    setTimeout(() => actions.style.opacity = '', 1500);
}

if (stopBtn) stopBtn.onclick = () => {
    if (abortController) {
        abortController.abort();
        abortController = null;
    }
    setGenerating(false);
    hideThinking();
};

if (sendBtn) sendBtn.onclick = () => sendMessage();

if (userInput) userInput.addEventListener('keydown', (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        sendMessage();
    }
});

if (clearBtn) clearBtn.onclick = () => {
    if (isGenerating) return;
    conversationHistory = [];
    lastUserMessage = null;
    if (msgContainer) {
        msgContainer.innerHTML = '';
        appendMessage('ai', 'Conversation cleared. Start fresh — ask me anything.', true);
    }
};

if (fsBtn) fsBtn.onclick = () => {
    if (chatContainer) {
        chatContainer.classList.toggle('fullscreen');
        const isFS = chatContainer.classList.contains('fullscreen');
        if (fsExpand) fsExpand.style.display = isFS ? 'none' : '';
        if (fsCollapse) fsCollapse.style.display = isFS ? '' : 'none';
        scrollToBottom();
    }
};

const menuToggle = document.getElementById('menu-toggle');
const navLinks = document.getElementById('nav-links');

if (menuToggle && navLinks) {
    menuToggle.addEventListener('click', () => {
        navLinks.classList.toggle('active');
        const icon = menuToggle.querySelector('svg');
        if (navLinks.classList.contains('active')) {
            icon.innerHTML = '<line x1="18" y1="6" x2="6" y2="18"></line><line x1="6" y1="6" x2="18" y2="18"></line>';
        } else {
            icon.innerHTML = '<line x1="3" y1="12" x2="21" y2="12"></line><line x1="3" y1="6" x2="21" y2="6"></line><line x1="3" y1="18" x2="21" y2="18"></line>';
        }
    });

    navLinks.querySelectorAll('a').forEach(link => {
        link.addEventListener('click', () => navLinks.classList.remove('active'));
    });
}
