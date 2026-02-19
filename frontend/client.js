const socket = io();

const messagesDiv = document.getElementById('messages');
const form = document.getElementById('messageForm');
const input = document.getElementById('messageInput');
const statusEl = document.getElementById('status'); // нужен в HTML

function setStatus(type, msg) {
  if (statusEl) {
    statusEl.className = type;
    statusEl.textContent = msg;
  } else {
    console.log(`[${type}] ${msg}`);
  }
}

// Загрузка истории сообщений
async function loadMessages() {
  try {
    const response = await fetch('/messages?take=200');
    console.log('Response status:', response.status); // отладка
    const data = await response.json();
    console.log('Response data:', data); // отладка

    if (!response.ok) {
      throw new Error(data.error || `HTTP error ${response.status}`);
    }
    if (!Array.isArray(data)) {
      throw new Error('Сервер вернул не массив: ' + JSON.stringify(data));
    }

    messagesDiv.innerHTML = '';
    data.forEach(addMessageToList);
    messagesDiv.scrollTop = messagesDiv.scrollHeight;
    setStatus('ok', 'Сообщения загружены');
  } catch (e) {
    setStatus('error', 'Ошибка загрузки: ' + e.message);
  }
}

// Добавление одного сообщения
function addMessageToList(message) {
  const messageEl = document.createElement('div');
  messageEl.className = 'msg';

  const meta = document.createElement('div');
  meta.className = 'meta';
  const senderName = message.sender?.name || message.sender?.email || message.senderId || 'Неизвестно';
  const time = message.createdAt ? new Date(message.createdAt).toLocaleString() : '';
  meta.textContent = `${senderName} • ${time}`;

  const textDiv = document.createElement('div');
  textDiv.className = 'text';
  textDiv.textContent = message.text;

  messageEl.appendChild(meta);
  messageEl.appendChild(textDiv);
  messagesDiv.appendChild(messageEl);
}

// Создание/получение пользователя
async function ensureUser() {
  let userId = localStorage.getItem('userId');
  if (userId) return userId;

  const email = prompt('Введите ваш email для входа:');
  if (!email) {
    alert('Email обязателен');
    return null;
  }

  try {
    const response = await fetch('/users', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email, name: email.split('@')[0] })
    });
    const data = await response.json();
    if (!response.ok) {
      throw new Error(data.error || 'Ошибка создания пользователя');
    }
    localStorage.setItem('userId', data.id);
    setStatus('ok', `Добро пожаловать, ${data.name || data.email}`);
    return data.id;
  } catch (e) {
    setStatus('error', e.message);
    return null;
  }
}

// Отправка сообщения
form.addEventListener('submit', async (e) => {
  e.preventDefault();
  const text = input.value.trim();
  if (!text) return;

  const senderId = await ensureUser();
  if (!senderId) return;

  try {
    const response = await fetch('/messages', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ text, senderId }),
    });
    const data = await response.json();
    if (!response.ok) {
      throw new Error(data.error || 'Ошибка отправки');
    }
    input.value = '';
  } catch (e) {
    setStatus('error', e.message);
  }
});

// Слушаем новые сообщения
socket.on('new_message', (message) => {
  addMessageToList(message);
  messagesDiv.scrollTop = messagesDiv.scrollHeight;
});

// Инициализация
(async () => {
  const userId = await ensureUser();
  if (userId) {
    loadMessages();
  } else {
    setStatus('error', 'Не удалось инициализировать пользователя');
  }
})();