import discord
from discord.ext import commands
from discord.ui import Button, View, Modal, TextInput
import json
import os
from datetime import datetime

bot = commands.Bot(command_prefix="!", intents=discord.Intents.all())

# Конфигурация
try:
    script_dir = os.path.dirname(os.path.abspath(__file__))
    config_path = os.path.join(script_dir, 'token_hound.json')
    
    with open(config_path, 'r', encoding='utf-8') as x:
        config = json.load(x)
        
    TARGET_CHANNEL_ID = int(config['target_channel_id'])
    RECRUITER_ROLE_ID = int(config['recruiter_role_id'])
    ACCEPTED_ROLE_ID = int(config['accepted_role_id'])
    LOGS_CHANNEL_ID = int(config['logs_channel_id'])
    APPLICATIONS_CHANNEL_ID = int(config['applications_channel_id'])
    
except FileNotFoundError:
    print("Error: token_hound.json file not found!")
    exit()
except json.JSONDecodeError:
    print("Error: token_hound.json contains invalid JSON!")
    exit()
except PermissionError:
    print("Error: Permission denied when trying to read token_hound.json!")
    exit()
except KeyError as e:
    print(f"Error: Missing required key in config: {e}")
    exit()
except ValueError as e:
    print(f"Error: Invalid ID format in config: {e}")
    exit()

class ApplicationForm(Modal, title="Подача заявки"):
    online = TextInput(
        label="Ваш онлайн (сколько вы обычно игрете в день)",
        placeholder="Например: 3-6ч",
        required=True
    )
    
    age = TextInput(
        label="Сколько вам лет?",
        placeholder="Например: 21",
        required=True
    )
    
    source = TextInput(
        label="Откуда вы узнали о нас?",
        placeholder="Например: от друга, с маркета и т.д.",
        required=True
    )
    
    stats_id = TextInput(
        label="Ваш статистический ID (статик)",
        required=True
    )

    async def on_submit(self, interaction: discord.Interaction):
        embed = discord.Embed(
            title="📋 Новая заявка",
            description=f"От пользователя: {interaction.user.mention}",
            color=0x3498db,
            timestamp=datetime.now()
        )
        
        embed.add_field(name="🕒 Онлайн", value=self.online.value, inline=False)
        embed.add_field(name="🎂 Возраст", value=self.age.value, inline=False)
        embed.add_field(name="🔍 Откуда узнали", value=self.source.value, inline=False)
        if self.stats_id.value:
            embed.add_field(name="📊 Статистический ID", value=self.stats_id.value, inline=False)
        
        embed.set_thumbnail(url=interaction.user.display_avatar.url)
        embed.set_author(name=str(interaction.user), icon_url=interaction.user.display_avatar.url)
        embed.set_footer(text=f"ID: {interaction.user.id}")

        target_channel = bot.get_channel(TARGET_CHANNEL_ID)
        if target_channel:
            msg = await target_channel.send(
                content=f"<@&{RECRUITER_ROLE_ID}> Новая заявка!",
                embed=embed
            )
            view = ApplicationView(interaction.user, msg)
            await msg.edit(view=view)
        
        await interaction.response.send_message(
            "✅ Ваша заявка успешно отправлена! Ожидайте ответа.",
            ephemeral=True
        )

