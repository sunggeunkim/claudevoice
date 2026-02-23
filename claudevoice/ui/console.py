from rich.console import Console
from rich.theme import Theme

theme = Theme({
    "tool": "cyan",
    "error": "red bold",
    "cost": "dim",
    "thinking": "dim italic",
    "prompt": "bold blue",
    "banner": "dim",
})

console = Console(theme=theme)
