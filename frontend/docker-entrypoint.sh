#!/bin/sh
# Set default PORT if not set
export PORT=${PORT:-80}

# Substitute PORT environment variable in nginx config
envsubst '$PORT' < /etc/nginx/conf.d/default.conf > /etc/nginx/conf.d/default.conf.tmp
mv /etc/nginx/conf.d/default.conf.tmp /etc/nginx/conf.d/default.conf

# Start nginx
exec nginx -g 'daemon off;'
