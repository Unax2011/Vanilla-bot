"""
Discord Reminder Bot
A bot that sends reminder messages every N messages in a specific channel
"""

import discord
from discord.ext import commands
from discord import app_commands
import logging
import json
import os
import asyncio
import tempfile
from datetime import datetime
from typing import Dict, Optional, Literal

class ReminderBot(commands.Bot):
    """Discord bot that sends reminders after a certain number of messages"""
    
    def __init__(self, config):
        # Set up bot intents with all necessary permissions
        intents = discord.Intents.default()
        intents.message_content = True  # Enable to read message content for commands
        intents.guilds = True
        intents.members = True  # Enable for welcome/goodbye detection
        
        # Initialize the bot
        super().__init__(
            command_prefix='!',  # We won't use commands, but it's required
            intents=intents,
            help_command=None
        )
        
        self.config = config
        self.logger = logging.getLogger(__name__)
        
        # Message counter storage
        self.message_counters: Dict[int, int] = {}
        self.counter_file = 'message_counters.json'
        
        # Suggestions command counter
        self.suggestions_command_counter = 0
        self.suggestions_command_threshold = 5
        
        # Help message counter for normal messages
        self.help_message_counter = 0
        self.help_message_threshold = 10
        
        # Ticket system
        self.tickets_file = 'tickets.json'
        self.ticket_counter = 0
        
        # Welcome channel ID
        self.welcome_channel_id = 1386434424781934724
        
        # Suggestions results channel ID
        self.suggestions_results_channel_id = 1386735237165351073
        
        # Strikes system
        self.strikes_file = 'strikes.json'
        
        # Suggestions system
        self.suggestions_file = 'suggestions.json'
        
        # Load existing counters from file
        self.load_counters()
        
        # Add strike command to tree with proper decoration
        @app_commands.command(name="strike", description="Gestiona strikes de usuarios")
        @app_commands.describe(
            accion="Acción a realizar",
            usuario="Usuario al que aplicar la acción",
            tipo="Tipo de strike (solo para add)",
            motivo="Motivo del strike (solo para add)"
        )
        async def strike_slash_command(
            interaction: discord.Interaction,
            accion: Literal["add", "check", "remove"],
            usuario: discord.Member,
            tipo: Optional[Literal["leve", "moderado", "grave"]] = None,
            motivo: Optional[str] = None
        ):
            await self.strike_command(interaction, accion, usuario, tipo, motivo)
        
        # Add accept command to tree
        @app_commands.command(name="aceptar", description="Acepta la solicitud de un usuario y le asigna un rol")
        @app_commands.describe(
            usuario="Usuario cuya solicitud será aceptada",
            rol="Rol que se le asignará al usuario"
        )
        async def accept_slash_command(
            interaction: discord.Interaction,
            usuario: discord.Member,
            rol: discord.Role
        ):
            await self.accept_command(interaction, usuario, rol)
        
        # Add deny command to tree
        @app_commands.command(name="denegar", description="Deniega la solicitud de un usuario y lo banea del servidor")
        @app_commands.describe(
            usuario="Usuario cuya solicitud será denegada"
        )
        async def deny_slash_command(
            interaction: discord.Interaction,
            usuario: discord.Member
        ):
            await self.deny_command(interaction, usuario)
        
        # Add suggest command group
        suggest_group = app_commands.Group(name="suggest", description="Sistema de sugerencias")
        
        @suggest_group.command(name="create", description="Crear una nueva sugerencia")
        @app_commands.describe(sugerencia="Tu sugerencia para el servidor")
        async def suggest_create_command(interaction: discord.Interaction, sugerencia: str):
            await self.suggest_create(interaction, sugerencia)
        
        @suggest_group.command(name="accept", description="Aceptar una sugerencia (Solo administradores)")
        @app_commands.describe(message_id="ID del mensaje de la sugerencia")
        async def suggest_accept_command(interaction: discord.Interaction, message_id: str):
            await self.suggest_accept(interaction, message_id)
        
        @suggest_group.command(name="deny", description="Rechazar una sugerencia (Solo administradores)")
        @app_commands.describe(message_id="ID del mensaje de la sugerencia")
        async def suggest_deny_command(interaction: discord.Interaction, message_id: str):
            await self.suggest_deny(interaction, message_id)
        
        self.tree.add_command(suggest_group)
        
        # Add ticket command group
        ticket_group = app_commands.Group(name="ticket", description="Sistema de tickets")
        
        @ticket_group.command(name="crear", description="Crear un nuevo ticket")
        @app_commands.describe(motivo="Motivo del ticket (opcional)")
        async def ticket_create_command(interaction: discord.Interaction, motivo: str = "Sin motivo especificado"):
            await self.create_ticket(interaction, motivo)
        
        @ticket_group.command(name="cerrar", description="Cerrar un ticket (Solo administradores)")
        async def ticket_close_command(interaction: discord.Interaction):
            await self.close_ticket(interaction)
        
        @ticket_group.command(name="add", description="Añadir usuario a un ticket (Solo administradores)")
        @app_commands.describe(usuario="Usuario a añadir al ticket")
        async def ticket_add_command(interaction: discord.Interaction, usuario: discord.Member):
            await self.add_user_to_ticket(interaction, usuario)
        
        self.tree.add_command(ticket_group)
        self.tree.add_command(strike_slash_command)
        self.tree.add_command(accept_slash_command)
        self.tree.add_command(deny_slash_command)
    
    def load_counters(self):
        """Load message counters from file"""
        try:
            if os.path.exists(self.counter_file):
                with open(self.counter_file, 'r') as f:
                    data = json.load(f)
                    # Convert string keys back to integers
                    self.message_counters = {int(k): v for k, v in data.items()}
                self.logger.info(f"Loaded message counters: {self.message_counters}")
            else:
                self.message_counters = {}
                self.logger.info("No existing counter file found, starting fresh")
        except Exception as e:
            self.logger.error(f"Error loading counters: {e}")
            self.message_counters = {}
    
    def save_counters(self):
        """Save message counters to file"""
        try:
            with open(self.counter_file, 'w') as f:
                # Convert integer keys to strings for JSON serialization
                data = {str(k): v for k, v in self.message_counters.items()}
                json.dump(data, f)
            self.logger.debug("Message counters saved")
        except Exception as e:
            self.logger.error(f"Error saving counters: {e}")
    
    async def on_ready(self):
        """Called when the bot is ready and connected to Discord"""
        self.logger.info(f'{self.user} has connected to Discord!')
        self.logger.info(f'Bot is monitoring channel ID: {self.config.CHANNEL_ID}')
        self.logger.info(f'Reminder threshold: {self.config.MESSAGE_THRESHOLD} messages')
        
        # List all accessible channels for debugging
        self.logger.info("Available channels:")
        for guild in self.guilds:
            self.logger.info(f'Guild: {guild.name} (ID: {guild.id})')
            for channel in guild.text_channels:
                self.logger.info(f'  - #{channel.name} (ID: {channel.id})')
        
        # Validate that the channels exist and are accessible
        channel = self.get_channel(self.config.CHANNEL_ID)
        welcome_channel = self.get_channel(self.welcome_channel_id)
        
        if channel:
            self.logger.info(f'Successfully found suggestion channel: {channel.name} in {channel.guild.name}')
        else:
            self.logger.error(f'Could not find suggestion channel with ID: {self.config.CHANNEL_ID}')
            
        if welcome_channel:
            self.logger.info(f'Successfully found welcome channel: {welcome_channel.name} in {welcome_channel.guild.name}')
        else:
            self.logger.error(f'Could not find welcome channel with ID: {self.welcome_channel_id}')
            
        if channel and welcome_channel:
            self.logger.info('Bot is ready to monitor messages and welcome users!')
            self.logger.warning('Note: Welcome/goodbye messages require Server Members Intent to be enabled in Discord Developer Portal')
            self.logger.info('Use "/test bienvenida" and "/test despedida" commands to test welcome functionality')
        elif channel:
            self.logger.info('Bot is ready to monitor messages (welcome channel not found)!')
        else:
            self.logger.error('Please check channel configuration')
            
        # Sincronizar comandos slash
        try:
            synced = await self.tree.sync()
            self.logger.info(f'Sincronizados {len(synced)} comandos slash')
            for cmd in synced:
                self.logger.info(f'  - {cmd.name}: {cmd.description}')
        except Exception as e:
            self.logger.error(f'Error sincronizando comandos slash: {e}')
            import traceback
            self.logger.error(traceback.format_exc())
    

    
    async def send_reminder(self, channel):
        """Send the reminder message to the specified channel"""
        try:
            await channel.send(self.config.REMINDER_MESSAGE)
            self.logger.info(f'Reminder sent to channel: {channel.name}')
        except discord.errors.Forbidden:
            self.logger.error(f'No permission to send messages in channel: {channel.name}')
        except discord.errors.HTTPException as e:
            self.logger.error(f'HTTP error while sending message: {e}')
        except Exception as e:
            self.logger.error(f'Unexpected error while sending reminder: {e}')
    
    async def on_error(self, event, *args, **kwargs):
        """Handle bot errors"""
        self.logger.error(f'Bot error in event {event}', exc_info=True)
    
    async def on_disconnect(self):
        """Called when the bot disconnects from Discord"""
        self.logger.warning('Bot disconnected from Discord')
    
    async def on_resumed(self):
        """Called when the bot resumes connection to Discord"""
        self.logger.info('Bot resumed connection to Discord')
    
    def reset_counter(self, channel_id: Optional[int] = None):
        """Reset message counter for a specific channel or all channels"""
        if channel_id:
            if channel_id in self.message_counters:
                old_count = self.message_counters[channel_id]
                self.message_counters[channel_id] = 0
                self.save_counters()
                self.logger.info(f'Reset counter for channel {channel_id} (was {old_count})')
            else:
                self.logger.warning(f'No counter found for channel {channel_id}')
        else:
            # Reset all counters
            old_counters = self.message_counters.copy()
            self.message_counters.clear()
            self.save_counters()
            self.logger.info(f'Reset all counters (were {old_counters})')
    
    def get_counter(self, channel_id: int) -> int:
        """Get current message counter for a channel"""
        return self.message_counters.get(channel_id, 0)
    
    @commands.Cog.listener()
    async def on_member_join(self, member):
        """Called when a user joins the server - requires Server Members Intent"""
        try:
            welcome_channel = self.get_channel(self.welcome_channel_id)
            if welcome_channel:
                welcome_message = f"👋 ¡Bienvenido/a, {member.mention}! Gracias por unirte a nuestro servidor."
                await welcome_channel.send(welcome_message)
                self.logger.info(f'Welcome message sent for {member.name} ({member.id})')
            else:
                self.logger.error(f'Welcome channel not found (ID: {self.welcome_channel_id})')
        except discord.errors.Forbidden:
            self.logger.error(f'No permission to send welcome message in channel: {self.welcome_channel_id}')
        except Exception as e:
            self.logger.error(f'Error sending welcome message: {e}')
    
    @commands.Cog.listener()
    async def on_member_remove(self, member):
        """Called when a user leaves the server - requires Server Members Intent"""
        try:
            welcome_channel = self.get_channel(self.welcome_channel_id)
            if welcome_channel:
                goodbye_message = f"👋 {member.display_name} ha salido del servidor. ¡Hasta pronto!"
                await welcome_channel.send(goodbye_message)
                self.logger.info(f'Goodbye message sent for {member.name} ({member.id})')
            else:
                self.logger.error(f'Welcome channel not found (ID: {self.welcome_channel_id})')
        except discord.errors.Forbidden:
            self.logger.error(f'No permission to send goodbye message in channel: {self.welcome_channel_id}')
        except Exception as e:
            self.logger.error(f'Error sending goodbye message: {e}')
    
    async def on_message(self, message):
        """Handle both message counting and simple text-based commands"""
        
        # Log all messages for debugging
        channel_name = getattr(message.channel, 'name', 'DM')
        self.logger.info(f'Received message: "{message.content}" from {message.author.name} in #{channel_name}')
        
        # Ignore messages from bots (including this bot)
        if message.author.bot:
            return
        
        # Check for test commands first
        content = message.content.lower().strip()
        if content == "/test bienvenida" or content == "test bienvenida":
            self.logger.info(f'Test bienvenida command from {message.author.name}')
            welcome_channel = self.get_channel(self.welcome_channel_id)
            if welcome_channel:
                welcome_message = f"👋 ¡Bienvenido/a, {message.author.mention}! Gracias por unirte a nuestro servidor."
                await welcome_channel.send(welcome_message)
                await message.channel.send("Mensaje de bienvenida enviado.")
                self.logger.info(f'Test welcome message sent successfully')
            return
            
        if content == "/test despedida" or content == "test despedida":
            self.logger.info(f'Test despedida command from {message.author.name}')
            welcome_channel = self.get_channel(self.welcome_channel_id)
            if welcome_channel:
                goodbye_message = f"👋 {message.author.display_name} ha salido del servidor. ¡Hasta pronto!"
                await welcome_channel.send(goodbye_message)
                await message.channel.send("Mensaje de despedida enviado.")
                self.logger.info(f'Test goodbye message sent successfully')
            return

        # Check if message is in suggestions channel and restrict text messages
        if message.channel.id == self.config.CHANNEL_ID:
            # Check if message starts with slash command
            if message.content.startswith('/'):
                # Allow slash commands for everyone
                pass
            else:
                # Check if user has required role for text messages
                if not self.has_required_role(message.author):
                    # Delete the message and send warning
                    await message.delete()
                    warning_embed = discord.Embed(
                        title="⚠️ Mensaje no permitido",
                        description=f"{message.author.mention}, solo puedes usar comandos en este canal.\n\nUsa `/suggest create` para hacer una sugerencia.",
                        color=0xff9900
                    )
                    warning_msg = await message.channel.send(embed=warning_embed)
                    
                    # Delete warning after 10 seconds
                    await asyncio.sleep(10)
                    try:
                        await warning_msg.delete()
                    except:
                        pass
                    
                    self.logger.info(f"Deleted text message from {message.author.name} in suggestions channel")
                    return

            try:
                # Get current counter for this channel
                current_count = self.message_counters.get(message.channel.id, 0)
                current_count += 1
                
                self.logger.debug(f'Message #{current_count} in channel {message.channel.name}')
                
                # Update counter
                self.message_counters[message.channel.id] = current_count
                
                # Check if we should send a reminder
                if current_count >= self.config.MESSAGE_THRESHOLD:
                    await self.send_reminder(message.channel)
                    # Reset counter
                    self.message_counters[message.channel.id] = 0
                    self.logger.info(f'Sent reminder and reset counter for channel {message.channel.name}')
                
                # Save counters to file
                self.save_counters()
                
            except Exception as e:
                self.logger.error(f'Error processing message: {e}')
            
            return
        
        # Restricciones en canales de ticket - solo admins pueden responder
        if hasattr(message.channel, 'name') and message.channel.name.startswith("🎟️-ticket-"):
            if not message.author.bot and not self.has_required_role(message.author):
                # Verificar si es el creador del ticket
                tickets_data = self.load_tickets()
                channel_id = str(message.channel.id)
                
                if channel_id in tickets_data:
                    ticket_info = tickets_data[channel_id]
                    if message.author.id != ticket_info['creator_id']:
                        # No es admin ni creador, eliminar mensaje
                        await message.delete()
                        warning_embed = discord.Embed(
                            title="⚠️ Solo administradores pueden responder",
                            description=f"{message.author.mention}, solo los administradores pueden responder en los tickets.",
                            color=0xff9900
                        )
                        warning_msg = await message.channel.send(embed=warning_embed)
                        
                        # Eliminar advertencia después de 10 segundos
                        await asyncio.sleep(10)
                        try:
                            await warning_msg.delete()
                        except:
                            pass
                        
                        self.logger.info(f"Deleted message from {message.author.name} in ticket channel")
                        return

        # Count normal text messages (not commands) in any channel for help message system
        if not message.content.startswith('/') and not message.author.bot and hasattr(message.channel, 'name'):
            self.help_message_counter += 1
            
            # Check if we should send help message
            if self.help_message_counter >= self.help_message_threshold:
                self.help_message_counter = 0  # Reset counter
                
                help_message = (
                    "🆘 __***¿Te hace falta ayuda al momento?***__\n"
                    "Escribe por aquí y te echamos una mano rápido entre todos. 👇"
                )
                await message.channel.send(help_message)
                self.logger.info(f"Help message sent in channel {message.channel.name}")
            
        # Process commands if they exist
        await self.process_commands(message)
    
    # ============ STRIKES SYSTEM ============
    
    def load_strikes(self) -> dict:
        """Cargar strikes desde el archivo JSON"""
        try:
            if os.path.exists(self.strikes_file):
                with open(self.strikes_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            return {}
        except Exception as e:
            self.logger.error(f"Error cargando strikes: {e}")
            return {}
    
    def save_strikes(self, strikes_data: dict):
        """Guardar strikes en el archivo JSON"""
        try:
            with open(self.strikes_file, 'w', encoding='utf-8') as f:
                json.dump(strikes_data, f, indent=2, ensure_ascii=False)
        except Exception as e:
            self.logger.error(f"Error guardando strikes: {e}")
    
    def has_required_role(self, member: discord.Member) -> bool:
        """Verificar si el usuario tiene rol de Gerente o Subgerente"""
        required_roles = ['Gerente', 'Subgerente', '👑 Gerente', '👑 Subgerente']
        user_roles = [role.name for role in member.roles]
        self.logger.info(f'Checking roles for {member.name}: {user_roles}')
        self.logger.info(f'Required roles: {required_roles}')
        has_role = any(role in user_roles for role in required_roles)
        self.logger.info(f'Has required role: {has_role}')
        return has_role
    
    def count_strikes(self, user_strikes: list) -> dict:
        """Contar strikes por tipo"""
        count = {"leve": 0, "moderado": 0, "grave": 0}
        for strike in user_strikes:
            count[strike["tipo"]] += 1
        return count
    
    def check_strike_limits(self, strikes_count: dict) -> Optional[str]:
        """Verificar si se superan los límites de strikes"""
        leve = strikes_count["leve"]
        moderado = strikes_count["moderado"]
        grave = strikes_count["grave"]
        
        # Verificar límites críticos (posible despido)
        if grave >= 1:
            return "🚨 **POSIBLE DESPIDO DIRECTO** (1+ strikes graves)"
        elif leve >= 5:
            return "🚨 **POSIBLE DESPIDO** (5+ strikes leves)"
        elif moderado >= 3:
            return "🚨 **POSIBLE DESPIDO** (3+ strikes moderados)"
        
        # Verificar advertencias
        elif leve >= 3:
            return "⚠️ **ADVERTENCIA** (3+ strikes leves)"
        elif moderado >= 2:
            return "⚠️ **ADVERTENCIA** (2+ strikes moderados)"
        
        return None
    
    async def strike_command(
        self,
        interaction: discord.Interaction,
        accion: Literal["add", "check", "remove"],
        usuario: discord.Member,
        tipo: Optional[Literal["leve", "moderado", "grave"]] = None,
        motivo: Optional[str] = None
    ):
        """Comando principal para manejar strikes"""
        
        # Verificar permisos
        if not self.has_required_role(interaction.user):
            embed = discord.Embed(
                title="❌ Sin permisos",
                description="Solo usuarios con rol `Gerente` o `Subgerente` pueden usar este comando.",
                color=discord.Color.red()
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        
        # Cargar datos de strikes
        strikes_data = self.load_strikes()
        user_id = str(usuario.id)
        
        if accion == "add":
            await self._add_strike(interaction, strikes_data, user_id, usuario, tipo, motivo)
        elif accion == "check":
            await self._check_strikes(interaction, strikes_data, user_id, usuario)
        elif accion == "remove":
            await self._remove_strike(interaction, strikes_data, user_id, usuario)
    
    async def _add_strike(self, interaction, strikes_data, user_id, usuario, tipo, motivo):
        """Agregar un strike a un usuario"""
        if not tipo or not motivo:
            embed = discord.Embed(
                title="❌ Error",
                description="Para agregar un strike debes especificar `tipo` y `motivo`.",
                color=discord.Color.red()
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        
        # Crear entrada si no existe
        if user_id not in strikes_data:
            strikes_data[user_id] = []
        
        # Agregar nuevo strike
        new_strike = {
            "tipo": tipo,
            "motivo": motivo,
            "fecha": datetime.now().strftime("%Y-%m-%d"),
            "autor": interaction.user.display_name
        }
        
        strikes_data[user_id].append(new_strike)
        self.save_strikes(strikes_data)
        
        # Crear embed de confirmación
        embed = discord.Embed(
            title="✅ Strike agregado",
            description=f"Strike **{tipo}** agregado a {usuario.mention}",
            color=discord.Color.green()
        )
        embed.add_field(name="Motivo", value=motivo, inline=False)
        embed.add_field(name="Fecha", value=new_strike["fecha"], inline=True)
        embed.add_field(name="Por", value=interaction.user.mention, inline=True)
        
        # Calcular totales para verificar límites
        strikes_count = self.count_strikes(strikes_data[user_id])
        warning_message = self.check_strike_limits(strikes_count)
        
        if warning_message:
            embed.add_field(name="⚠️ Advertencia", value=warning_message, inline=False)
        
        await interaction.response.send_message(embed=embed)
        self.logger.info(f'Strike {tipo} agregado a {usuario.name} por {interaction.user.name}: {motivo}')
    
    async def _check_strikes(self, interaction, strikes_data, user_id, usuario):
        """Mostrar strikes de un usuario"""
        if user_id not in strikes_data or not strikes_data[user_id]:
            embed = discord.Embed(
                title="📋 Historial de strikes",
                description=f"{usuario.mention} no tiene strikes registrados.",
                color=discord.Color.blue()
            )
            await interaction.response.send_message(embed=embed)
            return
        
        user_strikes = strikes_data[user_id]
        strikes_count = self.count_strikes(user_strikes)
        
        # Crear embed con información
        embed = discord.Embed(
            title="📋 Historial de strikes",
            description=f"Strikes de {usuario.mention}",
            color=discord.Color.blue()
        )
        
        # Mostrar resumen por tipo
        embed.add_field(
            name="📊 Resumen",
            value=f"🟢 Leves: {strikes_count['leve']}\n🟡 Moderados: {strikes_count['moderado']}\n🔴 Graves: {strikes_count['grave']}",
            inline=True
        )
        
        # Mostrar advertencias si aplica
        warning_message = self.check_strike_limits(strikes_count)
        if warning_message:
            embed.add_field(name="⚠️ Estado", value=warning_message, inline=True)
        else:
            embed.add_field(name="✅ Estado", value="Dentro de los límites", inline=True)
        
        # Mostrar últimos 5 strikes
        recent_strikes = user_strikes[-5:]  # Últimos 5
        if recent_strikes:
            strikes_text = ""
            for strike in reversed(recent_strikes):  # Más recientes primero
                emoji = {"leve": "🟢", "moderado": "🟡", "grave": "🔴"}[strike["tipo"]]
                strikes_text += f"{emoji} **{strike['tipo'].title()}** - {strike['motivo']}\n*{strike['fecha']} por {strike.get('autor', 'N/A')}*\n\n"
            
            embed.add_field(
                name="📝 Últimos strikes",
                value=strikes_text[:1024],  # Límite de Discord
                inline=False
            )
        
        await interaction.response.send_message(embed=embed)
    
    async def _remove_strike(self, interaction, strikes_data, user_id, usuario):
        """Remover el último strike de un usuario"""
        if user_id not in strikes_data or not strikes_data[user_id]:
            embed = discord.Embed(
                title="❌ Error",
                description=f"{usuario.mention} no tiene strikes para remover.",
                color=discord.Color.red()
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        
        # Remover último strike
        removed_strike = strikes_data[user_id].pop()
        self.save_strikes(strikes_data)
        
        # Crear embed de confirmación
        embed = discord.Embed(
            title="🗑️ Strike removido",
            description=f"Se removió el último strike de {usuario.mention}",
            color=discord.Color.orange()
        )
        embed.add_field(name="Strike removido", value=f"**{removed_strike['tipo'].title()}**: {removed_strike['motivo']}", inline=False)
        embed.add_field(name="Fecha original", value=removed_strike['fecha'], inline=True)
        embed.add_field(name="Removido por", value=interaction.user.mention, inline=True)
        
        await interaction.response.send_message(embed=embed)
        self.logger.info(f'Strike removido de {usuario.name} por {interaction.user.name}')
    
    # ============ ACCEPT COMMAND ============
    
    async def accept_command(
        self,
        interaction: discord.Interaction,
        usuario: discord.Member,
        rol: discord.Role
    ):
        """Comando para aceptar solicitudes y asignar roles"""
        
        # Verificar permisos
        if not self.has_required_role(interaction.user):
            embed = discord.Embed(
                title="❌ Sin permisos",
                description="Solo usuarios con rol `Gerente` o `Subgerente` pueden usar este comando.",
                color=discord.Color.red()
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        
        try:
            # Asignar el rol al usuario
            await usuario.add_roles(rol)
            
            # Crear embed de confirmación
            embed = discord.Embed(
                title="✅ Solicitud Aceptada",
                description=f"✨ {usuario.mention}, tu solicitud ha sido aceptada.\nNos ha parecido muy interesante tu propuesta.\nA partir de ahora formas parte del equipo como {rol.mention}. ¡Bienvenido/a! 🎉",
                color=discord.Color.green()
            )
            embed.add_field(name="Usuario", value=usuario.mention, inline=True)
            embed.add_field(name="Rol Asignado", value=rol.mention, inline=True)
            embed.add_field(name="Aceptado por", value=interaction.user.mention, inline=True)
            
            await interaction.response.send_message(embed=embed)
            self.logger.info(f'Solicitud aceptada: {usuario.name} recibió rol {rol.name} por {interaction.user.name}')
            
        except discord.Forbidden:
            embed = discord.Embed(
                title="❌ Error de permisos",
                description=f"No tengo permisos para asignar el rol **{rol.name}**.\n\n**Solución:**\n1. Ve a Configuración del Servidor → Roles\n2. Arrastra mi rol por encima del rol **{rol.name}**\n3. Intenta el comando nuevamente",
                color=discord.Color.red()
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            self.logger.error(f'Error asignando rol {rol.name} a {usuario.name}: Sin permisos - El rol del bot debe estar por encima de {rol.name}')
            
        except Exception as e:
            embed = discord.Embed(
                title="❌ Error",
                description="Ocurrió un error al asignar el rol. Inténtalo de nuevo.",
                color=discord.Color.red()
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            self.logger.error(f'Error asignando rol {rol.name} a {usuario.name}: {e}')
    
    # ============ DENY COMMAND ============
    
    async def deny_command(
        self,
        interaction: discord.Interaction,
        usuario: discord.Member
    ):
        """Comando para denegar solicitudes, notificar por DM y banear usuario"""
        
        # Verificar permisos
        if not self.has_required_role(interaction.user):
            embed = discord.Embed(
                title="❌ Sin permisos",
                description="Solo usuarios con rol `Gerente` o `Subgerente` pueden usar este comando.",
                color=discord.Color.red()
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        
        # Mensaje de denegación
        deny_message = f"❌ {usuario.mention}, tu solicitud ha sido denegada.\nTras revisarla, hemos decidido no aceptarla en esta ocasión.\nTe animamos a seguir participando y a volver a intentarlo en el futuro. ¡Gracias por tu interés!"
        
        try:
            # Enviar mensaje por DM primero
            try:
                dm_embed = discord.Embed(
                    title="❌ Solicitud Denegada",
                    description=deny_message,
                    color=discord.Color.red()
                )
                await usuario.send(embed=dm_embed)
                dm_sent = True
                self.logger.info(f'Mensaje de denegación enviado por DM a {usuario.name}')
            except discord.Forbidden:
                dm_sent = False
                self.logger.warning(f'No se pudo enviar DM a {usuario.name} - DMs cerrados')
            
            # Banear al usuario
            await usuario.ban(reason=f"Solicitud denegada por {interaction.user.name}")
            
            # Crear embed de confirmación para el canal
            embed = discord.Embed(
                title="❌ Solicitud Denegada",
                description=deny_message,
                color=discord.Color.red()
            )
            embed.add_field(name="Usuario", value=usuario.mention, inline=True)
            embed.add_field(name="Denegado por", value=interaction.user.mention, inline=True)
            
            if dm_sent:
                embed.add_field(name="Notificación", value="✅ Usuario notificado por DM", inline=True)
            else:
                embed.add_field(name="Notificación", value="⚠️ No se pudo enviar DM (bloqueado)", inline=True)
            
            embed.add_field(name="Estado", value="🔨 Usuario baneado del servidor", inline=False)
            
            await interaction.response.send_message(embed=embed)
            self.logger.info(f'Solicitud denegada: {usuario.name} baneado por {interaction.user.name}')
            
        except discord.Forbidden:
            embed = discord.Embed(
                title="❌ Error de permisos",
                description="No tengo permisos para banear usuarios. Verifica que mi rol tenga permisos de 'Banear miembros'.",
                color=discord.Color.red()
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            self.logger.error(f'Error baneando a {usuario.name}: Sin permisos')
            
        except Exception as e:
            embed = discord.Embed(
                title="❌ Error",
                description="Ocurrió un error al procesar la denegación. Inténtalo de nuevo.",
                color=discord.Color.red()
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            self.logger.error(f'Error denegando solicitud de {usuario.name}: {e}')
    
    # ===== SUGGESTIONS SYSTEM =====
    
    def load_suggestions(self) -> dict:
        """Cargar sugerencias desde el archivo JSON"""
        try:
            if os.path.exists(self.suggestions_file):
                with open(self.suggestions_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            return {}
        except Exception as e:
            self.logger.error(f"Error loading suggestions: {e}")
            return {}
    
    def save_suggestions(self, suggestions_data: dict):
        """Guardar sugerencias en el archivo JSON"""
        try:
            with open(self.suggestions_file, 'w', encoding='utf-8') as f:
                json.dump(suggestions_data, f, indent=2, ensure_ascii=False)
        except Exception as e:
            self.logger.error(f"Error saving suggestions: {e}")
    
    async def suggest_create(self, interaction: discord.Interaction, sugerencia: str):
        """Crear una nueva sugerencia"""
        try:
            # Crear embed para la sugerencia
            embed = discord.Embed(
                title="💡 Nueva Sugerencia",
                description=sugerencia,
                color=0x3498db,  # Azul
                timestamp=datetime.now()
            )
            embed.set_author(
                name=interaction.user.display_name,
                icon_url=interaction.user.display_avatar.url
            )
            embed.set_footer(text="Reacciona con 👍 o 👎 para votar • Estado: Pendiente")
            
            # Responder al usuario
            await interaction.response.send_message("✅ Tu sugerencia ha sido enviada correctamente!", ephemeral=True)
            
            # Enviar la sugerencia al canal
            message = await interaction.followup.send(embed=embed)
            
            # Añadir reacciones automáticamente
            await message.add_reaction("👍")
            await message.add_reaction("👎")
            
            # Guardar la sugerencia en el archivo JSON
            suggestions_data = self.load_suggestions()
            suggestions_data[str(message.id)] = {
                "user_id": interaction.user.id,
                "user_name": interaction.user.display_name,
                "suggestion": sugerencia,
                "status": "pending",
                "created_at": datetime.now().isoformat(),
                "channel_id": interaction.channel.id
            }
            self.save_suggestions(suggestions_data)
            
            # Incrementar contador de comandos de sugerencias
            self.suggestions_command_counter += 1
            
            # Verificar si es momento de enviar mensaje recordatorio
            if self.suggestions_command_counter >= self.suggestions_command_threshold:
                self.suggestions_command_counter = 0  # Resetear contador
                
                # Enviar mensaje recordatorio al canal de sugerencias
                suggestion_channel = self.get_channel(self.config.CHANNEL_ID)
                if suggestion_channel:
                    reminder_message = (
                        "💬 __***¿Tienes alguna sugerencia?***__\n"
                        "Puedes enviar ideas tanto 🧠 **OOC**, 🎭 **IC** como del 🌐 **Discord**.\n"
                        "Usa el comando 👉 `/suggest create` para hacer tu propuesta."
                    )
                    await suggestion_channel.send(reminder_message)
                    self.logger.info("Mensaje recordatorio de sugerencias enviado")
            
            self.logger.info(f"Nueva sugerencia creada por {interaction.user}: {sugerencia[:50]}...")
            
        except Exception as e:
            await interaction.followup.send(f"❌ Error al crear la sugerencia: {str(e)}", ephemeral=True)
            self.logger.error(f"Error in suggest_create: {e}")
    
    async def suggest_accept(self, interaction: discord.Interaction, message_id: str):
        """Aceptar una sugerencia (Solo administradores)"""
        try:
            # Verificar permisos
            if not self.has_required_role(interaction.user):
                await interaction.response.send_message("❌ No tienes permisos para usar este comando.", ephemeral=True)
                return
            
            # Cargar sugerencias
            suggestions_data = self.load_suggestions()
            
            if message_id not in suggestions_data:
                await interaction.response.send_message("❌ No se encontró una sugerencia con ese ID.", ephemeral=True)
                return
            
            # Obtener el mensaje original
            try:
                channel = self.get_channel(suggestions_data[message_id]["channel_id"])
                message = await channel.fetch_message(int(message_id))
            except:
                await interaction.response.send_message("❌ No se pudo encontrar el mensaje original.", ephemeral=True)
                return
            
            # Contar reacciones antes de mover
            upvotes = 0
            downvotes = 0
            for reaction in message.reactions:
                if str(reaction.emoji) == "👍":
                    upvotes = reaction.count - 1  # Restamos 1 porque el bot también reaccionó
                elif str(reaction.emoji) == "👎":
                    downvotes = reaction.count - 1  # Restamos 1 porque el bot también reaccionó
            
            # Actualizar el embed
            embed = message.embeds[0]
            embed.color = 0x2ecc71  # Verde
            embed.set_footer(text="Estado: ✅ ACEPTADA")
            embed.add_field(name="Revisado por", value=f"<@{interaction.user.id}>", inline=True)
            embed.add_field(name="Fecha de revisión", value=f"<t:{int(datetime.now().timestamp())}:R>", inline=True)
            embed.add_field(name="Votos", value=f"👍 {upvotes} | 👎 {downvotes}", inline=True)
            
            # Mover la sugerencia al canal de resultados
            results_channel = self.get_channel(self.suggestions_results_channel_id)
            if results_channel:
                # Enviar al canal de resultados
                await results_channel.send(embed=embed)
                
                # Eliminar el mensaje original
                await message.delete()
                
                self.logger.info(f"Sugerencia movida a canal de resultados")
            else:
                # Si no se encuentra el canal de resultados, solo actualizar el mensaje original
                await message.edit(embed=embed)
                self.logger.warning("Canal de resultados no encontrado, manteniendo mensaje original")
            
            # Actualizar datos
            suggestions_data[message_id]["status"] = "accepted"
            suggestions_data[message_id]["reviewed_by"] = interaction.user.id
            suggestions_data[message_id]["reviewed_at"] = datetime.now().isoformat()
            suggestions_data[message_id]["moved_to_results"] = True
            suggestions_data[message_id]["final_votes"] = {"upvotes": upvotes, "downvotes": downvotes}
            self.save_suggestions(suggestions_data)
            
            await interaction.response.send_message(f"✅ Sugerencia aceptada y movida a resultados!", ephemeral=True)
            self.logger.info(f"Sugerencia {message_id} aceptada por {interaction.user}")
            
        except Exception as e:
            await interaction.response.send_message(f"❌ Error al aceptar la sugerencia: {str(e)}", ephemeral=True)
            self.logger.error(f"Error in suggest_accept: {e}")
    
    async def suggest_deny(self, interaction: discord.Interaction, message_id: str):
        """Rechazar una sugerencia (Solo administradores)"""
        try:
            # Verificar permisos
            if not self.has_required_role(interaction.user):
                await interaction.response.send_message("❌ No tienes permisos para usar este comando.", ephemeral=True)
                return
            
            # Cargar sugerencias
            suggestions_data = self.load_suggestions()
            
            if message_id not in suggestions_data:
                await interaction.response.send_message("❌ No se encontró una sugerencia con ese ID.", ephemeral=True)
                return
            
            # Obtener el mensaje original
            try:
                channel = self.get_channel(suggestions_data[message_id]["channel_id"])
                message = await channel.fetch_message(int(message_id))
            except:
                await interaction.response.send_message("❌ No se pudo encontrar el mensaje original.", ephemeral=True)
                return
            
            # Contar reacciones antes de mover
            upvotes = 0
            downvotes = 0
            for reaction in message.reactions:
                if str(reaction.emoji) == "👍":
                    upvotes = reaction.count - 1  # Restamos 1 porque el bot también reaccionó
                elif str(reaction.emoji) == "👎":
                    downvotes = reaction.count - 1  # Restamos 1 porque el bot también reaccionó
            
            # Actualizar el embed
            embed = message.embeds[0]
            embed.color = 0xe74c3c  # Rojo
            embed.set_footer(text="Estado: ❌ RECHAZADA")
            embed.add_field(name="Revisado por", value=f"<@{interaction.user.id}>", inline=True)
            embed.add_field(name="Fecha de revisión", value=f"<t:{int(datetime.now().timestamp())}:R>", inline=True)
            embed.add_field(name="Votos", value=f"👍 {upvotes} | 👎 {downvotes}", inline=True)
            
            # Mover la sugerencia al canal de resultados
            results_channel = self.get_channel(self.suggestions_results_channel_id)
            if results_channel:
                # Enviar al canal de resultados
                await results_channel.send(embed=embed)
                
                # Eliminar el mensaje original
                await message.delete()
                
                self.logger.info(f"Sugerencia movida a canal de resultados")
            else:
                # Si no se encuentra el canal de resultados, solo actualizar el mensaje original
                await message.edit(embed=embed)
                self.logger.warning("Canal de resultados no encontrado, manteniendo mensaje original")
            
            # Actualizar datos
            suggestions_data[message_id]["status"] = "denied"
            suggestions_data[message_id]["reviewed_by"] = interaction.user.id
            suggestions_data[message_id]["reviewed_at"] = datetime.now().isoformat()
            suggestions_data[message_id]["moved_to_results"] = True
            suggestions_data[message_id]["final_votes"] = {"upvotes": upvotes, "downvotes": downvotes}
            self.save_suggestions(suggestions_data)
            
            await interaction.response.send_message(f"❌ Sugerencia rechazada y movida a resultados!", ephemeral=True)
            self.logger.info(f"Sugerencia {message_id} rechazada por {interaction.user}")
            
        except Exception as e:
            await interaction.response.send_message(f"❌ Error al rechazar la sugerencia: {str(e)}", ephemeral=True)
            self.logger.error(f"Error in suggest_deny: {e}")

    # ==================== SISTEMA DE TICKETS ====================
    
    def load_tickets(self) -> dict:
        """Cargar tickets desde el archivo JSON"""
        try:
            if os.path.exists(self.tickets_file):
                with open(self.tickets_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    # Cargar contador de tickets
                    self.ticket_counter = data.get('counter', 0)
                    return data.get('tickets', {})
            return {}
        except Exception as e:
            self.logger.error(f"Error loading tickets: {e}")
            return {}

    def save_tickets(self, tickets_data: dict):
        """Guardar tickets en el archivo JSON"""
        try:
            data = {
                'counter': self.ticket_counter,
                'tickets': tickets_data
            }
            with open(self.tickets_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
        except Exception as e:
            self.logger.error(f"Error saving tickets: {e}")

    async def create_ticket(self, interaction: discord.Interaction, motivo: str):
        """Crear un nuevo ticket"""
        try:
            # Incrementar contador
            self.ticket_counter += 1
            ticket_number = self.ticket_counter
            
            # Crear nombre del canal
            channel_name = f"🎟️-ticket-{ticket_number:04d}"
            
            # Configurar permisos del canal
            overwrites = {
                interaction.guild.default_role: discord.PermissionOverwrite(read_messages=False),
                interaction.user: discord.PermissionOverwrite(
                    read_messages=True,
                    send_messages=True,
                    read_message_history=True
                ),
                interaction.guild.me: discord.PermissionOverwrite(
                    read_messages=True,
                    send_messages=True,
                    manage_channels=True,
                    read_message_history=True
                )
            }
            
            # Añadir permisos para administradores
            for role in interaction.guild.roles:
                if role.name in ["👑 Gerente", "👑 Subgerente", "Gerente", "Subgerente"]:
                    overwrites[role] = discord.PermissionOverwrite(
                        read_messages=True,
                        send_messages=True,
                        manage_channels=True,
                        read_message_history=True
                    )
            
            # Crear canal al inicio de la lista (position=0)
            ticket_channel = await interaction.guild.create_text_channel(
                channel_name,
                overwrites=overwrites,
                position=0,
                topic=f"Ticket #{ticket_number:04d} - Creado por {interaction.user.display_name}"
            )
            
            # Guardar información del ticket
            tickets_data = self.load_tickets()
            tickets_data[str(ticket_channel.id)] = {
                'number': ticket_number,
                'creator_id': interaction.user.id,
                'creator_name': interaction.user.display_name,
                'motivo': motivo,
                'created_at': datetime.now().isoformat(),
                'status': 'open',
                'messages': []
            }
            self.save_tickets(tickets_data)
            
            # Crear embed de bienvenida
            embed = discord.Embed(
                title=f"🎟️ Ticket #{ticket_number:04d}",
                description=f"**Creado por:** {interaction.user.mention}\n**Motivo:** {motivo}",
                color=0x00ff00,
                timestamp=datetime.now()
            )
            embed.add_field(
                name="📋 Instrucciones",
                value=(
                    "• Solo los administradores pueden responder\n"
                    "• Los admins pueden usar `/ticket add @usuario` para añadir personas\n"
                    "• Solo los admins pueden cerrar el ticket con `/ticket cerrar`\n"
                    "• Al cerrar se generará una transcripción automática"
                ),
                inline=False
            )
            embed.set_footer(text="Ticket creado")
            
            await ticket_channel.send(embed=embed)
            
            await interaction.response.send_message(
                f"✅ Ticket #{ticket_number:04d} creado exitosamente: {ticket_channel.mention}",
                ephemeral=True
            )
            
            self.logger.info(f"Ticket #{ticket_number:04d} created by {interaction.user.name} in {ticket_channel.name}")
            
        except Exception as e:
            self.logger.error(f"Error creating ticket: {e}")
            if not interaction.response.is_done():
                await interaction.response.send_message("❌ Error al crear el ticket.", ephemeral=True)

    async def close_ticket(self, interaction: discord.Interaction):
        """Cerrar un ticket (Solo administradores)"""
        if not self.has_required_role(interaction.user):
            await interaction.response.send_message("❌ No tienes permisos para cerrar tickets.", ephemeral=True)
            return
        
        # Verificar que estamos en un canal de ticket
        if not interaction.channel.name.startswith("🎟️-ticket-"):
            await interaction.response.send_message("❌ Este comando solo se puede usar en canales de ticket.", ephemeral=True)
            return
        
        try:
            tickets_data = self.load_tickets()
            channel_id = str(interaction.channel.id)
            
            if channel_id not in tickets_data:
                await interaction.response.send_message("❌ No se encontró información de este ticket.", ephemeral=True)
                return
            
            ticket_info = tickets_data[channel_id]
            
            # Generar transcripción
            await self.generate_transcript(interaction.channel, ticket_info)
            
            # Marcar como cerrado
            ticket_info['status'] = 'closed'
            ticket_info['closed_by'] = interaction.user.id
            ticket_info['closed_at'] = datetime.now().isoformat()
            tickets_data[channel_id] = ticket_info
            self.save_tickets(tickets_data)
            
            await interaction.response.send_message("✅ Ticket cerrado. Generando transcripción...", ephemeral=True)
            
            # Esperar un poco antes de eliminar el canal
            await asyncio.sleep(3)
            await interaction.channel.delete(reason=f"Ticket cerrado por {interaction.user.display_name}")
            
            self.logger.info(f"Ticket #{ticket_info['number']:04d} closed by {interaction.user.name}")
            
        except Exception as e:
            self.logger.error(f"Error closing ticket: {e}")
            if not interaction.response.is_done():
                await interaction.response.send_message("❌ Error al cerrar el ticket.", ephemeral=True)

    async def add_user_to_ticket(self, interaction: discord.Interaction, usuario: discord.Member):
        """Añadir usuario a un ticket (Solo administradores)"""
        if not self.has_required_role(interaction.user):
            await interaction.response.send_message("❌ No tienes permisos para añadir usuarios a tickets.", ephemeral=True)
            return
        
        # Verificar que estamos en un canal de ticket
        if not interaction.channel.name.startswith("🎟️-ticket-"):
            await interaction.response.send_message("❌ Este comando solo se puede usar en canales de ticket.", ephemeral=True)
            return
        
        try:
            # Añadir permisos al usuario
            await interaction.channel.set_permissions(
                usuario,
                read_messages=True,
                send_messages=True,
                read_message_history=True
            )
            
            embed = discord.Embed(
                title="👤 Usuario Añadido",
                description=f"{usuario.mention} ha sido añadido al ticket por {interaction.user.mention}",
                color=0x0099ff,
                timestamp=datetime.now()
            )
            
            await interaction.response.send_message(embed=embed)
            self.logger.info(f"User {usuario.name} added to ticket by {interaction.user.name}")
            
        except Exception as e:
            self.logger.error(f"Error adding user to ticket: {e}")
            if not interaction.response.is_done():
                await interaction.response.send_message("❌ Error al añadir el usuario al ticket.", ephemeral=True)

    async def generate_transcript(self, channel, ticket_info):
        """Generar transcripción del ticket"""
        try:
            # Buscar canal de transcripciones
            transcript_channel = None
            for ch in channel.guild.channels:
                if ch.name == "transcript":
                    transcript_channel = ch
                    break
            
            if not transcript_channel:
                self.logger.error("Transcript channel not found")
                return
            
            # Recopilar mensajes
            messages = []
            async for message in channel.history(limit=None, oldest_first=True):
                if not message.author.bot or message.embeds:  # Incluir embeds del bot
                    timestamp = message.created_at.strftime("%d/%m/%Y %H:%M:%S")
                    content = message.content if message.content else "[Embed/Archivo]"
                    messages.append(f"[{timestamp}] {message.author.display_name}: {content}")
            
            # Crear embed de transcripción
            embed = discord.Embed(
                title=f"📄 Transcripción Ticket #{ticket_info['number']:04d}",
                color=0x2f3136,
                timestamp=datetime.now()
            )
            embed.add_field(name="Creador", value=f"<@{ticket_info['creator_id']}>", inline=True)
            embed.add_field(name="Motivo", value=ticket_info['motivo'], inline=True)
            embed.add_field(name="Cerrado por", value=f"<@{ticket_info['closed_by']}>", inline=True)
            embed.add_field(name="Creado", value=datetime.fromisoformat(ticket_info['created_at']).strftime("%d/%m/%Y %H:%M"), inline=True)
            embed.add_field(name="Cerrado", value=datetime.fromisoformat(ticket_info['closed_at']).strftime("%d/%m/%Y %H:%M"), inline=True)
            embed.add_field(name="Total Mensajes", value=str(len(messages)), inline=True)
            
            await transcript_channel.send(embed=embed)
            
            # Enviar transcripción como archivo de texto
            if messages:
                transcript_text = f"TRANSCRIPCIÓN TICKET #{ticket_info['number']:04d}\n"
                transcript_text += f"Creador: {ticket_info['creator_name']}\n"
                transcript_text += f"Motivo: {ticket_info['motivo']}\n"
                transcript_text += f"Creado: {ticket_info['created_at']}\n"
                transcript_text += f"Cerrado: {ticket_info['closed_at']}\n"
                transcript_text += "=" * 50 + "\n\n"
                transcript_text += "\n".join(messages)
                
                # Crear archivo temporal
                with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.txt', encoding='utf-8') as f:
                    f.write(transcript_text)
                    temp_path = f.name
                
                # Enviar archivo
                with open(temp_path, 'rb') as f:
                    file = discord.File(f, filename=f"ticket-{ticket_info['number']:04d}-transcript.txt")
                    await transcript_channel.send(file=file)
                
                # Limpiar archivo temporal
                os.unlink(temp_path)
            
            self.logger.info(f"Transcript generated for ticket #{ticket_info['number']:04d}")
            
        except Exception as e:
            self.logger.error(f"Error generating transcript: {e}")
