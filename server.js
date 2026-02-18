const express = require('express');
const http = require('http');
const { Server } = require('socket.io');

const app = express();
const server = http.createServer(app);
const io = new Server(server);

app.use(express.json());
app.use(express.static('public')); // раздаём статические файлы из папки public

// Хранилище сообщений в памяти
let messages = [];

// Получить все сообщения
app.get('/messages', (req, res) => {
  res.json(messages);
});

// Создать новое сообщение
app.post('/messages', (req, res) => {
  const { text } = req.body;
  if (!text) {
    return res.status(400).json({ error: 'text is required' });
  }

  const newMessage = {
    id: Date.now(),
    text,
    timestamp: new Date().toISOString(),
  };

  messages.push(newMessage);

  // Отправляем событие всем подключённым клиентам
  io.emit('new_message', newMessage);

  res.status(201).json(newMessage);
});

// Подключение WebSocket
io.on('connection', (socket) => {
  console.log('a user connected');
});

const PORT = 3001;
server.listen(PORT, () => {
  console.log(`Server running on http://localhost:${PORT}`);
});