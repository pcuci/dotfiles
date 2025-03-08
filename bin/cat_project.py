#!/usr/bin/env python3

import os
import subprocess

def get_tracked_python_files():
    """Retrieve Python files tracked by Git, respecting .gitignore."""
    try:
        result = subprocess.run(
            ["git", "ls-files", "--cached", "--others", "--exclude-standard"],
            capture_output=True,
            text=True,
            check=True
        )
        return [file for file in result.stdout.splitlines() if file.endswith(".py")]
    except subprocess.CalledProcessError:
        print("Error: Ensure this script is run inside a Git repository.")
        return []

def main():
    output_file = f"/tmp/{os.path.basename(os.getcwd())}.txt"

    with open(output_file, "w", encoding="utf-8") as out:
        for file in get_tracked_python_files():
            print(f"\n{file}:\n")
            out.write(f"\n{file}:\n\n")

            try:
                with open(file, "r", encoding="utf-8") as f:
                    content = f.read()
                    print(content)
                    out.write(content + "\n\n\n")
            except Exception as e:
                print(f"Error reading {file}: {e}")
                out.write(f"Error reading {file}: {e}\n\n\n")

    print(f"\n✅ Output saved to {output_file}")

if __name__ == "__main__":
    main()
