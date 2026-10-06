FROM node:22-alpine AS build
WORKDIR /workspace
COPY package.json ./
COPY apps/web/package.json ./apps/web/package.json
RUN npm install
COPY apps/web ./apps/web
RUN npm run build:web

FROM node:22-alpine
WORKDIR /workspace
COPY --from=build /workspace/package.json ./
COPY --from=build /workspace/node_modules ./node_modules
COPY --from=build /workspace/apps/web ./apps/web
EXPOSE 3000
# Compose publishes the container port only on host loopback.
CMD ["npm", "--workspace", "apps/web", "run", "start"]
