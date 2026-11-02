FROM node:26-alpine AS deps
RUN mkdir /app && chown node:node /app
WORKDIR /app
USER node
COPY --chown=node:node package.json package-lock.json ./
RUN npm ci

# Local development with hot reload.
FROM deps AS dev
COPY --chown=node:node . .
EXPOSE 5173
CMD ["npm", "run", "dev", "--", "--host", "0.0.0.0"]

# Static production bundle in /app/dist.
FROM deps AS build
COPY --chown=node:node . .
RUN npm run build
