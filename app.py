from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import sqlite3
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
import asyncio
import interactions
from aiohttp import ClientSession

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class NameChangeRequest(BaseModel):
    id: int
    username: str

def init_db():
    conn = sqlite3.connect("players.db")
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS players (
            id INTEGER PRIMARY KEY,
            username TEXT NOT NULL
        )
    ''')
    conn.commit()
    conn.close()

init_db()

@app.post("/name")
async def change_name(request: NameChangeRequest):
    if not (4 <= len(request.username) <= 12):
        raise HTTPException(status_code=400, detail="O nome deve ter entre 4 e 12 caracteres")
    if not (1 <= request.id <= 1999):
        raise HTTPException(status_code=400, detail="ID inválido")

    conn = sqlite3.connect("players.db")
    c = conn.cursor()
    c.execute("UPDATE players SET username = ? WHERE id = ?", (request.username, request.id))
    if c.rowcount == 0:
        c.execute("INSERT INTO players (id, username) VALUES (?, ?)", (request.id, request.username))
    conn.commit()
    conn.close()
    return {"status": "success", "new_username": request.username}

@app.get("/username-config")
async def get_username(id: int):
    conn = sqlite3.connect("players.db")
    c = conn.cursor()
    c.execute("SELECT username FROM players WHERE id = ?", (id,))
    result = c.fetchone()
    conn.close()
    if result:
        return {"new_username": result[0]}
    raise HTTPException(status_code=404, detail="Jogador não encontrado")

bot = interactions.Client(token="MTI0MjEzNDkxNjc3MDEwMzM0Ng.G9hjYv.gEENkejnMg2-_-ypQynlQMitMK2Ky-eHRZJGSs")

@interactions.slash_command(
    name="nick",
    description="Muda o nome do usuário no jogo",
    options=[
        interactions.SlashCommandOption(
            name="userid",
            description="ID do usuário (1-1999)",
            type=interactions.OptionType.INTEGER,
            required=True,
        ),
        interactions.SlashCommandOption(
            name="novonick",
            description="Novo nome (4-12 caracteres)",
            type=interactions.OptionType.STRING,
            required=True,
        ),
    ]
)
async def nick(ctx: interactions.SlashContext, userid: int, novonick: str):
    if not (1 <= userid <= 1999):
        await ctx.send("ID inválido. Deve estar entre 1 e 1999.", ephemeral=True)
        return
    if not (4 <= len(novonick) <= 12):
        await ctx.send("O nome deve ter entre 4 e 12 caracteres.", ephemeral=True)
        return

    async with ClientSession() as session:
        async with session.post(
            "https://teste052.onrender.com/name",
            json={"id": userid, "username": novonick}
        ) as response:
            if response.status == 200:
                await ctx.send(f"Nome alterado para '{novonick}' para o ID {userid}.", ephemeral=True)
            else:
                await ctx.send("Erro ao atualizar o nome no servidor.", ephemeral=True)

async def main():
    try:
        bot_task = asyncio.create_task(bot.start())
        await uvicorn.run(app, host="0.0.0.0", port=8000)
    except Exception as e:
        print(f"Erro: {e}")

if __name__ == "__main__":
    asyncio.run(main())
