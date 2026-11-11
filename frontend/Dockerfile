# --- Desarrollo (compose.yaml): target "dev" ---
FROM node:22-alpine AS dev

WORKDIR /app

COPY package*.json ./

RUN npm ci

COPY . .

EXPOSE 5173

CMD ["npm", "run", "dev", "--", "--host", "0.0.0.0"]


# --- Compilacion de produccion ---
FROM dev AS build

# Vite incrusta esta variable al compilar: debe ser la URL publica de la API.
ARG VITE_API_BASE_URL
ENV VITE_API_BASE_URL=$VITE_API_BASE_URL

RUN npm run build


# --- Produccion (por defecto): nginx sirve dist/ ---
FROM nginx:1.27-alpine AS prod

# La imagen oficial aplica envsubst a /etc/nginx/templates/*.template
# al arrancar, asi que ${PORT} se resuelve en tiempo de ejecucion.
ENV PORT=8080
COPY nginx.conf.template /etc/nginx/templates/default.conf.template
COPY --from=build /app/dist /usr/share/nginx/html

EXPOSE 8080
