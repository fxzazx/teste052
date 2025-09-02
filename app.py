# api.py
import json
import discord
from discord.ext import commands
from discord import app_commands, ButtonStyle
from discord.ui import Button, View
from flask import Flask, request, jsonify, redirect, session
from threading import Thread
import asyncio
import requests
import os
from dotenv import load_dotenv
import time

load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "15150306")

ARQUIVO_DADOS = "game_data.json"
CANAL_RANKING_ID = 1412135078687146008
CANAL_LOG_ID = 1412135078687146008
CARGOS_ADMIN = [1389319267991814255]  # Cargo para boost [WB]

def carregar_db():
    try:
        if os.path.exists(ARQUIVO_DADOS):
            with open(ARQUIVO_DADOS, 'r') as f:
                dados = json.load(f)
                chaves_necessarias = ["jogadores", "ids_banidos", "proximo_id", "vitorias", "discords", "jogadores_online", "fila_ranking", "jogo_para_discord_id", "autenticacoes_pendentes", "usuarios_permitidos"]
                for chave in chaves_necessarias:
                    if chave not in dados:
                        dados[chave] = {} if chave in ["jogadores", "vitorias", "discords", "jogadores_online", "jogo_para_discord_id", "autenticacoes_pendentes", "usuarios_permitidos"] else [] if chave in ["ids_banidos", "fila_ranking"] else 1
                return dados
        else:
            dados = {
                "jogadores": {},
                "ids_banidos": [],
                "proximo_id": 1,
                "vitorias": {},
                "discords": {},
                "jogadores_online": {},
                "fila_ranking": [],
                "jogo_para_discord_id": {},
                "autenticacoes_pendentes": {},
                "usuarios_permitidos": {}
            }
            salvar_db(dados)
            return dados
    except Exception as e:
        print(f"Erro ao carregar dados JSON: {e}")
        dados = {
            "jogadores": {},
            "ids_banidos": [],
            "proximo_id": 1,
            "vitorias": {},
            "discords": {},
            "jogadores_online": {},
            "fila_ranking": [],
            "jogo_para_discord_id": {},
            "autenticacoes_pendentes": {},
            "usuarios_permitidos": {}
        }
        salvar_db(dados)
        return dados

def salvar_db(db):
    try:
        with open(ARQUIVO_DADOS, 'w') as f:
            json.dump(db, f, indent=4)
    except Exception as e:
        print(f"Erro ao salvar dados JSON: {e}")

def resetar_db():
    dados = {
        "jogadores": {},
        "ids_banidos": [],
        "proximo_id": 1,
        "vitorias": {},
        "discords": {},
        "jogadores_online": {},
        "fila_ranking": [],
        "jogo_para_discord_id": {},
        "autenticacoes_pendentes": {},
        "usuarios_permitidos": {}
    }
    if os.path.exists(ARQUIVO_DADOS):
        os.remove(ARQUIVO_DADOS)
    salvar_db(dados)
    return dados

db = carregar_db()
usuarios_verificados = {}

CLIENT_ID = os.getenv("CLIENT_ID", "1412134916770103346")
CLIENT_SECRET = os.getenv("CLIENT_SECRET", "AOkqiLik9q3FdFZJJNqW4olsOCkNrhzK")
REDIRECT_URI = os.getenv("REDIRECT_URI", "https://teste052.onrender.com/callback")
BOT_TOKEN = os.getenv("BOT_TOKEN", "MTI0MjEzNDkxNjc3MDEwMzM0Ng.G9hjYv.gEENkejnMg2-_-ypQynlQMitMK2Ky-eHRZJGSs")

def obter_tag_boost(discord_id, membro):
    if any(role.id == CARGOS_ADMIN[0] for role in membro.roles):
        return "<color=pink><sup>[WB]"
    return ""

@app.route("/auth")
def autenticar():
    id_jogo = request.args.get("id")
    if not id_jogo:
        return jsonify({"erro": "ID inválido"}), 400

    id_discord = db["jogo_para_discord_id"].get(id_jogo)
    if id_discord and id_discord in db["discords"]:
        return jsonify({"mensagem": f"Já autenticado como {db['discords'][id_discord]}", "autenticado": True}), 200

    session["id_jogo"] = id_jogo
    url_oauth_discord = (
        f"https://discord.com/api/oauth2/authorize"
        f"?client_id={CLIENT_ID}"
        f"&redirect_uri={REDIRECT_URI}"
        f"&response_type=code"
        f"&scope=identify"
        f"&state={id_jogo}"
    )
    db["autenticacoes_pendentes"][id_jogo] = True
    salvar_db(db)
    return redirect(url_oauth_discord)

