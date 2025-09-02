import asyncio
import discord
from discord.ext import commands
from fastapi import FastAPI, Form
from fastapi.responses import HTMLResponse
import uvicorn

app = FastAPI()
bot = commands.Bot(command_prefix='!', intents=discord.Intents.default())

DISCORD_TOKEN = "MTI0MjEzNDkxNjc3MDEwMzM0Ng.G9hjYv.gEENkejnMg2-_-ypQynlQMitMK2Ky-eHRZJGSs"  # Coloque o token do bot aqui

@app.get("/", response_class=HTMLResponse)
async def root():
    html_content = """
    <!doctype html>
    <html>
        <head>
            <title>Enviar Mensagem para Discord</title>
        </head>
        <body>
            <h1>Enviar Mensagem para Canal do Discord</h1>
            <form action="/send" method="post">
                <label for="channel_id">ID do Canal:</label>
                <input type="text" id="channel_id" name="channel_id" required><br><br>
                <label for="message">Mensagem:</label>
                <textarea id="message" name="message" required></textarea><br><br>
                <input type="submit" value="Enviar">
            </form>
        </body>
    </html>
    """
    return html_content

@app.post("/send")
async def send_message(channel_id: str = Form(...), message: str = Form(...)):
    try:
        channel = bot.get_channel(int(channel_id))
        if channel:
            await channel.send(message)
            return {"status": "success", "detail": "Mensagem enviada!"}
        else:
            return {"status": "error", "detail": "Canal não encontrado."}
    except ValueError:
        return {"status": "error", "detail": "ID do canal inválido."}
    except Exception as e:
        return {"status": "error", "detail": str(e)}

@bot.event
async def on_ready():
    print(f'Bot conectado como {bot.user}')

async def main():
    try:
        bot_task = asyncio.create_task(bot.start(DISCORD_TOKEN))
        await uvicorn.run(app, host="0.0.0.0", port=8000)
    except Exception as e:
        print(f"Erro: {e}")

if __name__ == "__main__":
    asyncio.run(main())
