# syntax=docker/dockerfile:1

# ---- build stage -------------------------------------------------------------
FROM node:24-alpine AS build

WORKDIR /app

# npm ci, not npm install: it installs exactly what package-lock.json pins and
# fails if the lockfile and package.json disagree, so the image can't quietly
# drift onto a different version of a dependency than the one that was tested.
COPY package.json package-lock.json ./
RUN npm ci

COPY . .

# Vite substitutes import.meta.env.* at BUILD time — the value is baked into the
# bundle as a string literal, so setting this in docker-compose `environment:`
# would do nothing at all. It has to be a build arg.
#
# The relative '/api' is the whole point of putting nginx in front: the browser
# calls the same origin it loaded the page from, so there is no preflight, no
# CORS configuration to keep in sync, and no hostname baked into the JavaScript.
# mediaUrl() in src/api/client.js derives /media/ from this same value, so photos
# stay same-origin too.
ARG VITE_API_BASE_URL=/api
ENV VITE_API_BASE_URL=$VITE_API_BASE_URL

RUN npm run build

# ---- serve stage -------------------------------------------------------------
FROM nginx:1.29-alpine

# Only the built assets cross the stage boundary. node_modules — several hundred
# megabytes of build-time-only dependencies — stays behind, and so does the Vite
# dev server, which has no business being reachable in a deployed container.
COPY --from=build /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 80
