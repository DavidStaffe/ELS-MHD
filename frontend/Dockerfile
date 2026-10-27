FROM node:22-bookworm-slim AS build
WORKDIR /app
COPY package.json package-lock.json ./
# Temporary compatibility setting for the repository's existing CRA/ESLint
# and react-day-picker/date-fns peer dependency conflicts.
# TODO: Align dependencies and regenerate lockfile; remove this flag.
RUN npm install --legacy-peer-deps --no-audit --no-fund
COPY . .
ENV REACT_APP_BACKEND_URL=""
ENV CI=false
RUN npm run build

FROM nginx:1.27-alpine
COPY --from=build /app/build /usr/share/nginx/html
COPY deploy/nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