@app.route("/callback")
def callback():
    codigo = request.args.get("code")
    id_jogo = request.args.get("state")

    if not codigo or not id_jogo:
        return jsonify({"erro": "Código ou estado ausente"}), 400

    dados = {
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "grant_type": "authorization_code",
        "code": codigo,
        "redirect_uri": REDIRECT_URI,
        "scope": "identify"
    }
    headers = {"Content-Type": "application/x-www-form-urlencoded"}

    try:
        resposta_token = requests.post("https://discord.com/api/oauth2/token", data=dados, headers=headers)
        resposta_token.raise_for_status()
        json_token = resposta_token.json()
        token_acesso = json_token.get("access_token")
        if not token_acesso:
            return jsonify({"erro": "Erro ao obter token"}), 400

        resposta_usuario = requests.get(
            "https://discord.com/api/users/@me",
            headers={"Authorization": f"Bearer {token_acesso}"}
        )
        resposta_usuario.raise_for_status()
        usuario = resposta_usuario.json()
        id_discord = str(usuario["id"])
        tag_discord = f'{usuario["username"]}#{usuario["discriminator"]}'

        if id_jogo in db["jogo_para_discord_id"]:
            if db["jogo_para_discord_id"][id_jogo] == id_discord:
                return jsonify({"mensagem": f"Já autenticado como {tag_discord}", "autenticado": True}), 200
            else:
                return jsonify({"erro": "ID do jogo já associado a outro Discord"}), 400

        usuarios_verificados[id_jogo] = tag_discord
        db["discords"][id_discord] = tag_discord
        db["jogo_para_discord_id"][id_jogo] = id_discord
        if id_discord not in db["jogadores"]:
            db["jogadores"][id_discord] = f"StumbleB[{id_jogo}]"
            db["jogadores_online"][id_discord] = True
        if id_jogo in db["autenticacoes_pendentes"]:
            del db["autenticacoes_pendentes"][id_jogo]
        salvar_db(db)

        nome_usuario = db["jogadores"].get(id_discord, "Desconhecido")
        asyncio.run_coroutine_threadsafe(
            enviar_log(f"Jogador autenticado: ID do jogo {id_jogo} ID Discord {id_discord} Nome {nome_usuario} Discord {tag_discord}"),
            bot.loop
        )
        
        conteudo_html = f"""
        <!DOCTYPE html>
        <html lang="pt-BR">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>Autenticação Concluída</title>
            <style>
                body {{
                    background-color: #D6EAF8;
                    display: flex;
                    justify-content: center;
                    align-items: center;
                    height: 100vh;
                    margin: 0;
                    font-family: Arial, sans-serif;
                }}
                .container {{
                    background-color: #FFFFFF;
                    padding: 20px;
                    border-radius: 15px;
                    box-shadow: 0 4px 8px rgba(0, 0, 0, 0.2);
                    text-align: center;
                    max-width: 400px;
                }}
                h2 {{
                    color: #333;
                    font-size: 24px;
                    margin-bottom: 10px;
                }}
                p {{
                    color: #555;
                    font-size: 16px;
                    margin-top: 10px;
                }}
            </style>
        </head>
        <body>
            <div class="container">
                <h2>Autenticado com sucesso como {tag_discord}</h2>
                <p>Você pode fechar esta aba agora</p>
            </div>
        </body>
        </html>
        """
        return conteudo_html, 200
    except requests.RequestException as e:
        asyncio.run_coroutine_threadsafe(
            enviar_log(f"Erro de autenticação para ID do jogo {id_jogo}: {str(e)}"),
            bot.loop
        )
        return jsonify({"erro": f"Falha na autenticação: {str(e)}"}), 400

@app.route("/check-auth")
def verificar_autenticacao():
    id_jogo = request.args.get("id")
    if not id_jogo:
        return jsonify({"erro": "ID não fornecido"}), 400
    id_discord = db["jogo_para_discord_id"].get(id_jogo)
    if id_discord and id_discord in db["discords"]:
        return jsonify({"autenticado": True, "discord": db["discords"][id_discord]})
    return jsonify({"autenticado": False, "discord": "Desconectado"})

@app.route("/check-discord")
def verificar_discord():
    id_jogo = request.args.get("id")
    if not id_jogo:
        return jsonify({"erro": "ID não fornecido"}), 400
    id_discord = db["jogo_para_discord_id"].get(id_jogo)
    if id_discord and id_discord in db["discords"]:
        return jsonify({"discord": db["discords"][id_discord]})
    return jsonify({"discord": "Desconhecido"})

@app.route("/player-join", methods=["POST"])
def jogador_entrar():
    nome_usuario = request.form.get("username")
    id_jogo = request.form.get("id")
    if not nome_usuario or not id_jogo:
        return jsonify({"erro": "Dados ausentes"}), 400

    id_discord = db["jogo_para_discord_id"].get(id_jogo)
    if not id_discord:
        if id_jogo not in db["autenticacoes_pendentes"]:
            db["autenticacoes_pendentes"][id_jogo] = True
            salvar_db(db)
        return jsonify({"erro": "ID do jogo não associado a um Discord. Autentique primeiro"}), 400

    # Verifica se o usuário tem o cargo de boost
    try:
        membro = bot.get_guild(CANAL_RANKING_ID).get_member(int(id_discord))
        tag_boost = obter_tag_boost(id_discord, membro) if membro else ""
    except:
        tag_boost = ""

    is_novo = id_discord not in db["jogadores"]
    nome_usuario = nome_usuario[:200]  # Limita a 200 caracteres
    if len(nome_usuario) < 4:
        nome_usuario = f"StumbleB[{id_jogo}]"
    db["jogadores"][id_discord] = nome_usuario + tag_boost
    db["jogadores_online"][id_discord] = True
    if int(id_jogo) >= db["proximo_id"]:
        db["proximo_id"] = int(id_jogo) + 1
    salvar_db(db)

    nome_atual = db["jogadores"][id_discord]
    if is_novo:
        asyncio.run_coroutine_threadsafe(
            enviar_log(f"Novo jogador: ID do jogo {id_jogo} ID Discord {id_discord} Nome {nome_atual}"),
            bot.loop
        )
    else:
        asyncio.run_coroutine_threadsafe(
            enviar_log(f"Jogador reconectado: ID do jogo {id_jogo} ID Discord {id_discord} Nome {nome_atual}"),
            bot.loop
        )
    return jsonify({"id": id_jogo, "novo": is_novo, "username": nome_atual})

