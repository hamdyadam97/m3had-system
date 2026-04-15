#!/bin/bash

# ============================================
# Init Let's Encrypt SSL for Dockerized Django
# ============================================

if ! [ -x "$(command -v docker-compose)" ] && ! [ -x "$(command -v docker)" ]; then
  echo 'Error: docker or docker-compose is not installed.' >&2
  exit 1
fi

# تعيين النطاقات والبريد
# عدل هنا:
DOMAINS=("yourdomain.com" "www.yourdomain.com")
EMAIL="admin@yourdomain.com"
NGINX_CONTAINER_NAME="institute_nginx"

# لا تعدل تحت هذا السطر إلا لو تعرف إنت بتعمل إيه
RSA_KEY_SIZE=4096
DATA_PATH="./certbot"

if [ -d "$DATA_PATH/conf/live/${DOMAINS[0]}" ]; then
  echo "Existing certificate found for ${DOMAINS[0]}. Skipping..."
  exit 0
fi

if [ ! -e "$DATA_PATH/conf/options-ssl-nginx.conf" ] || [ ! -e "$DATA_PATH/conf/ssl-dhparams.pem" ]; then
  echo "### Downloading recommended TLS parameters ..."
  mkdir -p "$DATA_PATH/conf"
  curl -s https://raw.githubusercontent.com/certbot/certbot/master/certbot-nginx/certbot_nginx/_internal/tls_configs/options-ssl-nginx.conf > "$DATA_PATH/conf/options-ssl-nginx.conf"
  curl -s https://raw.githubusercontent.com/certbot/certbot/master/certbot/certbot/ssl-dhparams.pem > "$DATA_PATH/conf/ssl-dhparams.pem"
fi

echo "### Creating dummy certificate for ${DOMAINS[0]} ..."
mkdir -p "$DATA_PATH/conf/live/${DOMAINS[0]}"
docker-compose -f docker-compose.prod.yml run --rm --entrypoint " \
  openssl req -x509 -nodes -newkey rsa:$RSA_KEY_SIZE -days 1 \
    -keyout '/etc/letsencrypt/live/${DOMAINS[0]}/privkey.pem' \
    -out '/etc/letsencrypt/live/${DOMAINS[0]}/fullchain.pem' \
    -subj '/CN=localhost' \
" certbot

echo "### Starting nginx ..."
docker-compose -f docker-compose.prod.yml up --force-recreate -d nginx

echo "### Deleting dummy certificate for ${DOMAINS[0]} ..."
docker-compose -f docker-compose.prod.yml run --rm --entrypoint " \
  rm -Rf /etc/letsencrypt/live/${DOMAINS[0]} && \
  rm -Rf /etc/letsencrypt/archive/${DOMAINS[0]} && \
  rm -Rf /etc/letsencrypt/renewal/${DOMAINS[0]}.conf \
" certbot

echo "### Requesting Let's Encrypt certificate for ${DOMAINS[*]} ..."
# Join $DOMAINS to -d args
domain_args=""
for domain in "${DOMAINS[@]}"; do
  domain_args="$domain_args -d $domain"
done

# Select appropriate email arg
if [ -n "$EMAIL" ]; then
  email_arg="--email $EMAIL"
else
  email_arg="--register-unsafely-without-email"
fi

docker-compose -f docker-compose.prod.yml run --rm --entrypoint " \
  certbot certonly --webroot -w /var/www/certbot \
    $email_arg \
    $domain_args \
    --rsa-key-size $RSA_KEY_SIZE \
    --agree-tos \
    --force-renewal \
    --non-interactive \
" certbot

echo "### Updating nginx config with domain name ..."
sed -i "s/DOMAIN_PLACEHOLDER/${DOMAINS[0]}/g" nginx/nginx.conf
sed -i "s/server_name _;/server_name ${DOMAINS[0]} www.${DOMAINS[0]};/g" nginx/nginx.conf

echo "### Reloading nginx ..."
docker-compose -f docker-compose.prod.yml exec nginx nginx -s reload

echo "### SSL Setup complete!"
