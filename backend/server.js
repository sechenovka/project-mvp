const express = require("express");
const http = require("http");
const { Server } = require("socket.io");
const path = require("path");
const fs = require("fs");
const { body, validationResult } = require("express-validator");
const { prisma, testConnection, initDatabase } = require("./db");
const { exec } = require("child_process");

// Загружаем переменные окружения из .env (если есть)
require("dotenv").config({ path: path.join(__dirname, ".env"), override: true });

// Встроенные значения по умолчанию
process.env.DATABASE_URL = process.env.DATABASE_URL || "file:./dev.db";
process.env.PORT = process.env.PORT || 3001;

const app = express();
const server = http.createServer(app);
const io = new Server(server, {
  cors: {
    origin: "*", // для отладки; в продакшене можно ограничить
    methods: ["GET", "POST"]
  }
});

const PORT = process.env.PORT;

// Определяем путь к папке frontend
let frontendPath = path.join(__dirname, "frontend"); // для скомпилированного exe (exe в корне, frontend рядом)
if (!fs.existsSync(frontendPath)) {
  // Если не нашли, пробуем ../frontend (для разработки: запуск из папки backend)
  frontendPath = path.join(__dirname, "../frontend");
}
console.log(`📁 Serving frontend from: ${frontendPath}`);
app.use(express.static(frontendPath));

app.use(express.json());
 
// Валидация
const validate = (req, res, next) => {
  const errors = validationResult(req);
  if (!errors.isEmpty()) {
    return res.status(400).json({ errors: errors.array() });
  }
  next();
};

// ========== API ==========

// Создание/получение пользователя
app.post(
  "/users",
  [
    body("email").isEmail().normalizeEmail(),
    body("name").optional().trim().isLength({ min: 1, max: 50 }),
  ],
  validate,
  async (req, res) => {
    try {
      const { email, name } = req.body;
      console.log(`📨 POST /users: ${email}`);
      let user = await prisma.user.findUnique({ where: { email } });
      if (!user) {
        user = await prisma.user.create({
          data: { email, name: name || email.split("@")[0] },
        });
        console.log(`✅ User created: ${user.id}`);
      } else {
        console.log(`✅ User found: ${user.id}`);
      }
      res.json({ id: user.id, email: user.email, name: user.name });
    } catch (e) {
      console.error("❌ Error in /users:", e);
      res.status(500).json({ error: "Failed to create/find user" });
    }
  }
);

// Получить историю сообщений
app.get("/messages", async (req, res) => {
  try {
    const take = Math.min(Number(req.query.take || 50), 200);
    console.log(`📨 GET /messages?take=${take}`);
    const messages = await prisma.message.findMany({
      take,
      orderBy: { createdAt: "desc" },
      include: { sender: { select: { id: true, email: true, name: true } } },
    });
    console.log(`✅ Loaded ${messages.length} messages`);
    res.json(messages.reverse());
  } catch (e) {
    console.error("❌ Error in GET /messages:", e);
    res.status(500).json({ error: "Failed to load messages" });
  }
});

// Создать сообщение + рассылка через WebSocket
app.post(
  "/messages",
  [
    body("text").trim().isLength({ min: 1, max: 1000 }),
    body("senderId").isUUID(),
  ],
  validate,
  async (req, res) => {
    try {
      const { text, senderId } = req.body;
      console.log(`📨 POST /messages: text="${text}", senderId=${senderId}`);
 
      const sender = await prisma.user.findUnique({ where: { id: senderId } });
      if (!sender) {
        console.log(`❌ Sender not found: ${senderId}`);
        return res.status(400).json({ error: "Sender not found" });
      }
 
      const msg = await prisma.message.create({
        data: { text, senderId },
        include: { sender: { select: { id: true, email: true, name: true } } },
      });
      console.log(`✅ Message created: id=${msg.id}`);
  
      const clientsCount = io.engine.clientsCount;
      console.log(`📤 Emitting 'new_message' to ${clientsCount} clients`);
      io.emit("new_message", msg);

      res.status(201).json(msg);
    } catch (e) {
      console.error("❌ Error in POST /messages:", e);
      res.status(500).json({ error: "Failed to create message" });
    }
  }
);

// Health check
app.get("/health", (req, res) => {
  res.json({ ok: true });
});

// Корневой маршрут — отдаём index.html
app.get("/", (req, res) => {
  res.sendFile(path.join(frontendPath, "index.html"));
});

// ========== WebSocket ==========
io.on("connection", (socket) => {
  console.log(`🔌 User connected (socket id: ${socket.id}). Total clients: ${io.engine.clientsCount}`);
  
  socket.on("disconnect", () => {
    console.log(`🔌 User disconnected (socket id: ${socket.id}). Remaining clients: ${io.engine.clientsCount}`);
  });
});

// ========== Запуск сервера ==========
async function startServer() {
  // Проверяем подключение к БД и инициализируем таблицы при необходимости
  const connected = await testConnection();
  if (!connected) {
    console.log("⚠️ База данных не найдена, создаём таблицы...");
    await initDatabase();
  }

  server.listen(PORT, () => {
    console.log(`🚀 Server running on http://localhost:${PORT}`);
    // Открываем браузер автоматически
    const url = `http://localhost:${PORT}`;
    if (process.platform === 'win32') {
      exec(`start ${url}`);
    } else if (process.platform === 'darwin') {
      exec(`open ${url}`);
    } else {
      exec(`xdg-open ${url}`);
    }
  });
}

startServer();