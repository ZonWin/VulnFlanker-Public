FROM node:22-alpine AS build

WORKDIR /app

COPY frontend/package*.json ./
RUN --mount=type=cache,target=/root/.npm \
    npm ci

COPY frontend/ ./

ARG VITE_API_BASE_URL=
ARG VITE_AGENT_INGRESS_BASE_URL=
ENV VITE_API_BASE_URL=$VITE_API_BASE_URL
ENV VITE_AGENT_INGRESS_BASE_URL=$VITE_AGENT_INGRESS_BASE_URL

RUN npm run build

FROM nginx:1.27-alpine

COPY deploy/frontend.nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist /usr/share/nginx/html

EXPOSE 80
