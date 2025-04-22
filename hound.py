import discord
from discord.ext import commands
from discord.ui import Button, View, Modal, TextInput
import json
from datetime import datetime

bot = commands.Bot(command_prefix="/", intents=discord.Intents.all())

# Конфигурация
with open('token_hound.json') as f:
    config = json.load(f)

SOURCE_CHANNEL_ID = config['source_channel_id']
TARGET_CHANNEL_ID = config['target_channel_id'] 
RECRUITER_ROLE_ID = config['recruiter_role_id']
ACCEPTED_ROLE_ID = config['accepted_role_id']
LOGS_CHANNEL_ID = config['logs_channel_id']

class CallModal(Modal, title="Укажите время обзвона"):
    time = TextInput(label="Формат: 15:30 20.05.2024", placeholder="ЧЧ:ММ ДД.ММ.ГГГГ")
    
    def __init__(self, view: View):
        super().__init__()
        self.view = view

    async def on_submit(self, interaction: discord.Interaction):
        try:
            call_time = datetime.strptime(self.time.value, "%H:%M %d.%m.%Y")
            formatted_time = call_time.strftime("%d %B в %H:%M")
            
            embed = self.view.message.embeds[0]
            embed.add_field(
                name="Статус",
                value=f"🕒 Вызван на обзвон {interaction.user.mention}\n**Время:** {formatted_time}",
                inline=False
            )
            
            self.view.clear_items()
            self.view.add_item(Button(
                label="Принять",
                style=discord.ButtonStyle.success,
                custom_id=f"accept_{self.view.member.id}",
                emoji="✅"
            ))
            self.view.add_item(Button(
                label="Отклонить",
                style=discord.ButtonStyle.danger,
                custom_id=f"reject_{self.view.member.id}",
                emoji="❌"
            ))
            
            await interaction.response.edit_message(embed=embed, view=self.view)
            
            embed = discord.Embed(
                title="📅 Вас вызвали на обзвон",
                description=f"**Дата:** {formatted_time}\n**Рекрутер:** {interaction.user.mention}",
                color=0x3498db
            )
            await self.view.member.send(embed=embed)
            
        except ValueError:
            await interaction.response.send_message(
                "❌ Неверный формат времени! Используйте ЧЧ:ММ ДД.ММ.ГГГГ",
                ephemeral=True
            )

class ApplicationView(View):
    def __init__(self, member: discord.Member = None, message: discord.Message = None):
        super().__init__(timeout=None)
        self.member = member
        self.message = message
        
        user_id = member.id if member else 0
        
        buttons = [
            Button(label="Принять", style=discord.ButtonStyle.success, custom_id=f"accept_{user_id}", emoji="✅"),
            Button(label="Отклонить", style=discord.ButtonStyle.danger, custom_id=f"reject_{user_id}", emoji="❌"),
            Button(label="Обзвон", style=discord.ButtonStyle.primary, custom_id=f"call_{user_id}", emoji="📞")
        ]
        
        for btn in buttons:
            self.add_item(btn)

    async def interaction_check(self, interaction: discord.Interaction):
        if not any(role.id in [RECRUITER_ROLE_ID] for role in interaction.user.roles) and not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("❌ У вас нет прав для этого действия!", ephemeral=True)
            return False
        return True

    async def disable_all_buttons(self):
        for item in self.children:
            item.disabled = True
        if self.message:
            await self.message.edit(view=self)

    async def accept_application(self, interaction: discord.Interaction):
        role = interaction.guild.get_role(ACCEPTED_ROLE_ID)
        if role:
            try:
                await self.member.add_roles(role)
            except discord.Forbidden:
                pass
        
        embed = self.message.embeds[0]
        embed.add_field(
            name="Статус",
            value=f"✅ Принято {interaction.user.mention}",
            inline=False
        )
        
        await interaction.response.edit_message(embed=embed, view=None)  # Полностью убираем кнопки
        
        embed = discord.Embed(
            title="🎉 Ваша заявка одобрена!",
            description="Добро пожаловать в нашу команду!\nОжидайте дальнейших инструкций.",
            color=0x2ecc71
        )
        embed.set_thumbnail(url=self.member.display_avatar.url)
        await self.member.send(embed=embed)
        
        await self.log_action(interaction, "Принята", 0x2ecc71)

    async def reject_application(self, interaction: discord.Interaction):
        embed = self.message.embeds[0]
        embed.add_field(
            name="Статус",
            value=f"❌ Отклонено {interaction.user.mention}",
            inline=False
        )
        
        await interaction.response.edit_message(embed=embed, view=None)  # Полностью убираем кнопки
        
        embed = discord.Embed(
            title="😕 Заявка отклонена",
            description="К сожалению, ваша заявка не была одобрена.",
            color=0xe74c3c
        )
        embed.set_thumbnail(url=self.member.display_avatar.url)
        await self.member.send(embed=embed)
        
        await self.log_action(interaction, "Отклонена", 0xe74c3c)

    async def call_for_interview(self, interaction: discord.Interaction):
        await interaction.response.send_modal(CallModal(self))

    async def log_action(self, interaction, action, color):
        log_channel = bot.get_channel(LOGS_CHANNEL_ID)
        if log_channel:
            embed = discord.Embed(
                title=f"Заявка {action.lower()}",
                color=color,
                timestamp=datetime.now()
            )
            embed.add_field(name="Пользователь", value=self.member.mention)
            embed.add_field(name="Рекрутер", value=interaction.user.mention)
            embed.set_thumbnail(url=self.member.display_avatar.url)
            await log_channel.send(embed=embed)

