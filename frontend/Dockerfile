FROM node:20-slim AS builder

WORKDIR /app

COPY package*.json ./
RUN npm ci

COPY . .

# BACKEND_API_URL must be provided at build time so next.config.ts can bake
# the correct rewrite destination into routes-manifest.json.
# On Railway: set this as a build variable on the frontend service, e.g.:
#   BACKEND_API_URL=https://your-backend.up.railway.app/api
ARG BACKEND_API_URL
ENV BACKEND_API_URL=${BACKEND_API_URL}

RUN npm run build

# --- Runtime stage ---
FROM node:20-slim AS runner

WORKDIR /app

ENV NODE_ENV=production

COPY --from=builder /app/public ./public
COPY --from=builder /app/.next/standalone ./
COPY --from=builder /app/.next/static ./.next/static

EXPOSE 3000

CMD ["node", "server.js"]
