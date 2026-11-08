import hashlib
import hmac
import json
import time
from urllib.parse import parse_qsl

from aiohttp import web


PAGES_ORIGIN = "https://bishnoitarachand007-commits.github.io"


def verify_init_data(init_data, bot_token):
    if not init_data or len(init_data) > 8192:
        return None

    try:
        fields = dict(parse_qsl(init_data, keep_blank_values=True))
        received_hash = fields.pop("hash")
        auth_date = int(fields["auth_date"])
        user = json.loads(fields["user"])

        if time.time() - auth_date > 86400 or auth_date > time.time() + 60:
            return None

        data_check = "\n".join(
            f"{key}={value}" for key, value in sorted(fields.items())
        )

        secret = hmac.new(
            b"WebAppData", bot_token.encode(), hashlib.sha256
        ).digest()

        calculated = hmac.new(
            secret, data_check.encode(), hashlib.sha256
        ).hexdigest()

        if not hmac.compare_digest(calculated, received_hash):
            return None

        return user
    except (ValueError, KeyError, TypeError, json.JSONDecodeError):
        return None


def build_web_app(bot_client, active_games, process_card_pass, bot_token):
    locks = {}

    @web.middleware
    async def cors(request, handler):
        if request.method == "OPTIONS":
            response = web.Response(status=204)
        else:
            response = await handler(request)

        origin = request.headers.get("Origin")
        if origin == PAGES_ORIGIN:
            response.headers["Access-Control-Allow-Origin"] = PAGES_ORIGIN
            response.headers["Access-Control-Allow-Headers"] = (
                "Content-Type, X-Telegram-Init-Data"
            )
            response.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
            response.headers["Vary"] = "Origin"
        return response

    def get_user(request):
        init_data = request.headers.get("X-Telegram-Init-Data", "")
        return verify_init_data(init_data, bot_token)

    def get_player(game_id, user_id):
        game = active_games.get(game_id)
        if not game or not game.get("turn_active"):
            return None, None

        index = game["current"]
        if not 0 <= index < len(game["names"]):
            return None, None

        if game["user_ids"][index] != user_id:
            return None, None

        player = {
            "hand": game["hands"][index],
            "name": game["names"][index],
            "is_bot": game["user_ids"][index] == 0,
        }
        if player["is_bot"]:
            return None, None

        return game, (index, player)

    async def health(request):
        return web.json_response({"status": "ready"})

    async def cards(request):
        user = get_user(request)
        if not user:
            return web.json_response({"error": "Telegram verification failed"}, status=401)

        try:
            game_id = int(request.query["game_id"])
        except (KeyError, ValueError):
            return web.json_response({"error": "Invalid game"}, status=400)

        game, result = get_player(game_id, int(user["id"]))
        if not result:
            return web.json_response({"error": "Not your active turn"}, status=403)

        index, player = result
        return web.json_response({
            "cards": player["hand"],
            "turn_id": game["turn_id"],
            "player": player["name"]
        })

    async def select_card(request):
        user = get_user(request)
        if not user:
            return web.json_response({"error": "Telegram verification failed"}, status=401)

        try:
            data = await request.json()
            game_id = int(data["game_id"])
            turn_id = int(data["turn_id"])
            card_index = int(data["card_index"])
        except (ValueError, KeyError, TypeError):
            return web.json_response({"error": "Invalid selection"}, status=400)

        lock = locks.setdefault(game_id, __import__("asyncio").Lock())

        async with lock:
            game, result = get_player(game_id, int(user["id"]))

            if not result or game["turn_id"] != turn_id:
                return web.json_response({"error": "Turn expired"}, status=409)

            index, player = result
            if not 0 <= card_index < len(player["hand"]):
                return web.json_response({"error": "Invalid card"}, status=400)

            task = game.get("turn_task")
            if task and not task.done():
                task.cancel()
                try:
                    await task
                except Exception:
                    pass

            game["turn_active"] = False
            game["turn_task"] = None
            await process_card_pass(bot_client, game_id, index, card_index)

        return web.json_response({"status": "card passed"})

    application = web.Application(
        middlewares=[cors],
        client_max_size=4096
    )
    application.router.add_get("/health", health)
    application.router.add_get("/api/cards", cards)
    application.router.add_post("/api/select", select_card)
    application.router.add_route("OPTIONS", "/{tail:.*}", health)

    return application
