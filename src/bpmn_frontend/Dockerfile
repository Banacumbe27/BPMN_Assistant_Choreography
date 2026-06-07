FROM node:20 AS build-stage
WORKDIR /app

COPY src/bpmn_frontend/package*.json ./
RUN npm install
COPY src/bpmn_frontend .

ARG VITE_API_BASE_URL
ARG VITE_LAYOUT_BASE_URL
ENV VITE_API_BASE_URL=${VITE_API_BASE_URL}
ENV VITE_LAYOUT_BASE_URL=${VITE_LAYOUT_BASE_URL}

RUN npm run build

FROM nginx:stable-alpine AS production-stage
COPY --from=build-stage /app/dist /usr/share/nginx/html
EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]