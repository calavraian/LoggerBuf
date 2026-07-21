import os
import urllib.request
import urllib.error
import click

SKILL_URL = "https://raw.githubusercontent.com/calavraian/LoggerBuf/main/.agents/skills/loggerbuf/SKILL.md"

def init_agents(base_dir=".agents/skills"):
    """
    Downloads and installs the official LoggerBuf agent SKILL.md.
    """
    # 1. Validate base_dir exists and is writable
    if not os.path.exists(base_dir):
        click.secho(f"Error: The base directory '{base_dir}' does not exist.", fg="red")
        click.secho("Please ensure the base directory exists before running this command.", fg="red")
        return False
        
    if not os.access(base_dir, os.W_OK):
        click.secho(f"Error: Write permission denied for directory '{base_dir}'.", fg="red")
        return False

    # 2. Create loggerbuf namespace folder
    skill_dir = os.path.join(base_dir, "loggerbuf")
    try:
        os.makedirs(skill_dir, exist_ok=True)
    except Exception as e:
        click.secho(f"Error creating directory '{skill_dir}': {e}", fg="red")
        return False

    # 3. Download the SKILL.md
    skill_file_path = os.path.join(skill_dir, "SKILL.md")
    click.secho(f"Downloading LoggerBuf SKILL.md from GitHub...", fg="cyan")
    
    try:
        with urllib.request.urlopen(SKILL_URL) as response:
            if response.status != 200:
                click.secho(f"Error downloading SKILL.md: HTTP {response.status}", fg="red")
                return False
            content = response.read()
            
        with open(skill_file_path, "wb") as f:
            f.write(content)
            
        click.secho(f"Success! Agent skill downloaded to: {os.path.abspath(skill_file_path)}", fg="green", bold=True)
        return True
    except urllib.error.URLError as e:
        click.secho(f"Network error while downloading SKILL.md: {e.reason}", fg="red")
        return False
    except Exception as e:
        click.secho(f"Failed to download or save SKILL.md: {e}", fg="red")
        return False
