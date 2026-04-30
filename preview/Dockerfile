# syntax=docker/dockerfile:1

# Microsoft's official Playwright image already has Chromium and all the
# Linux libs it needs (libnss3, libxkbcommon, etc.) baked in — saves us a
# long apt-get incantation and several hundred MB of trial-and-error.
FROM mcr.microsoft.com/playwright:v1.50.0-jammy

ENV NODE_ENV=production

WORKDIR /app

COPY package.json ./
# No lockfile yet — npm install (not ci) will resolve from the manifest.
# When this stabilizes, generate package-lock.json and switch to `npm ci`
# for reproducible builds.
RUN npm install --omit=dev

COPY server.cjs ./

EXPOSE 3000

# Playwright's image runs as root by default; the `pwuser` user is set up
# for unprivileged Chromium runs.
USER pwuser

CMD ["node", "server.cjs"]
