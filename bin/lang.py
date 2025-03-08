#!/usr/bin/env python3
import shlex
from langchain.schema.runnable import Runnable
from langchain_core.runnables import RunnableMap, RunnableSequence
import sys
import subprocess

def resolve_alias(alias_name):
    """Resolve the full absolute path of an alias."""
    command = f"bash -i -c 'alias {alias_name}'"
    process = subprocess.run(command, shell=True, text=True, capture_output=True)

    if process.returncode != 0:
        raise RuntimeError(f"Failed to resolve alias. Error: {process.stderr.strip()}")

    alias_output = process.stdout.strip()
    if alias_output.startswith(f"alias {alias_name}="):
        alias_command = alias_output.split('=')[1].strip("'")
        base_command = alias_command.split()[0]
        abs_path_process = subprocess.run(
            ["which", base_command], 
            text=True, 
            capture_output=True
        )
        if abs_path_process.returncode == 0:
            return abs_path_process.stdout.strip()
        else:
            raise RuntimeError(f"Failed to resolve absolute path of command: {base_command}. Error: {abs_path_process.stderr.strip()}")
    else:
        raise RuntimeError(f"Failed to parse alias output: {alias_output}")

F_FULL_PATH = resolve_alias("f")
print(f"Resolved path for alias 'f': {F_FULL_PATH}")

class f_yt(Runnable):
    def invoke(self, input, context=None):
        command = f"{F_FULL_PATH} yt {shlex.quote(input)}"
        process = subprocess.run(
            command,
            shell=True,
            text=True,
            capture_output=True
        )
        print("\n[Step 1: Transcript Extraction Output]:\n\n", process.stdout)
        if process.returncode == 0:
            return process.stdout
        else:
            raise RuntimeError(f"Failed to extract transcript. Error: {process.stderr}")

class f_find_logical_fallacies(Runnable):
    def invoke(self, input, context=None):
        command = f"{F_FULL_PATH} find_logical_fallacies"
        process = subprocess.run(
            command,
            shell=True,
            text=True,
            capture_output=True,
            input=input
        )
        print("\n[Step 2: Logical Fallacies Output]:\n\n", process.stdout)
        if process.returncode == 0:
            return process.stdout
        else:
            raise RuntimeError(f"Failed to find logical fallacies. Error: {process.stderr}")

class f_extract_wisdom(Runnable):
    def invoke(self, input, context=None):
        command = f"{F_FULL_PATH} extract_wisdom"
        process = subprocess.run(
            command,
            shell=True,
            text=True,
            capture_output=True,
            input=input
        )
        print("\n[Step 3: Wisdom Extraction Output]:\n\n", process.stdout)
        if process.returncode == 0:
            return process.stdout
        else:
            raise RuntimeError(f"Failed to extract wisdom. Error: {process.stderr}")

class f_extract_main_idea(Runnable):
    def invoke(self, input, context=None):
        combined_input = "\n".join(input.values())
        command = f"{F_FULL_PATH} extract_main_idea"
        process = subprocess.run(
            command,
            shell=True,
            text=True,
            capture_output=True,
            input=combined_input
        )
        print("\n[Step 4: Main Idea Extraction Output]:\n\n", process.stdout)
        if process.returncode == 0:
            return process.stdout
        else:
            raise RuntimeError(f"Failed to extract main idea. Error: {process.stderr}")

get_transcript = f_yt()
find_logical_fallacies = f_find_logical_fallacies()
extract_wisdom = f_extract_wisdom()
extract_main_idea = f_extract_main_idea()

pipeline = RunnableSequence(
    get_transcript,
    RunnableMap(
        {
            "logical_flaws": find_logical_fallacies,
            "wisdom": extract_wisdom,
        }
    ),
    extract_main_idea
)

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python3 script.py <youtube_url>")
        sys.exit(1)

    youtube_url = sys.argv[1]
    outputs = pipeline.invoke(youtube_url)