@app.route("/player-leave", methods=["POST"])
def jogador_sair():
    id_jogo = request.form.get("id")
    if not id_jogo:
        return jsonify({"erro": "ID não fornecido"}), 400
    id_discord = db["jogo_para_discord_id"].get(id_jogo)
    if id_discord and id_discord in db["jogadores_online"]:
        db["jogadores_online"][id_discord] = False
        if id_discord in db["fila_ranking"]:
            db["fila_ranking"].remove(id_discord)
            salvar_db(db)
            asyncio.run_coroutine_threadsafe(
                enviar_log(f"Jogador saiu: ID do jogo {id_jogo} ID Discord {id_discord}"),
                bot.loop
            )
            asyncio.run_coroutine_threadsafe(
                atualizar_embed_ranking(),
                bot.loop
            )
        salvar_db(db)
    return jsonify({"id": id_jogo, "status": "offline"})

@app.route("/username-config", methods=["GET"])
def configurar_nome_usuario():
    id_jogo = request.args.get("id")
    if not id_jogo:
        return jsonify({"erro": "ID não fornecido"}), 400
    id_discord = db["jogo_para_discord_id"].get(id_jogo)
    if not id_discord or id_discord not in db["jogadores"]:
        return jsonify({"erro": "ID não encontrado", "novo_nome_usuario": None}), 404
    # Verifica se o usuário tem o cargo de boost
    try:
        membro = bot.get_guild(CANAL_RANKING_ID).get_member(int(id_discord))
        tag_boost = obter_tag_boost(id_discord, membro) if membro else ""
    except:
        tag_boost = ""
    return jsonify({
        "id_alvo": id_jogo,
        "novo_nome_usuario": db["jogadores"][id_discord] + tag_boost
    })

@app.route("/ban", methods=["POST"])
def banir():
    id_jogo = request.form.get("id")
    if not id_jogo:
        return jsonify({"erro": "ID não fornecido"}), 400
    id_discord = db["jogo_para_discord_id"].get(id_jogo)
    if not id_discord or id_discord not in db["jogadores"]:
        return jsonify({"erro": "ID não encontrado"}), 404
    if id_discord not in db["ids_banidos"]:
        db["ids_banidos"].append(id_discord)
        salvar_db(db)
        asyncio.run_coroutine_threadsafe(
            enviar_log(f"Jogador banido: ID do jogo {id_jogo} ID Discord {id_discord}"),
            bot.loop
        )
    return jsonify({"id_db": "id_jogo"})

@app.route("/unban", methods=["POST"])
def desbanir():
    id_jogo = request.form.get("id")
    if not id_jogo:
        return jsonify({"erro": "ID não fornecido"}), 400
    id_discord = db["jogo_para_discord_id"].get(id_jogo)
    if not id_discord or id_discord not in db["jogadores"]:
        return jsonify({"erro": "ID não encontrado"}), 404
    if id_discord in db["ids_banidos"]:
        db["ids_banidos"].remove(id_discord)
        salvar_db(db)
        asyncio.run_coroutine_threadsafe(
            enviar_log(f"Jogador desbanido: ID do jogo {id_jogo} ID Discord {id_discord}"),
            bot.loop
        )
    return jsonify({"id": id_jogo})

@app.route("/check", methods=["GET"])
def verificar():
    nome = request.args.get("username")
    if not nome:
        return jsonify({"erro": "Nome não fornecido"}), 400
    for id_discord, nome_usuario in db["jogadores"].items():
        if nome_usuario == nome:
            id_jogo = next((gid for gid, did in db["jogo_para_discord_id"].items() if did == id_discord), None)
            return jsonify({"banido": id_discord in db["ids_banidos"], "id": id_jogo})
    return jsonify({"banido": False})

@app.route("/add-win", methods=["POST"])
def adicionar_vitoria():
    id_jogo = request.form.get("id")
    if not id_jogo:
        return jsonify({"erro": "ID não fornecido"}), 400
    id_discord = db["jogo_para_discord_id"].get(id_jogo)
    if not id_discord or id_discord not in db["jogadores"]:
        return jsonify({"erro": "ID não encontrado"}), 404

    if id_discord not in db["vitorias"]:
        db["vitorias"][id_discord] = 0

    db["vitorias"][id_discord] += 1
    salvar_db(db)
    asyncio.run_coroutine_threadsafe(
        enviar_log(f"Nova vitória registrada para ID do jogo {id_jogo} ID Discord {id_discord} Total de vitórias {db['vitorias'][id_discord]}"),
        bot.loop
    )
    return jsonify({"id": id_jogo, "vitorias": db["vitorias"][id_discord]})

@app.route("/get-win", methods=["GET"])
def obter_vitoria():
    id_jogo = request.args.get("id")
    if not id_jogo:
        return jsonify({"erro": "ID não fornecido"}), 400
    id_discord = db["jogo_para_discord_id"].get(id_jogo)
    vitorias = db["vitorias"].get(id_discord, 0)
    return jsonify({"id": id_jogo, "vitorias": vitorias})

