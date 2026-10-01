# Frontend image — M0 skeleton.
# M1+ will add a production-stage Nginx / static-file server.

FROM node:20-alpine AS build
WORKDIR /app

COPY package.json ./
RUN npm install

COPY tsconfig.json vite.config.ts tailwind.config.js postcss.config.js ./
COPY index.html ./
COPY src ./src

RUN npm run build

# --- runtime stage ---
FROM nginx:alpine
COPY --from=build /app/dist /usr/share/nginx/html
EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]