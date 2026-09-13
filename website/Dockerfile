# Next.js inlines every NEXT_PUBLIC_* value into the client JS bundle at
# `next build` time -- setting them as container *runtime* env vars (e.g.
# only in docker-compose.yml's `environment:`) has no effect on what the
# browser actually receives. They have to be passed as build ARGs instead,
# which is why docker-compose.yml's website service uses `build.args` for
# these rather than `environment`.
FROM node:20-slim AS builder
WORKDIR /app

ARG NEXT_PUBLIC_API_URL
# WARNING: NEXT_PUBLIC_* is Next.js's contract for "safe to ship to the
# browser" -- but ADMIN_SECRET and every per-agent API key below are
# genuine router credentials, not public config, and this bakes all of
# them into the client JS bundle in plaintext (visible via view-source to
# anyone who loads the site). That's an existing gap, not something this
# Dockerfile introduces -- see the Enterprise Deployment Blueprint's
# "Multi-user identity & RBAC" section. Closing it means routing
# admin/agent-authenticated calls through a server-side Next.js API route
# instead of calling the router directly from client components.
ARG NEXT_PUBLIC_ADMIN_SECRET
ARG NEXT_PUBLIC_MANAGER_API_KEY
ARG NEXT_PUBLIC_CEO_API_KEY
ARG NEXT_PUBLIC_PM_API_KEY
ARG NEXT_PUBLIC_PRODUCT_API_KEY
ARG NEXT_PUBLIC_ENGINEERING_API_KEY
ARG NEXT_PUBLIC_HR_API_KEY
ARG NEXT_PUBLIC_SALES_API_KEY
ARG NEXT_PUBLIC_MARKETING_API_KEY
ARG NEXT_PUBLIC_FINANCE_API_KEY

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
