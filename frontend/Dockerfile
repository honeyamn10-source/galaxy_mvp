FROM node:18-alpine AS build
WORKDIR /app

COPY package.json ./
RUN npm install

COPY . .

ARG REACT_APP_API_URL=http://localhost:1317
ARG REACT_APP_WS_URL=ws://localhost:26657/websocket
ARG REACT_APP_PREDICTIVE_URL=http://localhost:8300
ARG REACT_APP_LLM_URL=http://localhost:8600
ARG REACT_APP_AUTH_URL=http://localhost:8700
ENV REACT_APP_API_URL=${REACT_APP_API_URL}
ENV REACT_APP_WS_URL=${REACT_APP_WS_URL}
ENV REACT_APP_PREDICTIVE_URL=${REACT_APP_PREDICTIVE_URL}
ENV REACT_APP_LLM_URL=${REACT_APP_LLM_URL}
ENV REACT_APP_AUTH_URL=${REACT_APP_AUTH_URL}

RUN npm run build

FROM nginx:alpine
COPY --from=build /app/build /usr/share/nginx/html
EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
