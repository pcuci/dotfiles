#!/usr/bin/env python3

import os
import shutil
import sys

def is_text_file(file_path):
    """
    Determine if a file is a text file by attempting to decode it.
    """
    try:
        with open(file_path, 'rb') as f:
            # Read a small sample of the file
            sample = f.read(1024)
            # Try decoding with utf-8
            sample.decode('utf-8')
        return True
    except UnicodeDecodeError:
        # Not a text file if decoding fails
        return False
    except Exception as e:
        print(f"Error reading file {file_path}: {e}")
        return False

def should_ignore_file(file_name):
    """
    Determine if a file should be ignored based on its name or extension.
    """
    ignore_files = {'LICENSE.md'}
    ignore_extensions = {'.svg'}
    _, ext = os.path.splitext(file_name)
    return file_name in ignore_files or ext.lower() in ignore_extensions

def flatten_directory(source_dir, target_dir, force=False):
    if os.path.exists(target_dir):
        if force:
            shutil.rmtree(target_dir)
            os.makedirs(target_dir)
        else:
            user_input = input(f"Target directory '{target_dir}' already exists. Overwrite? (y/n): ").strip().lower()
            if user_input == 'y':
                shutil.rmtree(target_dir)
                os.makedirs(target_dir)
            else:
                print("Operation cancelled.")
                sys.exit(1)
    else:
        os.makedirs(target_dir)

    for root, dirs, files in os.walk(source_dir):
        for file_name in files:
            if should_ignore_file(file_name):
                print(f"{os.path.join(root, file_name)} SKIPPED (ignored)")
                continue

            file_path = os.path.join(root, file_name)
            if is_text_file(file_path):
                # Resolve potential name conflicts
                dest_file_name = file_name
                dest_file_path = os.path.join(target_dir, dest_file_name)
                count = 1
                while os.path.exists(dest_file_path):
                    base_name, ext = os.path.splitext(file_name)
                    dest_file_name = f"{base_name}_{count}{ext}"
                    dest_file_path = os.path.join(target_dir, dest_file_name)
                    count += 1
                shutil.copy2(file_path, dest_file_path)
                print(f"Copied text file to: {dest_file_path}")
            else:
                print(f"{file_path} SKIPPED")

def main():
    if len(sys.argv) < 3:
        print("Usage: python flatten_directory.py <source_dir> <target_dir> [--force]")
        sys.exit(1)
    source_dir = sys.argv[1]
    target_dir = sys.argv[2]
    force = '--force' in sys.argv
    flatten_directory(source_dir, target_dir, force)

if __name__ == "__main__":
    main()
