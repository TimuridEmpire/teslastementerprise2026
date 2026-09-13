# No credential build ARGs here. They used to be required (Next.js inlines
# NEXT_PUBLIC_* into the client JS bundle at `next build` time, which is
# how the admin secret and every agent's API key ended up shipping to the
# browser in plaintext) -- fixed by moving router-authenticated calls
# through a server-side proxy (app/api/router/[...path]/route.ts) that
# reads real credentials from its own runtime env vars instead. See
# docker-compose.yml's website service for those (`environment:`, not
# `build.args`) and the Enterprise Deployment Blueprint for the finding.
FROM node:20-slim AS builder
WORKDIR /app

COPY package.json package-lock.json* ./
RUN npm ci

COPY . .
RUN npm run build

FROM node:20-slim
WORKDIR /app
ENV NODE_ENV=production

COPY --from=builder /app/public ./public
COPY --from=builder /app/.next ./.next
COPY --from=builder /app/node_modules ./node_modules
COPY --from=builder /app/package.json ./package.json

EXPOSE 3000
CMD ["npm", "run", "start"]
