FROM nginx:1.27-alpine

COPY web/krizovka.html /usr/share/nginx/html/index.html

EXPOSE 80
