FROM node:22-bookworm-slim AS build
WORKDIR /service
ENV NEXT_TELEMETRY_DISABLED=1
RUN corepack enable && corepack prepare pnpm@11.25.0 --activate
COPY frontend/package.json frontend/pnpm-lock.yaml ./
RUN pnpm install --frozen-lockfile
COPY frontend/ .
RUN pnpm build

FROM node:22-bookworm-slim
WORKDIR /service
ENV NODE_ENV=production NEXT_TELEMETRY_DISABLED=1 HOSTNAME=0.0.0.0 PORT=10000 TZ=America/Vancouver
COPY --from=build --chown=node:node /service/.next/standalone ./
COPY --from=build --chown=node:node /service/.next/static ./.next/static
COPY --from=build --chown=node:node /service/public ./public
USER node
EXPOSE 10000
CMD ["node", "server.js"]
