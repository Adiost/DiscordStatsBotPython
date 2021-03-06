from discord.ext import commands
import discord
import logging
import asyncio
import asyncpg
import subprocess
import textwrap
import traceback
import re
import io
from contextlib import redirect_stdout


class Owner(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.settings = bot.settings
        self.pool = bot.pool
        self.config = bot.config

    # This cog is bot owner only
    async def cog_check(self, ctx):
        return await self.bot.is_owner(ctx.author)
    
    @commands.command()
    async def kill(self, ctx):
        await ctx.send('See you space cowboy...')
        await self.bot.close()

    @commands.command(aliases=['rl', 'rc'])
    async def reload(self, ctx, *, module):
        try:
            self.bot.reload_extension(f'cogs.{module}')
        except commands.ExtensionError as e:
            await ctx.send(f'{e.__class__.__name__}: {e}')
        except e:
            await ctx.send(str(e))
        else:
            await ctx.send('\N{OK HAND SIGN}')

    @commands.command(aliases=['gpl'])
    async def git_pull(self, ctx):
        async with ctx.typing():
            stdout, _ = await self.run_process('git pull')
            await ctx.send(stdout)

    @commands.command(aliases=['db'])
    async def db_fetch(self, ctx, *, query):
        async with ctx.typing():
            res = await self.pool.fetch(query)
            if res:
                await ctx.send([tuple(r) for r in res])
            else:
                await ctx.send('No rows returned')

    @commands.command(aliases=['rs'])
    async def restart(self, ctx):
        await self._restart(ctx)

    async def _restart(self, ctx):
        await ctx.send('Restarting...')
        self.bot.config.debugging = True
        await asyncio.create_subprocess_shell('(sleep 3 && . ~/.venv/ciri/bin/activate && python3 launcher.py) &', close_fds=True)
        await self.bot.close()

    @commands.command()
    async def update(self, ctx):
        async with ctx.typing():
            stdout, _ = await self.run_process('git pull')
            if 'bot.py' in stdout:
                await self._restart(ctx)
            else:
                cogs = re.findall(r'cogs/(\w+?)\.py', stdout)
                if not cogs:
                    await ctx.send('Nothing to update')
                    return
                try:
                    for cog in cogs:
                        if cog == 'utils':
                            continue
                        self.bot.reload_extension(f'cogs.{cog}')
                except commands.ExtensionError as e:
                    await ctx.send(f'{e.__class__.__name__}: {e}')
                except e:
                    await ctx.send(str(e))
                else:
                    await ctx.send('\N{OK HAND SIGN} Updated cogs {}'.format(', '.join(cogs)))

    @commands.command(aliases=['log'])
    async def tail_log(self, ctx):
        async with ctx.typing():
            stdout, stderr = await self.run_process('tail -n 30 cirilla.log')
            await ctx.send('```' + stdout[-1994:] + '```')
            if stderr:
                await ctx.send('Error:\n' + stderr)

    @commands.command(aliases=['err'])
    async def tail_error(self, ctx):
        async with ctx.typing():
            stdout, stderr = await self.run_process('tail -n 30 cirilla_errors.log')
            if not stdout:
                stdout = 'No errors'
            await ctx.send('```' + stdout[-1994:] + '```')
            if stderr:
                await ctx.send('Error:\n' + stderr)

    @commands.command(aliases=['sh'])
    async def shell(self, ctx, *, script):
        async with ctx.typing():
            stdout, stderr = await self.run_process(script)
            await ctx.send(stdout)
            if stderr:
                await ctx.send('Error:\n' + stderr)

    @commands.command(hidden=True, name='eval')
    async def _eval(self, ctx, *, body: str):
        """Evaluates a code"""

        env = {
            'bot': self.bot,
            'ctx': ctx,
            'channel': ctx.channel,
            'author': ctx.author,
            'guild': ctx.guild,
            'message': ctx.message
        }

        env.update(globals())

        body = self.cleanup_code(body)
        stdout = io.StringIO()

        to_compile = f'async def func():\n{textwrap.indent(body, "  ")}'

        try:
            exec(to_compile, env)
        except Exception as e:
            return await ctx.send(f'```py\n{e.__class__.__name__}: {e}\n```')

        func = env['func']
        try:
            with redirect_stdout(stdout):
                ret = await func()
        except Exception as e:
            value = stdout.getvalue()
            await ctx.send(f'```py\n{value}{traceback.format_exc()}\n```')
        else:
            value = stdout.getvalue()
            try:
                await ctx.message.add_reaction('\u2705')
            except:
                pass

            if ret is None:
                if value:
                    await ctx.send(f'```py\n{value}\n```')
            else:
                await ctx.send(f'```py\n{value}{ret}\n```')

    def cleanup_code(self, content):
        """Automatically removes code blocks from the code."""
        # remove ```py\n```
        if content.startswith('```') and content.endswith('```'):
            return '\n'.join(content.split('\n')[1:-1])

        # remove `foo`
        return content.strip('` \n')
    
    async def run_process(self, command):
        try:
            process = await asyncio.create_subprocess_shell(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            result = await process.communicate()
        except NotImplementedError:
            process = subprocess.Popen(command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            result = await self.bot.loop.run_in_executor(None, process.communicate)

        return [output.decode() for output in result]
            
def setup(bot):
    bot.add_cog(Owner(bot))