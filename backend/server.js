const express = require("express");
const http = require("http");
const { Server } = require("socket.io");
const path = require("path");
const { body, validationResult } = require("express-validator");
const { prisma } = require("./db");

const app = express();
const server = http.createServer(app);
const io = new Server(server);

const PORT = process.env.PORT || 3001;

// Мидлвары
app.use(express.json());

// Статика из папки frontend (без public)
const frontendPath = path.join(__dirname, "../frontend");
app.use(express.static(frontendPath));

// Валидация
const validate = (req, res, next) => {
  const errors = validationResult(req);
  if (!errors.isEmpty()) {
    return res.status(400).json({ errors: errors.array() });
  }
  next();
};

// === API Роуты ===

// Создание/получение пользователя (нужен для senderId)
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
      let user = await prisma.user.findUnique({ where: { email } });
      if (!user) {
        user = await prisma.user.create({
          data: { email, name: name || email.split("@")[0] },
        });
      }
      res.json({ id: user.id, email: user.email, name: user.name });
    } catch (e) {
      console.error(e);
      res.status(500).json({ error: "Failed to create/find user" });
    }
  }
);

// Получить историю сообщений
app.get("/messages", async (req, res) => {
  try {
    const take = Math.min(Number(req.query.take || 50), 200);
    const messages = await prisma.message.findMany({
      take,
      orderBy: { createdAt: "desc" },
      include: { sender: { select: { id: true, email: true, name: true } } },
    });
    res.json(messages.reverse());
  } catch (e) {
    console.error(e);
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

      const sender = await prisma.user.findUnique({ where: { id: senderId } });
      if (!sender) {
        return res.status(400).json({ error: "Sender not found" });
      }

      const msg = await prisma.message.create({
        data: { text, senderId },
        include: { sender: { select: { id: true, email: true, name: true } } },
      });

      // Отправляем событие всем клиентам
      io.emit("new_message", msg);

      res.status(201).json(msg);
    } catch (e) {
      console.error(e);
      res.status(500).json({ error: "Failed to create message" });
    }
  }
);

// Health check
app.get("/health", (req, res) => {
  res.json({ ok: true });
});

// Корневой маршрут — отдаём index.html (если запрос не обработан статикой)
app.get("/", (req, res) => {
  res.sendFile(path.join(frontendPath, "index.html"));
});

// === WebSocket ===
io.on("connection", (socket) => {
  console.log("a user connected");
  socket.on("disconnect", () => {
    console.log("user disconnected");
  });
});

// Запуск сервера
server.listen(PORT, () => {
  console.log(`Server running on http://localhost:${PORT}`);
});