class ApplicationButton(Button):
    def __init__(self):
        super().__init__(
            label="Подать заявку",
            style=discord.ButtonStyle.primary,
            emoji="📝"
        )
    
    async def callback(self, interaction: discord.Interaction):
        await interaction.response.send_modal(ApplicationForm())

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
        if not any(role.id == RECRUITER_ROLE_ID for role in interaction.user.roles) and not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("❌ У вас нет прав для этого действия!", ephemeral=True)
            return False
        return True

    async def accept_application(self, interaction: discord.Interaction):
        role = interaction.guild.get_role(ACCEPTED_ROLE_ID)
        if role:
            try:
                await self.member.add_roles(role)
            except discord.Forbidden:
                await interaction.followup.send("❌ Не удалось выдать роль (недостаточно прав)", ephemeral=True)
        
        embed = self.message.embeds[0]
        embed.add_field(
            name="Статус",
            value=f"✅ Принято {interaction.user.mention}",
            inline=False
        )
        
        await interaction.response.edit_message(embed=embed, view=None)
        
        try:
            embed = discord.Embed(
                title="🎉 Ваша заявка одобрена!",
                description="Добро пожаловать в Hound!\nдля получения инвайта Обратитесь в личные сообщения к тому кто вас принял или старшему составу семьи.",
                color=0x2ecc71
            )
            embed.set_thumbnail(url=self.member.display_avatar.url)
            await self.member.send(embed=embed)
        except discord.Forbidden:
            await interaction.followup.send("❌ Не удалось отправить сообщение пользователю (закрытые ЛС)", ephemeral=True)
        
        await self.log_action(interaction, "Принята", 0x2ecc71)

    async def reject_application(self, interaction: discord.Interaction):
        embed = self.message.embeds[0]
        embed.add_field(
            name="Статус",
            value=f"❌ Отклонено {interaction.user.mention}",
            inline=False
        )
        
        await interaction.response.edit_message(embed=embed, view=None)
        
        try:
            embed = discord.Embed(
                title="😕 Заявка отклонена",
                description="К сожалению, ваша заявка не была одобрена.",
                color=0xe74c3c
            )
            embed.set_thumbnail(url=self.member.display_avatar.url)
            await self.member.send(embed=embed)
        except discord.Forbidden:
            await interaction.followup.send("❌ Не удалось отправить сообщение пользователю (закрытые ЛС)", ephemeral=True)
        
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
            embed.add_field(name="Пользователь", value=f"{self.member.mention} ({self.member.id})")
            embed.add_field(name="Рекрутер", value=interaction.user.mention)
            embed.set_thumbnail(url=self.member.display_avatar.url)
            await log_channel.send(embed=embed)

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

@bot.hybrid_command(name="setup", description="Создает сообщение с кнопкой для подачи заявки")
@commands.has_permissions(administrator=True)
async def setup(ctx: commands.Context):
    """Создает сообщение с кнопкой для подачи заявки"""
    embed = discord.Embed(
        title="🌟 **Добро пожаловать в семейный Discord Hound!** 🌟",
        description=(
            "Хотите стать частью нашей дружной семьи? У нас есть всё для вашего комфорта и успеха:\n\n"
            "🚗 **Крутой автопарк и семейный дом**\n\n"
            "В нашем гараже всегда есть свободные места и крутые тачки\n\n"
            "🏆 **Премии для самых активных**\n\n"
            "Участвуйте в жизни семьи  — получайте заслуженные награды! Ваша активность не останется без внимания.\n\n"
            "🤝 **Поддержка от опытных игроков гос.струкур**\n\n"
            "Новички — не переживайте! Наши старожилы помогут вам освоиться и добиться успеха в гос структурах.\n\n"
            "🎉 **Общение с крутыми людьми**\n\n"
            "мы все добрые и отзывчивые и готовы обьяснить почти что угодно да и просто поболтать будет калсно) — здесь вы найдёте друзей и единомышленников!\n\n"
            "📋 **Критерии для вступления:**\n\n"
                "✔ **Активность** – нормальный онлайн.\n"
                "✔ **16+** (могут быть и исключения).\n"
                "✔** Адекватность** – вежливость и хладнокровие в любой ситуации.\n"
                "✔** Командный дух** – будь просто человеком.\n\n"
                "**Ждём именно тебя! Присоединяйся и стань частью Hound Family!** 🐾💛\n\n"
        ),
        color=0x5865F2
    )
    embed.set_footer(text="для подачи заявки жми на кнопку снизу")
    
    view = View()
    view.add_item(ApplicationButton())
    
    await ctx.send(embed=embed, view=view)

@bot.hybrid_command(name="apply", description="Подать заявку на вступление")
async def apply(ctx: commands.Context):
    """Позволяет пользователю подать заявку напрямую через команду"""
    if ctx.interaction:
        await ctx.interaction.response.send_modal(ApplicationForm())
    else:
        await ctx.send("Эта команда доступна только через slash-команды (/apply)")

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
    bot.add_view(ApplicationView())
    try:
        await bot.tree.sync()
        print("Синхронизированы команды меню")
    except Exception as e:
        print(f"Ошибка синхронизации команд: {e}")

bot.run(config['token'])