intents = discord.Intents.default()
intents.message_content = True
intents.presences = True
intents.members = True
bot = commands.Bot(command_prefix="!", intents=intents)

async def enviar_log(msg):
    await bot.wait_until_ready()
    canal = bot.get_channel(CANAL_LOG_ID)
    if canal:
        await canal.send(msg)
    else:
        print(f"Canal de log {CANAL_LOG_ID} não encontrado")

async def enviar_backup_json():
    while True:
        await bot.wait_until_ready()
        canal = bot.get_channel(CANAL_LOG_ID)
        if canal:
            try:
                with open(ARQUIVO_DADOS, 'r') as f:
                    dados_json = json.load(f)
                json_formatado = json.dumps(dados_json, indent=2, sort_keys=True)
                await canal.send(f"Backup do banco de dados em {time.strftime('%Y-%m-%d %H:%M:%S UTC')}:\n```json\n{json_formatado}\n```")
            except Exception as e:
                print(f"Erro ao enviar backup JSON: {e}")
                await canal.send(f"Erro ao enviar backup JSON: {e}")
        await asyncio.sleep(900)

async def restaurar_db_de_log():
    await bot.wait_until_ready()
    canal = bot.get_channel(CANAL_LOG_ID)
    if not canal:
        print(f"Canal de log {CANAL_LOG_ID} não encontrado")
        return

    async for mensagem in canal.history(limit=100):
        if mensagem.author == bot.user and "Backup do banco de dados em" in mensagem.content:
            try:
                inicio_json = mensagem.content.index("```json\n") + 8
                fim_json = mensagem.content.rindex("\n```")
                dados_json = mensagem.content[inicio_json:fim_json]
                novo_db = json.loads(dados_json)
                chaves_necessarias = ["jogadores", "ids_banidos", "proximo_id", "vitorias", "discords", "jogadores_online", "fila_ranking", "jogo_para_discord_id", "autenticacoes_pendentes", "usuarios_permitidos"]
                for chave in chaves_necessarias:
                    if chave not in novo_db:
                        novo_db[chave] = {} if chave in ["jogadores", "vitorias", "discords", "jogadores_online", "jogo_para_discord_id", "autenticacoes_pendentes", "usuarios_permitidos"] else [] if chave in ["ids_banidos", "fila_ranking"] else 1
                global db
                db = novo_db
                salvar_db(db)
                print("JSON restaurado do log mais recente")
                await enviar_log("JSON restaurado do log mais recente")
                break
            except Exception as e:
                print(f"Erro ao restaurar JSON do log: {e}")
                await enviar_log(f"Erro ao restaurar JSON do log: {e}")
                break

