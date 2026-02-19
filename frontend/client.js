const socket = io(); // подключение к WebSocket

const messagesDiv = document.getElementById('messages');
const form = document.getElementById('messageForm');
const input = document.getElementById('messageInput');

// Загружаем историю сообщений при загрузке страницы
async function loadMessages() {
    const response = await fetch('/messages');
    const messages = await response.json();
    messages.forEach(addMessageToList);
}

// Добавляет одно сообщение в DOM
function addMessageToList(message) {
    const messageEl = document.createElement('div');
    const time = new Date(message.timestamp).toLocaleTimeString();
    messageEl.textContent = `[${time}] ${message.text}`;
    messagesDiv.appendChild(messageEl);
}

// Отправка формы
form.addEventListener('submit', async (e) => {
    e.preventDefault();
    const text = input.value.trim();
    if (!text) return;

    const response = await fetch('/messages', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ text }),
    });

    if (response.ok) {
        input.value = ''; // очищаем поле
        // Само сообщение добавится через сокет
    } else {
        console.error('Ошибка при отправке');
    }
});

// Слушаем новые сообщения через сокет
socket.on('new_message', (message) => {
    addMessageToList(message);
});

// Стартовая загрузка истории
loadMessages();