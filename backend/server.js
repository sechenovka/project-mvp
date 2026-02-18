const express = require("express");
const { prisma } = require("./db");
const path = require("path");

const app = express();
app.use(express.json());
// serve frontend (same origin, no CORS issues)
app.use(express.static(path.join(__dirname, "..", "frontend")));

// health-check
app.get("/health", (req, res) => {
  res.json({ ok: true });
});

// --- DEBUG ROUTES (register BEFORE listen) ---
app.get("/debug/db", (req, res) => {
  res.json({ databaseUrl: process.env.DATABASE_URL || null });
});

app.get("/debug/users", async (req, res) => {
  try {
    const users = await prisma.user.findMany({
      select: { id: true, email: true, name: true, createdAt: true },
      orderBy: { createdAt: "asc" },
    });
    res.json(users);
  } catch (e) {
    console.error(e);
    res
      .status(500)
      .json({ error: "Failed to load users", details: String(e?.message || e) });
  }
});

app.get("/debug/user/:id", async (req, res) => {
  try {
    const user = await prisma.user.findUnique({
      where: { id: req.params.id },
      select: { id: true, email: true, name: true, createdAt: true },
    });

    res.json({ found: !!user, user });
  } catch (e) {
    console.error(e);
    res
      .status(500)
      .json({ error: "Failed to load user", details: String(e?.message || e) });
  }
});

// получить историю сообщений
app.get("/messages", async (req, res) => {
  try {
    const take = Math.min(Number(req.query.take || 50), 200);

    const messages = await prisma.message.findMany({
      orderBy: { createdAt: "asc" },
      take,
      include: {
        sender: { select: { id: true, email: true, name: true } },
      },
    });

    res.json(messages);
  } catch (e) {
    console.error(e);
    res
      .status(500)
      .json({ error: "Failed to load messages", details: String(e?.message || e) });
  }
});

// создать сообщение
app.post("/messages", async (req, res) => {
  try {
    const { text, senderId } = req.body;

    if (!text || !senderId) {
      return res.status(400).json({ error: "text and senderId are required" });
    }

    // Guard: avoid FK error by validating sender exists
    const senderExists = await prisma.user.findUnique({
      where: { id: senderId },
      select: { id: true },
    });

    if (!senderExists) {
      return res.status(400).json({
        error: "Unknown senderId (user not found)",
        senderId,
      });
    }

    const msg = await prisma.message.create({
      data: { text, senderId },
      include: {
        sender: { select: { id: true, email: true, name: true } },
      },
    });

    res.status(201).json(msg);
  } catch (e) {
    console.error(e);
    res
      .status(500)
      .json({ error: "Failed to create message", details: String(e?.message || e) });
  }
});

const PORT = process.env.PORT || 3001;
app.listen(PORT, () => {
  console.log(`API running on http://localhost:${PORT}`);
});