class VisualizacaoFilaRanking(View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Entrar na Fila", style=ButtonStyle.green, custom_id="entrar_fila_ranking")
    async def botao_entrar_fila(self, interacao: discord.Interaction, botao: Button):
        id_discord = str(interacao.user.id)
        if id_discord not in db["discords"]:
            await interacao.response.send_message("Você precisa autenticar sua conta Discord no jogo para entrar na fila", ephemeral=True)
            return
        if id_discord in db["ids_banidos"]:
            await interacao.response.send_message("Você está banido e não pode entrar na fila", ephemeral=True)
            return
        if id_discord in db["fila_ranking"]:
            await interacao.response.send_message("Você já está na fila", ephemeral=True)
            return

        db["fila_ranking"].append(id_discord)
        salvar_db(db)
        id_jogo = next((gid for gid, did in db["jogo_para_discord_id"].items() if did == id_discord), "Desconhecido")
        await interacao.response.send_message(f"Você entrou na fila 1v1 Posição: {len(db['fila_ranking'])}", ephemeral=True)
        await atualizar_embed_ranking()

        if len(db["fila_ranking"]) >= 2:
            await iniciar_partida_ranking()

async def atualizar_embed_ranking():
    canal = bot.get_channel(CANAL_RANKING_ID)
    if not canal:
        print(f"Canal {CANAL_RANKING_ID} não encontrado")
        return

    embed = discord.Embed(
        title="Fila de Ranking 1v1",
        description="Jogue e decida o vencedor no final da partida\n\nAguardando jogadores",
        color=discord.Color.blue()
    )
    if db["fila_ranking"]:
        jogador = await bot.fetch_user(int(db["fila_ranking"][0]))
        embed.description = f"Jogue e decida o vencedor no final da partida\n\n{jogador.display_name} vs [Aguardando adversário]"
    embed.set_footer(text="Clique no botão para entrar na fila")

    visualizacao = VisualizacaoFilaRanking()
    async for mensagem in canal.history(limit=100):
        if mensagem.author == bot.user and mensagem.embeds and mensagem.embeds[0].title == "Fila de Ranking 1v1":
            await mensagem.edit(embed=embed, view=visualizacao)
            return
    await canal.send(embed=embed, view=visualizacao)

async def iniciar_partida_ranking():
    if len(db["fila_ranking"]) < 2:
        return

    id_jogador1 = db["fila_ranking"].pop(0)
    id_jogador2 = db["fila_ranking"].pop(0)
    salvar_db(db)

    jogador1 = await bot.fetch_user(int(id_jogador1))
    jogador2 = await bot.fetch_user(int(id_jogador2))
    canal = bot.get_channel(CANAL_RANKING_ID)
    if not canal:
        print(f"Canal {CANAL_RANKING_ID} não encontrado")
        return

    thread = await canal.create_thread(
        name=f"1v1 {jogador1.display_name} vs {jogador2.display_name}",
        auto_archive_duration=60,
        type=discord.ChannelType.private_thread
    )
    await thread.add_user(jogador1)
    await thread.add_user(jogador2)

    embed = discord.Embed(
        title="Partida de Ranking 1v1",
        description=f"{jogador1.display_name} vs {jogador2.display_name}\n\nEscolha o vencedor da partida clicando no botão correspondente",
        color=discord.Color.purple()
    )
    embed.set_footer(text="Ambos os jogadores devem concordar com o vencedor")

    visualizacao = VisualizacaoSelecaoVencedor(id_jogador1, id_jogador2, jogador1.display_name, jogador2.display_name, thread)
    await thread.send(embed=embed, view=visualizacao)
    await thread.send(f"{jogador1.mention} {jogador2.mention} Jogue a partida e selecione o vencedor")
    id_jogo1 = next((gid for gid, did in db["jogo_para_discord_id"].items() if did == id_jogador1), "Desconhecido")
    id_jogo2 = next((gid for gid, did in db["jogo_para_discord_id"].items() if did == id_jogador2), "Desconhecido")
    await enviar_log(f"Partida 1v1 iniciada: {jogador1.display_name} (ID do jogo {id_jogo1} ID Discord {id_jogador1}) vs {jogador2.display_name} (ID do jogo {id_jogo2} ID Discord {id_jogador2})")

    await atualizar_embed_ranking()

class VisualizacaoSelecaoVencedor(View):
    def __init__(self, id_jogador1: str, id_jogador2: str, nome_jogador1: str, nome_jogador2: str, thread):
        super().__init__(timeout=None)
        self.id_jogador1 = id_jogador1
        self.id_jogador2 = id_jogador2
        self.nome_jogador1 = nome_jogador1
        self.nome_jogador2 = nome_jogador2
        self.thread = thread
        self.votos = {}

        self.adicionar_botao(nome_jogador1, id_jogador1)
        self.adicionar_botao(nome_jogador2, id_jogador2)

    def adicionar_botao(self, rotulo: str, id_jogador: str):
        botao = Button(label=rotulo, style=ButtonStyle.blurple, custom_id=f"votar_vencedor_{id_jogador}")
        async def callback_botao(interacao: discord.Interaction):
            if interacao.user.id not in (int(self.id_jogador1), int(self.id_jogador2)):
                await interacao.response.send_message("Apenas os jogadores da partida podem votar", ephemeral=True)
                return
            if interacao.user.id in self.votos:
                await interacao.response.send_message("Você já votou", ephemeral=True)
                return

            self.votos[str(interacao.user.id)] = id_jogador
            id_jogo = next((gid for gid, did in db["jogo_para_discord_id"].items() if did == str(interacao.user.id)), "Desconhecido")
            await interacao.response.send_message(f"Você votou em {rotulo} como vencedor", ephemeral=True)
            await enviar_log(f"Voto registrado por ID do jogo {id_jogo} ID Discord {interacao.user.id} para {rotulo} (ID Discord {id_jogador})")

            if len(self.votos) == 2:
                await self.processar_votos(interacao.channel)

        botao.callback = callback_botao
        self.add_item(botao)

    async def processar_votos(self, canal):
        voto1 = self.votos.get(self.id_jogador1)
        voto2 = self.votos.get(self.id_jogador2)

        if voto1 == voto2:
            id_vencedor = voto1
            id_perdedor = self.id_jogador1 if id_vencedor == self.id_jogador2 else self.id_jogador2
            nome_vencedor = self.nome_jogador1 if id_vencedor == self.id_jogador1 else self.nome_jogador2
            nome_perdedor = self.nome_jogador2 if id_vencedor == self.id_jogador1 else self.nome_jogador1

            if id_vencedor not in db["vitorias"]:
                db["vitorias"][id_vencedor] = 0
            db["vitorias"][id_vencedor] += 1
            salvar_db(db)

            id_jogo_vencedor = next((gid for gid, did in db["jogo_para_discord_id"].items() if did == id_vencedor), "Desconhecido")
            id_jogo_perdedor = next((gid for gid, did in db["jogo_para_discord_id"].items() if did == id_perdedor), "Desconhecido")
            await canal.send(f"{nome_vencedor} venceu a partida Total de vitórias: {db['vitorias'][id_vencedor]}")
            await enviar_log(f"Vitória registrada para {nome_vencedor} (ID do jogo {id_jogo_vencedor} ID Discord {id_vencedor}) contra {nome_perdedor} (ID do jogo {id_jogo_perdedor} ID Discord {id_perdedor}) Total de vitórias: {db['vitorias'][id_vencedor]}")
            await self.thread.edit(archived=True, locked=True)
        else:
            mencoes_admin = " ".join(f"<@&{id_cargo}>" for id_cargo in CARGOS_ADMIN) or "@admin"
            await canal.send(f"Os jogadores não concordaram com o vencedor {mencoes_admin}, por favor, decidam o vencedor")
            await enviar_log(f"Conflito de votos na partida {self.nome_jogador1} vs {self.nome_jogador2} Aguardando decisão do admin")
            visualizacao = VisualizacaoSelecaoVencedorAdmin(self.id_jogador1, self.id_jogador2, self.nome_jogador1, self.nome_jogador2, self.thread)
            await canal.send(embed=discord.Embed(title="Escolher Vencedor", description="Admins, selecionem o vencedor da partida", color=discord.Color.red()), view=visualizacao)

class VisualizacaoSelecaoVencedorAdmin(View):
    def __init__(self, id_jogador1: str, id_jogador2: str, nome_jogador1: str, nome_jogador2: str, thread):
        super().__init__(timeout=None)
        self.id_jogador1 = id_jogador1
        self.id_jogador2 = id_jogador2
        self.nome_jogador1 = nome_jogador1
        self.nome_jogador2 = nome_jogador2
        self.thread = thread

        self.adicionar_botao(nome_jogador1, id_jogador1)
        self.adicionar_botao(nome_jogador2, id_jogador2)

    def adicionar_botao(self, rotulo: str, id_jogador: str):
        botao = Button(label=rotulo, style=ButtonStyle.red, custom_id=f"admin_votar_vencedor_{id_jogador}")
        async def callback_botao(interacao: discord.Interaction):
            if not any(cargo.id in CARGOS_ADMIN or interacao.user.guild_permissions.administrator for cargo in interacao.user.roles):
                await interacao.response.send_message("Apenas admins podem selecionar o vencedor", ephemeral=True)
                return

            id_vencedor = id_jogador
            id_perdedor = self.id_jogador1 if id_vencedor == self.id_jogador2 else self.id_jogador2
            nome_vencedor = self.nome_jogador1 if id_vencedor == self.id_jogador1 else self.nome_jogador2
            nome_perdedor = self.nome_jogador2 if id_vencedor == self.id_jogador1 else self.nome_jogador1

            if id_vencedor not in db["vitorias"]:
                db["vitorias"][id_vencedor] = 0
            db["vitorias"][id_vencedor] += 1
            salvar_db(db)

            id_jogo_vencedor = next((gid for gid, did in db["jogo_para_discord_id"].items() if did == id_vencedor), "Desconhecido")
            id_jogo_perdedor = next((gid for gid, did in db["jogo_para_discord_id"].items() if did == id_perdedor), "Desconhecido")
            await interacao.response.send_message(f"{nome_vencedor} foi selecionado como vencedor pelo admin", ephemeral=True)
            await interacao.channel.send(f"{nome_vencedor} venceu a partida Total de vitórias: {db['vitorias'][id_vencedor]}")
            await enviar_log(f"Vitória registrada para {nome_vencedor} (ID do jogo {id_jogo_vencedor} ID Discord {id_vencedor}) contra {nome_perdedor} (ID do jogo {id_jogo_perdedor} ID Discord {id_perdedor}) por decisão do admin Total de vitórias: {db['vitorias'][id_vencedor]}")
            await self.thread.edit(archived=True, locked=True)
        botao.callback = callback_botao
        self.add_item(botao)

@bot.event
async def on_ready():
    print(f"Bot conectado como {bot.user}")
    try:
        await bot.tree.sync()
        print("Comandos sincronizados com Discord: /nick, /ban, /unban, /buscar, /ranking, /ranked, /add-wins, /dar-permissao")
        await enviar_log(f"Bot iniciado como {bot.user}")
        await restaurar_db_de_log()
        bot.loop.create_task(enviar_backup_json())
    except Exception as e:
        print(f"Erro ao sincronizar comandos: {e}")
        await enviar_log(f"Erro ao sincronizar comandos: {e}")

@bot.tree.command(name="nick", description="Alterar apelido por ID do jogo ou menção do Discord")
@app_commands.describe(identificador="ID do jogo ou menção do Discord (@usuário)", novonome="Novo nome")
async def nick(interacao: discord.Interaction, identificador: str, novonome: str):
    if not (any(cargo.id in CARGOS_ADMIN for cargo in interacao.user.roles) or interacao.user.guild_permissions.administrator or str(interacao.user.id) in db["usuarios_permitidos"]):
        await interacao.response.send_message("Você não tem permissão para usar este comando", ephemeral=True)
        return

    id_discord = None
    tag_discord = None

    if identificador.startswith("<@") and identificador.endswith(">"):
        try:
            id_usuario = identificador.strip("<@!>")
            membro = await interacao.guild.fetch_member(int(id_usuario))
            tag_discord = f"{membro.name}#{membro.discriminator}"
            id_discord = str(membro.id)
        except discord.errors.NotFound:
            await interacao.response.send_message("Usuário Discord não encontrado", ephemeral=True)
            return
    else:
        id_discord = db["jogo_para_discord_id"].get(identificador)

    if not id_discord or id_discord not in db["discords"]:
        await interacao.response.send_message(f"ID {identificador} não está autenticado com Discord", ephemeral=True)
        return

    if len(novonome) < 4 or len(novonome) > 200:
        await interacao.response.send_message("O nome deve ter entre 4 e 200 caracteres", ephemeral=True)
        return

    # Verifica se o usuário tem o cargo de boost
    membro = await interacao.guild.fetch_member(int(id_discord))
    tag_boost = obter_tag_boost(id_discord, membro) if membro else ""

    db["jogadores"][id_discord] = novonome + tag_boost
    salvar_db(db)
    id_jogo = next((gid for gid, did in db["jogo_para_discord_id"].items() if did == id_discord), "Desconhecido")
    await interacao.response.send_message(f"Apelido para ID do jogo {id_jogo} atualizado para {novonome + tag_boost}", ephemeral=True)
    await enviar_log(f"Apelido alterado: ID do jogo {id_jogo} ID Discord {id_discord} para {novonome + tag_boost}")

@bot.tree.command(name="ban", description="Banir um jogador por ID do jogo")
@app_commands.describe(id="ID do jogo do jogador a ser banido")
async def ban_cmd(interacao: discord.Interaction, id: str):
    if not (any(cargo.id in CARGOS_ADMIN for cargo in interacao.user.roles) or interacao.user.guild_permissions.administrator or str(interacao.user.id) in db["usuarios_permitidos"]):
        await interacao.response.send_message("Você não tem permissão para usar este comando", ephemeral=True)
        return

    id_discord = db["jogo_para_discord_id"].get(id)
    if not id_discord or id_discord not in db["discords"]:
        await interacao.response.send_message(f"ID {id} não está autenticado com Discord", ephemeral=True)
        return
    if id_discord in db["ids_banidos"]:
        await interacao.response.send_message(f"ID {id} já está banido", ephemeral=True)
        return
    db["ids_banidos"].append(id_discord)
    salvar_db(db)
    await interacao.response.send_message(f"Jogador com ID do jogo {id} foi banido", ephemeral=True)
    await enviar_log(f"Jogador banido: ID do jogo {id} ID Discord {id_discord}")

@bot.tree.command(name="unban", description="Desbanir um jogador por ID do jogo")
@app_commands.describe(id="ID do jogo do jogador a ser desbanido")
async def unban_cmd(interacao: discord.Interaction, id: str):
    if not (any(cargo.id in CARGOS_ADMIN for cargo in interacao.user.roles) or interacao.user.guild_permissions.administrator or str(interacao.user.id) in db["usuarios_permitidos"]):
        await interacao.response.send_message("Você não tem permissão para usar este comando", ephemeral=True)
        return

    id_discord = db["jogo_para_discord_id"].get(id)
    if not id_discord or id_discord not in db["discords"]:
        await interacao.response.send_message(f"ID {id} não está autenticado com Discord", ephemeral=True)
        return
    if id_discord not in db["ids_banidos"]:
        await interacao.response.send_message(f"ID {id} não está banido", ephemeral=True)
        return
    db["ids_banidos"].remove(id_discord)
    salvar_db(db)
    await interacao.response.send_message(f"Jogador com ID do jogo {id} foi desbanido", ephemeral=True)
    await enviar_log(f"Jogador desbanido: ID do jogo {id} ID Discord {id_discord}")

@bot.tree.command(name="buscar", description="Buscar informações do jogador por ID do jogo ou menção do Discord")
@app_commands.describe(identificador="ID do jogo ou menção do Discord (@usuário)")
async def buscar(interacao: discord.Interaction, identificador: str):
    if not (any(cargo.id in CARGOS_ADMIN for cargo in interacao.user.roles) or interacao.user.guild_permissions.administrator or str(interacao.user.id) in db["usuarios_permitidos"]):
        await interacao.response.send_message("Você não tem permissão para usar este comando", ephemeral=True)
        return

    id_discord = None
    tag_discord = None

    if identificador.startswith("<@") and identificador.endswith(">"):
        try:
            id_usuario = identificador.strip("<@!>")
            membro = await interacao.guild.fetch_member(int(id_usuario))
            tag_discord = f"{membro.name}#{membro.discriminator}"
            id_discord = str(membro.id)
        except discord.errors.NotFound:
            await interacao.response.send_message("Usuário Discord não encontrado", ephemeral=True)
            return
    else:
        id_discord = db["jogo_para_discord_id"].get(identificador)

    if not id_discord or id_discord not in db["discords"]:
        await interacao.response.send_message(f"ID {identificador} não está autenticado com Discord", ephemeral=True)
        return

    nome = db["jogadores"].get(id_discord, f"ID {id_discord}")
    banido = id_discord in db["ids_banidos"]
    vitorias = db["vitorias"].get(id_discord, 0)
    tag_discord = db["discords"].get(id_discord, "Não autenticado")
    esta_online = db["jogadores_online"].get(id_discord, False)
    id_jogo = next((gid for gid, did in db["jogo_para_discord_id"].items() if did == id_discord), "Desconhecido")

    embed = discord.Embed(title=f"Informações do Jogador ID do jogo {id_jogo}", color=discord.Color.blue())
    embed.add_field(name="Nome", value=nome, inline=False)
    embed.add_field(name="Banido", value="Sim" if banido else "Não", inline=False)
    embed.add_field(name="Vitórias", value=str(vitorias), inline=False)
    embed.add_field(name="Discord", value=tag_discord, inline=False)
    embed.add_field(name="Online", value="Sim" if esta_online else "Não", inline=False)

    await interacao.response.send_message(embed=embed, ephemeral=True)

@bot.tree.command(name="ranking", description="Exibir classificação dos jogadores por vitórias")
async def ranking(interacao: discord.Interaction):
    if not (any(cargo.id in CARGOS_ADMIN for cargo in interacao.user.roles) or interacao.user.guild_permissions.administrator or str(interacao.user.id) in db["usuarios_permitidos"]):
        await interacao.response.send_message("Você não tem permissão para usar este comando", ephemeral=True)
        return

    if not db["vitorias"]:
        await interacao.response.send_message("Nenhum jogador com vitórias registradas", ephemeral=True)
        return

    vitorias_ordenadas = sorted(db["vitorias"].items(), key=lambda x: x[1], reverse=True)[:10]
    embed = discord.Embed(title="Classificação de Vitórias", color=discord.Color.gold())
    placar = ""
    for i, (id_discord, vitorias) in enumerate(vitorias_ordenadas, 1):
        nome = db["jogadores"].get(id_discord, f"ID {id_discord}")
        tag_discord = db["discords"].get(id_discord, "Não autenticado")
        id_jogo = next((gid for gid, did in db["jogo_para_discord_id"].items() if did == id_discord), "Desconhecido")
        placar += f"{i} {nome} (ID do jogo: {id_jogo}) - {vitorias} vitórias\nDiscord: {tag_discord}\n\n"
    
    embed.description = placar or "Sem dados para exibir"
    embed.set_footer(text="Top 10 jogadores por vitórias")
    await interacao.response.send_message(embed=embed)

@bot.tree.command(name="ranked", description="Iniciar fila de ranking 1v1")
async def ranked(interacao: discord.Interaction):
    if interacao.channel_id != CANAL_RANKING_ID:
        await interacao.response.send_message("Este comando só pode ser usado no canal de ranking", ephemeral=True)
        return

    embed = discord.Embed(
        title="Fila de Ranking 1v1",
        description="Jogue e decida o vencedor no final da partida\n\nAguardando jogadores",
        color=discord.Color.blue()
    )
    embed.set_footer(text="Clique no botão para entrar na fila")
    visualizacao = VisualizacaoFilaRanking()
    await interacao.response.send_message(embed=embed, view=visualizacao)
    await enviar_log(f"Fila de ranking iniciada por {interacao.user.display_name} (ID Discord {interacao.user.id})")

@bot.tree.command(name="add-wins", description="Adicionar vitórias a um jogador por ID do jogo ou menção do Discord")
@app_commands.describe(identificador="ID do jogo ou menção do Discord (@usuário)", quantidade="Número de vitórias a adicionar")
async def add_wins(interacao: discord.Interaction, identificador: str, quantidade: int):
    if not (any(cargo.id in CARGOS_ADMIN for cargo in interacao.user.roles) or interacao.user.guild_permissions.administrator):
        await interacao.response.send_message("Você não tem permissão para usar este comando", ephemeral=True)
        return

    if quantidade <= 0:
        await interacao.response.send_message("O número de vitórias deve ser maior que zero", ephemeral=True)
        return

    id_discord = None
    tag_discord = None

    if identificador.startswith("<@") and identificador.endswith(">"):
        try:
            id_usuario = identificador.strip("<@!>")
            membro = await interacao.guild.fetch_member(int(id_usuario))
            tag_discord = f"{membro.name}#{membro.discriminator}"
            id_discord = str(membro.id)
        except discord.errors.NotFound:
            await interacao.response.send_message("Usuário Discord não encontrado", ephemeral=True)
            return
    else:
        id_discord = db["jogo_para_discord_id"].get(identificador)

    if not id_discord or id_discord not in db["discords"]:
        await interacao.response.send_message(f"ID {identificador} não está autenticado com Discord", ephemeral=True)
        return

    if id_discord not in db["vitorias"]:
        db["vitorias"][id_discord] = 0

    db["vitorias"][id_discord] += quantidade
    salvar_db(db)
    id_jogo = next((gid for gid, did in db["jogo_para_discord_id"].items() if did == id_discord), "Desconhecido")
    await interacao.response.send_message(f"Adicionadas {quantidade} vitórias ao ID do jogo {id_jogo} Total de vitórias: {db['vitorias'][id_discord]}", ephemeral=True)
    await enviar_log(f"Adicionadas {quantidade} vitórias a {db['jogadores'].get(id_discord, 'Desconhecido')} (ID do jogo {id_jogo} ID Discord {id_discord}) Total de vitórias: {db['vitorias'][id_discord]}")

@bot.tree.command(name="dar-permissao", description="Conceder permissão para usar comandos (exceto /add-wins e /ranked)")
@app_commands.describe(usuario="Menção do Discord (@usuário)")
async def dar_permissao(interacao: discord.Interaction, usuario: str):
    if not (any(cargo.id in CARGOS_ADMIN for cargo in interacao.user.roles) or interacao.user.guild_permissions.administrator):
        await interacao.response.send_message("Você não tem permissão para usar este comando", ephemeral=True)
        return

    if not usuario.startswith("<@") or not usuario.endswith(">"):
        await interacao.response.send_message("Forneça uma menção válida do Discord (@usuário)", ephemeral=True)
        return

    try:
        id_usuario = usuario.strip("<@!>")
        membro = await interacao.guild.fetch_member(int(id_usuario))
        id_discord = str(membro.id)
        tag_discord = f"{membro.name}#{membro.discriminator}"
        db["usuarios_permitidos"][id_discord] = tag_discord
        salvar_db(db)
        await interacao.response.send_message(f"Permissão concedida para {tag_discord} usar comandos (exceto /add-wins e /ranked)", ephemeral=True)
        await enviar_log(f"Permissão concedida para {tag_discord} (ID Discord {id_discord}) usar comandos (exceto /add-wins e /ranked)")
    except discord.errors.NotFound:
        await interacao.response.send_message("Usuário Discord não encontrado", ephemeral=True)

def rodar_flask():
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 3000)), use_reloader=False)

if __name__ == "__main__":
    Thread(target=rodar_flask, daemon=True).start()
    bot.run(BOT_TOKEN)
