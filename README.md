# URLFairyBot

URLFairyBot is a whimsical Telegram bot that sprinkles its magic on messy URLs, transforming them into organized and enchanting links. Let the bot be your URL-cleaning companion, waving its digital wand to reveal the hidden wonders behind every web address.

## Features

- Casts a spell on URLs, turning them from chaos to clarity.
- Conjures up valuable data from URLs, like a true magical oracle.
- Your trusty URL fairy with a touch of whimsy and humor.

## Getting Started

Prepare for a magical journey as you set up and deploy the URLFairyBot.

### Prerequisites

- Docker and Docker Compose installed on your system (or your own fairy dust, whichever is handier).

### Installation

1. Begin your adventure by cloning this repository:

   ```bash
   git clone https://github.com/5mdt/urlfairy-bot.git
   cd urlfairy-bot
   ```

2. Craft a `.env` file in the root directory and set the necessary enchantments:

   ```dotenv
   BOT_TOKEN=your_bot_token
   BASE_URL=your_base_url
   ```

3. Do not forget to create a traefik reverse proxy `docker-compose.yml` file:

   ```yaml
   ---
   version: "3"
   services:
   app:
      command:
         - --api.insecure=true
         - --providers.docker=true
         - --providers.docker.exposedbydefault=false
         - --entrypoints.web.address=:80
         - --entrypoints.websecure.address=:443
         - --certificatesResolvers.le.acme.email=user@example.com # CHANGE THIS
         - --certificatesResolvers.le.acme.storage=acme.json
         - --certificatesResolvers.le.acme.tlsChallenge=true
         - --certificatesResolvers.le.acme.httpChallenge=true
         - --certificatesResolvers.le.acme.httpChallenge.entryPoint=web
         - --entrypoints.web.http.redirections.entrypoint.to=websecure
         - --entrypoints.web.http.redirections.entrypoint.scheme=https
         - --providers.docker.network=traefik_default1
      image: "traefik:latest"
      labels:
         com.centurylinklabs.watchtower.enable: "true"
      logging:
         driver: "json-file"
         options:
         max-file: "3"
         max-size: "1m"
      ports:
         - "80:80"
         - "443:443"
      restart: always
      volumes:
         - "/var/run/docker.sock:/var/run/docker.sock:ro"
         - "/opt/traefik/acme.json:/acme.json"
   ```

4. Brew your concoction of Docker spells to awaken the bot:

   ```shell
   docker-compose up -d
   ```

## Configuration

- `server/default.conf`: The magical scroll containing Nginx's secrets for serving the bot's magic.
- `cron/Dockerfile`: The recipe for the bot's trusty cron service that maintains its enchanted data.
- `bot/requirements.txt`: Ingredients list for the bot's Python potion.
- `bot/Dockerfile`: The cauldron where the bot's essence is distilled.
- `bot/main.py`: The spellbook containing Python incantations for the bot's functions.

## Usage

1. Initiate a conversation with the bot on Telegram.
2. Bestow upon it a twisted and tangled URL.
3. Witness the bot's incantations as it transforms the URL into an elegant masterpiece of clarity.
4. Share the now-gleaming link with fellow travelers to spread the charm of URLFairyBot.

## Contributing

Join the enchanting circle! If you stumble upon a bug or have an idea for a new spell, conjure an issue or send a magical pull request.

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for spellbinding details.

## Authors

- Vladimir Budylnikov aka [@nett00n](https://github.com/nett00n)

---

2023, Tbilisi, Sakartvelo
