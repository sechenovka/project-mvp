const path = require("path");
const { PrismaClient } = require("@prisma/client");

// Загрузка переменных окружения из .env (переопределяет существующие)
require("dotenv").config({ path: path.join(__dirname, ".env"), override: true });

// Глобальный синглтон для PrismaClient (предотвращает множественные подключения при hot-reload в dev)
const globalForPrisma = globalThis;

const prisma = globalForPrisma.prisma || new PrismaClient();

if (process.env.NODE_ENV !== "production") {
  globalForPrisma.prisma = prisma;
}

/**
 * Проверка подключения к базе данных
 * @returns {Promise<boolean>} true если подключение успешно
 */
async function testConnection() {
  try {
    await prisma.$queryRaw`SELECT 1`;
    console.log("✅ База данных подключена");
    return true;
  } catch (error) {
    console.error("❌ Ошибка подключения к БД:", error.message);
    return false;
  }
}

// Graceful shutdown
async function shutdown() {
  try {
    await prisma.$disconnect();
    console.log("🔌 Отключение от базы данных");
  } finally {
    process.exit(0);
  }
}

process.on("SIGINT", shutdown);
process.on("SIGTERM", shutdown);

module.exports = { prisma, testConnection };