# Dev-oriented image running the Vite dev server; see ARCHITECTURE.md §5d for
# the production-hardening steps deliberately deferred.
FROM node:22-alpine

WORKDIR /app

COPY package.json package-lock.json ./
RUN npm ci

COPY . .

EXPOSE 5173
CMD ["npm", "run", "dev"]
