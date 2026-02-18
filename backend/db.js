const path = require("path");
// Force-load the backend .env (override any existing env values)
require("dotenv").config({ path: path.join(__dirname, ".env"), override: true });

const { PrismaClient } = require("@prisma/client");

// Reuse PrismaClient in dev to avoid multiple connections on reloads
const globalForPrisma = globalThis;

const prisma = globalForPrisma.prisma || new PrismaClient();

if (process.env.NODE_ENV !== "production") {
  globalForPrisma.prisma = prisma;
}

// Graceful shutdown
process.on("SIGINT", async () => {
  try {
    await prisma.$disconnect();
  } finally {
    process.exit(0);
  }
});

process.on("SIGTERM", async () => {
  try {
    await prisma.$disconnect();
  } finally {
    process.exit(0);
  }
});

module.exports = { prisma };