@bot.event
async def on_message(message):
    print(f"Получено сообщение: {message.content}")  # Логирование входящих сообщений
    
    # Игнорируем сообщения от ботов (кроме вебхуков)
    if message.author.bot and not message.webhook_id:
        return

    # Проверяем что сообщение из нужного канала
    if message.channel.id == SOURCE_CHANNEL_ID:
        try:
            print("Сообщение из исходного канала")  # Логирование
            
            member = None
            username = None
            
            # 1. Ищем по упоминанию
            if message.mentions:
                member = message.mentions[0]
                print(f"Найден пользователь по упоминанию: {member}")
            
            # 2. Ищем по имени в тексте
            if not member and message.content:
                for line in message.content.split('\n'):
                    if 'discord:' in line.lower():
                        username = line.split(':')[-1].strip()
                        print(f"Ищем пользователя по имени: {username}")
                        member = discord.utils.find(
                            lambda m: m.name == username or m.display_name == username,
                            message.guild.members
                        )
                        if member:
                            break
            
            # 3. Ищем в embed полях
            if not member and message.embeds:
                for embed in message.embeds:
                    for field in embed.fields:
                        if 'discord' in field.name.lower():
                            username = field.value.strip('@')
                            print(f"Ищем пользователя по embed: {username}")
                            member = discord.utils.find(
                                lambda m: m.name == username or m.display_name == username,
                                message.guild.members
                            )
                            if member:
                                break
            
            if not member:
                print("Не удалось определить пользователя")
                return

            print(f"Найден пользователь: {member}")  # Логирование
            
            # Создаем embed для пересылки
            embed = discord.Embed(
                title="📋 Новая заявка",
                description=f"От пользователя: {member.mention}",
                color=0x3498db,
                timestamp=datetime.now()
            )
            
            # Добавляем только нужные поля (исключая Discord и email)
            excluded_fields = ['discord', 'email', 'ваш дискорд', 'почта']
            if message.embeds:
                for field in message.embeds[0].fields:
                    if not any(ex in field.name.lower() for ex in excluded_fields):
                        embed.add_field(
                            name=field.name,
                            value=field.value or "Не указано",
                            inline=False
                        )
            
            # Большой портрет пользователя
            embed.set_thumbnail(url=member.display_avatar.url)
            embed.set_author(name=str(member), icon_url=member.display_avatar.url)
            embed.set_footer(text=f"ID: {member.id}")

            # Отправляем в целевой канал
            target_channel = bot.get_channel(TARGET_CHANNEL_ID)
            if target_channel:
                print(f"Отправляем сообщение в канал {TARGET_CHANNEL_ID}")  # Логирование
                msg = await target_channel.send(
                    content=f"<@&{RECRUITER_ROLE_ID}> Новая заявка!",
                    embed=embed
                )
                view = ApplicationView(member, msg)
                await msg.edit(view=view)
                print("Сообщение успешно отправлено")  # Логирование

        except Exception as e:
            print(f"Ошибка обработки заявки: {e}")  # Логирование ошибок

    await bot.process_commands(message)

@bot.event
async def on_interaction(interaction: discord.Interaction):
    if interaction.type == discord.InteractionType.component:
        custom_id = interaction.data["custom_id"]
        if custom_id.startswith(("accept_", "reject_", "call_")):
            action, user_id = custom_id.split('_')
            member = interaction.guild.get_member(int(user_id))
            
            if not member:
                await interaction.response.send_message("Пользователь не найден", ephemeral=True)
                return
            
            view = ApplicationView(member, interaction.message)
            
            if action == "accept":
                await view.accept_application(interaction)
            elif action == "reject":
                await view.reject_application(interaction)
            elif action == "call":
                await view.call_for_interview(interaction)

@bot.event
async def on_ready():
    print(f"Бот {bot.user} готов к работе!")
    try:
        bot.add_view(ApplicationView())
    except Exception as e:
        print(f"Ошибка при регистрации View: {e}")

bot.run(config['token'])