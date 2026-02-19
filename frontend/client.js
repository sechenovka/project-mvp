const socket = io(window.location.origin);

socket.on('connect', () => console.log('✅ Socket connected'));
socket.on('connect_error', (err) => console.error('⚠️ Socket error:', err));

const statusEl = document.getElementById('status');
const messagesEl = document.getElementById('messages');
const emailInput = document.getElementById('email');
const nameInput = document.getElementById('name');
const textInput = document.getElementById('text');
const createUserBtn = document.getElementById('createUser');
const sendBtn = document.getElementById('send');
const reloadBtn = document.getElementById('reload');

let currentUserId = localStorage.getItem('userId') || null;

function setStatus(type, msg) {
    statusEl.className = type;
    statusEl.textContent = msg;
}

function escapeHtml(str) {
    return String(str).replace(/[&<>"]/g, function(match) {
        if (match === '&') return '&amp;';
        if (match === '<') return '&lt;';
        if (match === '>') return '&gt;';
        if (match === '"') return '&quot;';
        return match;
    });
}

function displayMessage(msg) {
    try {
        const msgDiv = document.createElement('div');
        msgDiv.className = 'msg';
        const meta = document.createElement('div');
        meta.className = 'meta';
        const sender = msg.sender?.name || msg.sender?.email || msg.senderId || 'Неизвестно';
        const time = msg.createdAt ? new Date(msg.createdAt).toLocaleString() : '';
        meta.textContent = `${escapeHtml(sender)} • ${time}`;
        const textDiv = document.createElement('div');
        textDiv.textContent = msg.text;
        msgDiv.appendChild(meta);
        msgDiv.appendChild(textDiv);
        messagesEl.appendChild(msgDiv);
    } catch (e) {
        console.error('displayMessage error:', e);
    }
}

async function loadMessages() {
    try {
        const res = await fetch('/messages?take=200');
        if (!res.ok) {
            const errorData = await res.json();
            throw new Error(errorData.error || `HTTP ${res.status}`);
        }
        const data = await res.json();
        if (!Array.isArray(data)) throw new Error('Сервер вернул не массив');
        messagesEl.innerHTML = '';
        data.forEach(displayMessage);
        messagesEl.scrollTop = messagesEl.scrollHeight;
    } catch (e) {
        setStatus('error', 'Ошибка загрузки: ' + e.message);
    }
}

async function createOrGetUser() {
    const email = emailInput.value.trim();
    if (!email) {
        setStatus('error', 'Введите email');
        return;
    }
    try {
        const res = await fetch('/users', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ email, name: nameInput.value.trim() || undefined })
        });
        const user = await res.json();
        if (!res.ok) throw new Error(user.error || 'Ошибка');
        currentUserId = user.id;
        localStorage.setItem('userId', currentUserId);
        setStatus('ok', `Пользователь: ${user.name || user.email}`);
        emailInput.disabled = true;
        nameInput.disabled = true;
        createUserBtn.disabled = true;
    } catch (e) {
        setStatus('error', e.message);
    }
}

async function sendMessage() {
    if (!currentUserId) {
        setStatus('error', 'Сначала войдите');
        return;
    }
    const text = textInput.value.trim();
    if (!text) return;
    try {
        const res = await fetch('/messages', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ text, senderId: currentUserId })
        });
        const data = await res.json();
        if (!res.ok) throw new Error(data.error || 'Ошибка');
        textInput.value = '';
    } catch (e) {
        setStatus('error', e.message);
    }
}

socket.on('new_message', (msg) => {
    displayMessage(msg);
    messagesEl.scrollTop = messagesEl.scrollHeight;
});

if (currentUserId) {
    emailInput.disabled = true;
    nameInput.disabled = true;
    createUserBtn.disabled = true;
    setStatus('ok', 'Добро пожаловать!');
}

createUserBtn.addEventListener('click', createOrGetUser);
sendBtn.addEventListener('click', sendMessage);
reloadBtn.addEventListener('click', loadMessages);
textInput.addEventListener('keydown', (e) => {
    if (e.key === 'Enter') sendMessage();
});

loadMessages();
