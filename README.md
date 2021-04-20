[![Issues](https://img.shields.io/github/issues/IAmTomahawkx/taptrack.svg?colorB=3333ff)](https://github.com/IAmTomahawkx/taptrack/issues)
[![Commit activity](https://img.shields.io/github/commit-activity/w/IAmTomahawkx/taptrack)](https://github.com/IAmTomahawkx/taptrack/commits)
[![Commit activity](https://img.shields.io/github/license/IAmTomahawkx/taptrack)](https://github.com/IAmTomahawkx/taptrack)
___
<h1 align="center">
TapTrack
</h1>
<p align="center">
<sup>
Advanced error handling for bots built with <a href="https://github.com/Rapptz/discord.py">discord.py</a>
</sup>
</p>

___
Errors are a part of life as a developer, but nailing them down and fixing them can be a pain with limited information.
TapTrack removes the information barrier by tracking as much as possible, as soon as the error happens.
___

## Installation
TapTrack is beta software, so it is not available on pypi. To install it, use the following:
```bash
pip install -U git+https://github.com/IAmTomahawkx/taptrack.git
```

## Setting up
TapTrack makes use of many environment variables (see [Additional environment variables](#additional-environment-variables)), but here are the variables to use it.
<table>
    <tr>
        <td>
            <code>TAPTRACK_STORAGE</code>
        </td>
        <td>
            Tells the package how to store errors. Must be one of the following:
            <br>
            <list>
                <li>
                    <code>postgres</code> - requires package <a href="https://pypi.org/projects/asyncpg"><code>asyncpg</code></a>
                </li>
                <li>
                    <code>custom.MyClass</code> - see <a href="#custom-states">Custom states</a>
                </li>
            </list>
        </td>
    </tr>
    <tr>
        <td>
            <code>TAPTRACK_DB_URI</code>
        </td>
        <td>
            This must be set if <code>TAPTRACK_STORAGE</code> is any of the following:
            <list>
                <li><code>postgres</code></li>
            </list>
            This should be a URI string that connects to your database
        </td>
    </tr>
</table>

After making sure these environment variables are set, insert this into your code
```python
bot.load_extension("taptrack")
```
This will automatically start a listener that will track uncaught errors (Uncaught errors are errors that do not subclass
[CommandError](https://discordpy.readthedocs.io/en/latest/ext/commands/api.html#discord.ext.commands.CommandError)).
Additionally, this will insert the `taptrack` command into your bot. See [taptrack commands](#taptrack-commands) for more info.

## Custom states
Custom states allow you to create your own method of storing taptracks errors. This can be accomplished by subclassing `taptrack.state.AbstractState`,
along with setting your `TAPTRACK_STORAGE` environment variable to `custom.subclassName`. For example, if your subclass
is named `MyState`, your `TAPTRACK_STORAGE` variable would be `custom.mystate` (case-insensitive)

## taptrack commands
<table>
    <tr>
        <td>
            <code>taptrack</code>
        </td>
        <td>
            Shows a brief overview of your error statuses.
        </td>
    </tr>
    <tr>
        <td>
            <code>taptrack error &lt;number&gt;</code>
        </td>
        <td>
            Gives a more advanced overview on a specific error.
        </td>
    </tr>
    <tr>
        <td>
            <code>taptrack trace &lt;number&gt;</code>
        </td>
        <td>
            Gives a full traceback. If the traceback is too long, it will be uploaded to a paste site.
        </td>
    </tr>
    <tr>
        <td>
            <code>taptrack messages &lt;number&gt;</code>
        </td>
        <td>
            Shows you raw data on all messages that have triggered the error.
        </td>
    </tr>
    <tr>
        <td>
            <code>taptrack frames &lt;number&gt;</code>
        </td>
        <td>
            Shows you the scope (variables) in every frame of the traceback. If these are too large for discord, they will be uploaded to a paste site.
        </td>
    </tr>
</table>

## Additional environment variables
There are more environment variables that can be set to customize TapTrack
<table>
    <tr>
        <td>
            <code>TAPTRACK_WEBHOOK_URL</code>
        </td>
        <td>
            If set, this should be a discord webhook URL. This will receive updates every time an error occurs,
            every time an error state is updated, etc.
        </td>
    </tr>
    <tr>
        <td>
            <code>TAPTRACK_PASTE_SITE</code>
        </td>
        <td>
            This can be used to change where the errors will go when they are too large for discord.
            The site in question must have a hastebin-like /documents endpoint that takes the text as the request body,
            and returns a json body with a <code>key</code> key. Defaults to <a href="https://mystb.in">https://mystb.in</a>
        </td>
    </tr>
    <tr>
        <td>
            <code>TAPTRACK_PASTE_AUTHORIZATION</code>
        </td>
        <td>
            Optional Authorization header for the paste site. 
        </td>
    </tr>
</table>