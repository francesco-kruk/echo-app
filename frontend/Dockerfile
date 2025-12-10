# Build stage
FROM node:20-alpine AS builder

WORKDIR /app

# Copy package files
COPY package*.json ./

# Install dependencies
RUN npm ci

# Copy source code
COPY . .

# Build arguments for auth configuration (passed via azd)
# Note: VITE_API_URL is no longer needed - we use /api proxy in production
ARG VITE_AZURE_CLIENT_ID
ARG VITE_TENANT_ID
ARG VITE_API_SCOPE
ARG VITE_AUTH_ENABLED=true

ENV VITE_AZURE_CLIENT_ID=$VITE_AZURE_CLIENT_ID
ENV VITE_TENANT_ID=$VITE_TENANT_ID
ENV VITE_API_SCOPE=$VITE_API_SCOPE
ENV VITE_AUTH_ENABLED=$VITE_AUTH_ENABLED

# Build the application
RUN npm run build

# Production stage with Nginx
FROM nginx:alpine

# Copy built assets from builder
COPY --from=builder /app/dist /usr/share/nginx/html

# Copy nginx configuration template (uses envsubst for runtime config)
COPY nginx.conf.template /etc/nginx/templates/default.conf.template

# Also copy static nginx.conf for local development (no proxy)
COPY nginx.conf /etc/nginx/nginx.conf.static

# Expose port 80
EXPOSE 80

# Default backend URL (will be overridden by Container Apps env var)
ENV BACKEND_URL=http://backend

# Health check
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
    CMD wget --no-verbose --tries=1 --spider http://localhost/health || exit 1

# Use envsubst to process the template and start nginx
# The nginx:alpine image automatically processes templates in /etc/nginx/templates/
CMD ["nginx", "-g", "daemon off;"]
